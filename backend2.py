import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import json

# --- Imports from your helpers ---
from extract_ab_block_from_pdf import extract_relevant_block_from_pdf
from extract_entries_from_ab_block import extract_ab_und_zusetzungen


# --- Configuration ---
load_dotenv()
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

# --- Firebase Init ---
#cred = credentials.Certificate('fire-base.json')
cred = credentials.Certificate('/etc/secrets/fire-base.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def normalize_nr(nr):
    return nr.replace(" ", "").lower() if nr else ""

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
    incomplete_entries_with_names = []  # <--- new
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
            block = extract_relevant_block_from_pdf(tmp.name)
            billing_date = extract_billing_date(tmp.name)
        os.unlink(tmp.name)
        print(f"\n--- Debug: BLOCK EXTRACTED for {file.filename} ---\n{block}\n--- END BLOCK ---\n")
        if not block:
            invalid_files.append({"filename": file.filename, "reason": "no_data"})
            continue
        # Updated: get both parsed_list and skipped_any from the parser
        parsed_list, skipped_any = extract_ab_und_zusetzungen(block)
        print(f"\n--- Debug: REGEX RESPONSE for {file.filename} ---\n{parsed_list}\n--- END RESPONSE ---\n")
        if not parsed_list or not isinstance(parsed_list, list) or len(parsed_list) == 0:
            print(f"\n--- Debug: Regex returned empty or invalid list for {file.filename} ---\n")
            invalid_files.append({"filename": file.filename, "reason": "no_data"})
            continue
        # If any required entry is missing/empty, skip file
        required_fields = ["Name", "Rechnungsempfängers", "Rechnungs-Nr. DZR", "Ihre Rechnungs-Nr.", "Betrag"]
        if not all(
            isinstance(entry, dict) and all(entry.get(field, '').strip() for field in required_fields)
            for entry in parsed_list
        ):
            print(f"Regex returned incomplete entry for {file.filename}")
            invalid_files.append({"filename": file.filename, "reason": "incomplete_entry"})
            continue
        # If any lines were skipped, mark for manual review and provide added names
        if skipped_any:
            names_found = [row['Name'] for row in parsed_list]
            incomplete_entries_with_names.append({
                "filename": file.filename,
                "added_names": names_found
            })
            invalid_files.append({"filename": file.filename, "reason": "incomplete_entry"})
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
                row["Betrag"] = f"{value:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')
            except Exception:
                pass  # If conversion fails, leave as is
            nr = normalize_nr(row.get("Ihre Rechnungs-Nr."))
            betrag = row.get("Betrag", "")
            if not nr or (nr, betrag) in existing_nr_betrag:
                continue  # Skip duplicate or empty
            doc_ref = db.collection('invoices').add(row)
            row['id'] = doc_ref[1].id
            all_rows.append(row)
            existing_nr_betrag.add((nr, betrag))  # Prevent duplicates within this batch
    return jsonify({
        'data': all_rows,
        'invalid_files': invalid_files,
        'incomplete_entries_with_names': incomplete_entries_with_names
    })

@app.route('/api/rows', methods=['GET'])
def get_rows():
    assigned_to_param = request.args.get('assigned_to', 'all')
    assigned_to_list = [x.strip() for x in assigned_to_param.split(',')] if assigned_to_param != 'all' else None

    docs = db.collection('invoices').stream()
    active_rows = []
    archived_rows = []
    for doc in docs:
        row = doc.to_dict()
        row['id'] = doc.id
        # Filter by assigned_to if specified
        if assigned_to_list and row.get('assigned_to', '') not in assigned_to_list:
            continue
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

@app.route('/api/manual_entry', methods=['POST'])
def manual_entry():
    data = request.json
    required_fields = ["Name", "Rechnungsempfängers", "Rechnungs-Nr. DZR", "Ihre Rechnungs-Nr.", "Betrag"]
    if not all(data.get(field, '').strip() for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    # Add default fields if not provided
    row = {col: data.get(col, '') for col in CSV_COLUMNS}
    row['notes'] = row.get('notes', '')
    row['starred'] = row.get('starred', False)
    row['assigned_to'] = row.get('assigned_to', '')
    row['handled_by'] = row.get('handled_by', '')
    row['archive_result'] = row.get('archive_result', '')
    row['Billing Date'] = row.get('Billing Date', '')

    # Ensure Betrag is always negative
    betrag = row.get("Betrag", "")
    betrag_clean = betrag.replace('.', '').replace(',', '.').replace(' ', '')
    try:
        value = float(betrag_clean)
        if value > 0:
            value = -value
        row["Betrag"] = f"{value:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')
    except Exception:
        pass  # If conversion fails, leave as is

    doc_ref = db.collection('invoices').add(row)
    row['id'] = doc_ref[1].id
    return jsonify({'success': True, 'row': row})

@app.route('/api/row/<row_id>/edit', methods=['POST'])
def edit_row(row_id):
    data = request.json
    required_fields = ["Name", "Rechnungsempfängers", "Rechnungs-Nr. DZR", "Ihre Rechnungs-Nr.", "Betrag", "Billing Date"]
    if not all(data.get(field, '').strip() for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    # Restriction: Betrag must be a number
    betrag = data.get("Betrag", "")
    betrag_clean = betrag.replace('.', '').replace(',', '.').replace(' ', '')
    try:
        value = float(betrag_clean)
        if value > 0:
            value = -value
        data["Betrag"] = f"{value:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')
    except Exception:
        return jsonify({'error': 'Betrag must be a valid number'}), 400

    # Restriction: Rechnungs-Nr. DZR must only contain numbers and /
    if not re.fullmatch(r'[0-9/]+', data.get("Rechnungs-Nr. DZR", "")):
        return jsonify({'error': 'Rechnungs-Nr. DZR must only contain numbers and /'}), 400

    db.collection('invoices').document(row_id).update(data)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
