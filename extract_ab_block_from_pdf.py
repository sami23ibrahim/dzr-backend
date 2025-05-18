import pdfplumber
import re

def extract_relevant_block_from_pdf(pdf_path: str) -> str:
    # Extract all text from all pages
    text = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + '\n'
    # Find all positions of 'Ab- und Zusetzungen' and 'Summe Ab- und Zusetzungen'
    starts = [m.start() for m in re.finditer(r"Ab- und Zusetzungen", text)]
    ends = [m.start() for m in re.finditer(r"Summe Ab- und Zusetzungen", text)]
    if not starts or not ends:
        return None
    # Pick the last 'Ab- und Zusetzungen' that is BEFORE any end marker
    start = None
    for s in reversed(starts):
        if any(e > s for e in ends):
            start = s
            break
    if start is None:
        return None
    end = min(e for e in ends if e > start)
    block = text[start:end]

    # --- NEW: Remove header lines automatically ---
    lines = block.splitlines()
    # Remove empty lines
    lines = [line for line in lines if line.strip()]
    # Remove the first 2 or 3 lines if they match the known header pattern
    # Adjust this number if your header is sometimes longer/shorter
    header_phrases = [
        "Ab- und Zusetzungen",
        "Name des Patienten/ Rechnungs-Nr. Ihre Rechnungs-Nr. Betrag",
        "Rechnungsempfängers DZR"
    ]
    # Remove lines that match any header phrase at the start of the block
    while lines and any(h in lines[0] for h in header_phrases):
        lines.pop(0)
    while lines and any(h in lines[0] for h in header_phrases):  # In case header repeats
        lines.pop(0)
    # You can also remove 2-3 lines blindly if the above doesn't work for some PDFs
    block_cleaned = "\n".join(lines)
    return block_cleaned.strip()
