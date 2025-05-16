import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import requests
import pandas as pd
import re
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import json

# AI and extraction config
load_dotenv()
API_KEY = os.getenv('API_KEY')
API_URL = 'https://openrouter.ai/api/v1/chat/completions'
CSV_COLUMNS = [
    'Name',
    'Rechnungsempfängers',
    'Rechnungs-Nr. DZR',
    'Ihre Rechnungs-Nr.',
    'Betrag',
    'Billing Date',
    'notes',
    'starred',
    'assigned_to',
    'handled_by',
    'archive_result'
]

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin
print("FIREBASE_SERVICE_ACCOUNT:", os.getenv('FIREBASE_SERVICE_ACCOUNT'))
cred = credentials.Certificate('/etc/secrets/d3z-pdf-firebase-adminsdk-fbsvc-613ac76010.json')
#cred = credentials.Certificate('d3z-pdf-firebase-adminsdk-fbsvc-613ac76010.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def normalize_nr(nr):
    return nr.replace(" ", "").lower() if nr else ""

def extract_relevant_block(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    # Extract block between the two markers
    start = text.find('Ab- und Zusetzungen')
    end = text.find('Summe Ab- und Zusetzungen')
    if start == -1 or end == -1 or end <= start:
        return None
    block = text[start:end]
    return block.strip()

def parse_block_with_ai(block):
#     prompt = f"""
# Extract all data rows (ignore any table headers or column names) from the following text block (between 'Ab- und Zusetzungen' and 'Summe Ab- und Zusetzungen').
# For each row, extract:
# - Name (the first part of the main entry line, before the invoice numbers)
# - Rechnungs-Nr. DZR (the invoice number, on the main entry line)
# - Ihre Rechnungs-Nr. (your invoice number, on the main entry line)
# - Betrag (the amount, on the main entry line)
# - Rechnungsempfängers (the line(s) that come after the Betrag for each entry, until the next entry starts; join all such lines as one field. If there is no such line, leave this field blank.)

# Return the result as a JSON array, where each element is an object with these keys: Name, Rechnungsempfängers, Rechnungs-Nr. DZR, Ihre Rechnungs-Nr., Betrag. Do not include any header or column name rows in the output.

# Important:
# If, for any entry, one or more of the five required fields (Name, Rechnungsempfängers, Rechnungs-Nr. DZR, Ihre Rechnungs-Nr., Betrag) is missing or empty, do not return any data. Instead, return only this JSON:
# {{
#   "error": "This file could not be processed automatically. Please handle it manually."
# }}

# Example input block:
# Lisa Anne Sibbing 297426/12/2023 130 (GOZ) -123,64
# Telefonisch: Direktzahlung vom 19.02.2024
# Emine Sarihan 506432/03/2024 459 (EA) -179,26
# Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis

# Example output:
# [
#   {{
#     "Name": "Lisa Anne Sibbing",
#     "Rechnungsempfängers": "Telefonisch: Direktzahlung vom 19.02.2024",
#     "Rechnungs-Nr. DZR": "297426/12/2023",
#     "Ihre Rechnungs-Nr.": "130 (GOZ)",
#     "Betrag": "-123,64"
#   }},
#   {{
#     "Name": "Emine Sarihan",
#     "Rechnungsempfängers": "Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis",
#     "Rechnungs-Nr. DZR": "506432/03/2024",
#     "Ihre Rechnungs-Nr.": "459 (EA)",
#     "Betrag": "-179,26"
#   }},
# ]

# Text block:
# {block}
# """



    prompt = f"""
Extract all data rows from the following text block (between 'Ab- und Zusetzungen' and 'Summe Ab- und Zusetzungen').

Each row must explicitly have these fields:
1. Name: Text at the start of the line before the first invoice number.
2. Rechnungs-Nr. DZR: Invoice number in the exact format 'XXXXXX/XX/XXXX'.
3. Ihre Rechnungs-Nr.: Invoice identifier (e.g. '1029 (GOZ)'). 
4. Betrag: Numeric amount at the end of the line (e.g. '-61,14').
5. Rechnungsempfängers: Any lines following the main line until the next main entry.

Critical instructions to detect missing fields clearly:
- A valid main line always has at least three clear elements in sequence after the Name: "Rechnungs-Nr. DZR", "Ihre Rechnungs-Nr.", "Betrag".
- "Rechnungs-Nr. DZR" is ALWAYS a number in the explicit format "XXXXXX/XX/XXXX".
- "Betrag" is ALWAYS numeric (positive or negative) and at the very end of the main line.
- "Ihre Rechnungs-Nr." should appear BETWEEN the "Rechnungs-Nr. DZR" and "Betrag". If there is NO clear separate field between "Rechnungs-Nr. DZR" and "Betrag", this explicitly means "Ihre Rechnungs-Nr." is missing.
Important clarifications:
- If a field is explicitly represented as empty parentheses "()", explicitly set the field as "" (empty string).
- If a field is entirely missing or unclear (not explicitly represented), do NOT guess the field; instead, STOP extraction immediately and return only this JSON:{{
  "error": "This file could not be processed automatically. Please handle it manually."
}}

Examples to illustrate this clearly:

Example Input:
Thomas Müller 341342/02/2024 -44,55
Extra notes line here

Correct Output (because "Ihre Rechnungs-Nr." is clearly missing):
{{
  "error": "This file could not be processed automatically. Please handle it manually."
}}

Another Example Input:
Emine Sarihan 506432/03/2024 () -179,26
Extra notes here

Correct Output (because parentheses explicitly show "Ihre Rechnungs-Nr." is empty but clearly indicated):
[
  {{
    "Name": "Emine Sarihan",
    "Rechnungsempfängers": "Extra notes here",
    "Rechnungs-Nr. DZR": "506432/03/2024",
    "Ihre Rechnungs-Nr.": "",
    "Betrag": "-179,26"
  }}
]

Text block to extract:
{block}
"""




    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(API_URL, headers=headers, json=data)
    try:
        response.raise_for_status()
        result = response.json()
        import json as pyjson
        content = result['choices'][0]['message']['content']
        # Remove code block markers if present
        if content.strip().startswith('```'):
            content = content.strip().split('\n', 1)[1].rsplit('```', 1)[0]
        parsed = pyjson.loads(content)
        return parsed
    except Exception as e:
        print('Failed to parse AI response:', e)
        print('AI response:', getattr(response, 'text', None))
        # Special marker for AI exhaustion or error
        return '__AI_ERROR__'

def extract_billing_date(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text()
    # Look for 'Abrechnungsdatum' followed by a date
    match = re.search(r'Abrechnungsdatum\s+(\d{2}[.\/]\d{2}[.\/]\d{4})', first_page_text)
    if match:
        return match.group(1)
    return ''

@app.route('/api/upload', methods=['POST'])
def upload_invoices():
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400
    files = request.files.getlist('files')
    all_rows = []
    invalid_files = []
    ai_error = False
    # Gather all existing (Ihre Rechnungs-Nr., Betrag) pairs from Firestore (active and archived)
    existing_nr_betrag = set()
    docs = db.collection('invoices').stream()
    for doc in docs:
        doc_data = doc.to_dict()
        doc_nr = normalize_nr(doc_data.get("Ihre Rechnungs-Nr."))
        doc_betrag = doc_data.get("Betrag", "")
        if doc_nr:
            existing_nr_betrag.add((doc_nr, doc_betrag))
    for file in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            block = extract_relevant_block(tmp.name)
            billing_date = extract_billing_date(tmp.name)
        os.unlink(tmp.name)
        print(f"\n--- Debug: BLOCK SENT TO AI for {file.filename} ---\n{block}\n--- END BLOCK ---\n")
        if not block:
            invalid_files.append({"filename": file.filename, "reason": "no_data"})
            continue
        parsed_list = parse_block_with_ai(block)
        print(f"\n--- Debug: AI RESPONSE for {file.filename} ---\n{parsed_list}\n--- END AI RESPONSE ---\n")
        if parsed_list == '__AI_ERROR__':
            ai_error = True
            break
        if isinstance(parsed_list, dict) and parsed_list.get("error"):
            print(f"\n--- Debug: AI ERROR for {file.filename} ---\n{parsed_list['error']}\n")
            invalid_files.append({"filename": file.filename, "reason": "incomplete_entry"})  # Frontend: show 'The following files may contain corrupted data. Please handle them manually.'
            continue
        if not parsed_list or not isinstance(parsed_list, list) or len(parsed_list) == 0:
            print(f"\n--- Debug: AI returned empty or invalid list for {file.filename} ---\n")
            invalid_files.append({"filename": file.filename, "reason": "no_data"})
            continue
        # DO NOT FORGET: If any entry is missing/empty, skip the whole file!
        required_fields = ["Name", "Rechnungsempfängers", "Rechnungs-Nr. DZR", "Ihre Rechnungs-Nr.", "Betrag"]
        if not all(
            isinstance(entry, dict) and all(entry.get(field, '').strip() for field in required_fields)
            for entry in parsed_list
        ):
            print(f"AI returned incomplete entry for {file.filename}")
            invalid_files.append({"filename": file.filename, "reason": "incomplete_entry"})  # Frontend: show 'The following files may contain corrupted data. Please handle them manually.'
            continue  # Skip this file, do not add any rows
        for parsed in parsed_list:
            row = {col: parsed.get(col, '') for col in CSV_COLUMNS}
            print(f"\n--- Debug: ROW TO BE ADDED for {file.filename} ---\n{row}\n--- END ROW ---\n")
            row['Billing Date'] = billing_date
            row['notes'] = ""
            row['starred'] = False
            row['assigned_to'] = ""
            # Ensure Betrag is always negative
            betrag = row.get("Betrag", "")
            betrag_clean = betrag.replace('.', '').replace(',', '.').replace(' ', '')
            try:
                value = float(betrag_clean)
                if value > 0:
                    value = -value
                # Format back to German style (e.g., -49,33)
                row["Betrag"] = f"{value:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')
            except Exception:
                pass  # If conversion fails, leave as is
            nr = normalize_nr(row.get("Ihre Rechnungs-Nr."))
            betrag = row.get("Betrag", "")
            if not nr or (nr, betrag) in existing_nr_betrag:
                continue  # Skip duplicate or empty
            # Add to Firestore
            doc_ref = db.collection('invoices').add(row)
            row['id'] = doc_ref[1].id
            all_rows.append(row)
            existing_nr_betrag.add((nr, betrag))  # Prevent duplicates within this batch
    if ai_error:
        return jsonify({'ai_error': True}), 200
    return jsonify({'data': all_rows, 'invalid_files': invalid_files})

@app.route('/api/rows', methods=['GET'])
def get_rows():
    docs = db.collection('invoices').stream()
    active_rows = []
    archived_rows = []
    for doc in docs:
        row = doc.to_dict()
        row['id'] = doc.id
        if row.get('archived'):
            archived_rows.append(row)
        else:
            active_rows.append(row)
    return jsonify({'active': active_rows, 'archived': archived_rows})

@app.route('/api/row/<row_id>/archive', methods=['POST'])
def archive_row(row_id):
    data = request.json or {}
    archive_result = data.get('archive_result', '')
    doc_ref = db.collection('invoices').document(row_id)
    doc = doc_ref.get()
    handled_by = ""
    if doc.exists:
        doc_data = doc.to_dict()
        handled_by = doc_data.get('assigned_to', '')
    doc_ref.update({'archived': True, 'handled_by': handled_by, 'archive_result': archive_result})
    return jsonify({'success': True})

@app.route('/api/row/<row_id>', methods=['DELETE'])
def delete_row(row_id):
    db.collection('invoices').document(row_id).delete()
    return jsonify({'success': True})

@app.route('/api/row/<row_id>/unarchive', methods=['POST'])
def unarchive_row(row_id):
    db.collection('invoices').document(row_id).update({'archived': False})
    return jsonify({'success': True})

@app.route('/api/row/<row_id>/notes', methods=['POST'])
def update_notes(row_id):
    notes = request.json.get('notes', '')
    db.collection('invoices').document(row_id).update({'notes': notes})
    return jsonify({'success': True})

@app.route('/api/row/<row_id>/starred', methods=['POST'])
def update_starred(row_id):
    starred = request.json.get('starred', False)
    db.collection('invoices').document(row_id).update({'starred': starred})
    return jsonify({'success': True})

@app.route('/api/row/<row_id>/assigned_to', methods=['POST'])
def update_assigned_to(row_id):
    assigned_to = request.json.get('assigned_to', '')
    db.collection('invoices').document(row_id).update({'assigned_to': assigned_to})
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True) 