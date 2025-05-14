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
cred = credentials.Certificate('d3z-pdf-firebase-adminsdk-fbsvc-613ac76010.json')
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
    prompt = f"""
Extract all data rows (ignore any table headers or column names) from the following text block (between 'Ab- und Zusetzungen' and 'Summe Ab- und Zusetzungen').
For each row, extract:
- Name (the first line of the row, which is the person's name)
- Rechnungsempfängers (all lines after the name, before the invoice numbers, joined as one field; if there is no such line, leave this field blank)
- Rechnungs-Nr. DZR
- Ihre Rechnungs-Nr.
- Betrag
Return the result as a JSON array, where each element is an object with these keys: Name, Rechnungsempfängers, Rechnungs-Nr. DZR, Ihre Rechnungs-Nr., Betrag. Do not include any header or column name rows in the output.

Example input block:
Ab- und Zusetzungen
Name des Patienten/ Rechnungsempfängers        Rechnungs-Nr. DZR    Ihre Rechnungs-Nr.    Betrag
Bradley Stephenson
  Schriftwechsel - Sonstiges                  389853/03/2025       2293 (EA)             -300,16
Oussama Sabri
  Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis    806429/04/2025       2443 (GOZ)            -1.581,87
Mahmoud Khaled
  Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis    806437/04/2025       2422 (EA)             -115,00
Summe Ab- und Zusetzungen

Example output:
[
  {{
    "Name": "Bradley Stephenson",
    "Rechnungsempfängers": "Schriftwechsel - Sonstiges",
    "Rechnungs-Nr. DZR": "389853/03/2025",
    "Ihre Rechnungs-Nr.": "2293 (EA)",
    "Betrag": "-300,16"
  }},
  {{
    "Name": "Oussama Sabri",
    "Rechnungsempfängers": "Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis",
    "Rechnungs-Nr. DZR": "806429/04/2025",
    "Ihre Rechnungs-Nr.": "2443 (GOZ)",
    "Betrag": "-1.581,87"
  }},
  {{
    "Name": "Mahmoud Khaled",
    "Rechnungsempfängers": "Telefonat - Hakam El Daghma - Absetzung auf Wunsch der Praxis",
    "Rechnungs-Nr. DZR": "806437/04/2025",
    "Ihre Rechnungs-Nr.": "2422 (EA)",
    "Betrag": "-115,00"
  }}
]

Text block:
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
    # Gather all existing normalized Ihre Rechnungs-Nr. from Firestore (active and archived)
    existing_nrs = set()
    docs = db.collection('invoices').stream()
    for doc in docs:
        doc_nr = normalize_nr(doc.to_dict().get("Ihre Rechnungs-Nr."))
        if doc_nr:
            existing_nrs.add(doc_nr)
    for file in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            block = extract_relevant_block(tmp.name)
            billing_date = extract_billing_date(tmp.name)
        os.unlink(tmp.name)
        if not block:
            invalid_files.append(file.filename)
            continue
        parsed_list = parse_block_with_ai(block)
        if parsed_list == '__AI_ERROR__':
            ai_error = True
            break
        if not parsed_list or not isinstance(parsed_list, list) or len(parsed_list) == 0:
            invalid_files.append(file.filename)
            continue
        for parsed in parsed_list:
            row = {col: parsed.get(col, '') for col in CSV_COLUMNS}
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
            if not nr or nr in existing_nrs:
                continue  # Skip duplicate or empty
            # Add to Firestore
            doc_ref = db.collection('invoices').add(row)
            row['id'] = doc_ref[1].id
            all_rows.append(row)
            existing_nrs.add(nr)  # Prevent duplicates within this batch
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