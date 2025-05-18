# import os
# from extract_ab_block_from_pdf import extract_relevant_block_from_pdf
# from pdf_testing import extract_ab_und_zusetzungen

# def extract_billing_date(pdf_path):
#     import pdfplumber
#     import re
#     with pdfplumber.open(pdf_path) as pdf:
#         first_page_text = pdf.pages[0].extract_text()
#     match = re.search(r'Abrechnungsdatum\s+(\d{2}[.\/]\d{2}[.\/]\d{4})', first_page_text)
#     if match:
#         return match.group(1)
#     return ''

# # List your PDF files here
# pdf_files = [
#     "test1.pdf",
#     "test2.pdf"
# ]

# for pdf_file in pdf_files:
#     if not os.path.exists(pdf_file):
#         print(f"File not found: {pdf_file}")
#         continue

#     print(f"\n=== Processing: {pdf_file} ===")
#     block = extract_relevant_block_from_pdf(pdf_file)

#     # Print the extracted block right after extracting it:
#     print("\n--- Extracted Block ---")
#     print(block)
#     print("--- End Extracted Block ---\n")

#     if not block:
#         print("No valid block found in PDF!")
#         continue

#     billing_date = extract_billing_date(pdf_file)
#     rows = extract_ab_und_zusetzungen(block)

#     if not rows:
#         print("No valid invoice rows found!")
#         continue

#     for row in rows:
#         row['Billing Date'] = billing_date
#         print(row)


import os
from extract_ab_block_from_pdf import extract_relevant_block_from_pdf
from extract_entries_from_ab_block import extract_ab_und_zusetzungen

def extract_billing_date(pdf_path):
    import pdfplumber
    import re
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text()
    match = re.search(r'Abrechnungsdatum\s+(\d{2}[.\/]\d{2}[.\/]\d{4})', first_page_text)
    if match:
        return match.group(1)
    return ''

pdf_files = [
    "b.pdf",
    "b2.pdf",
    "b3.pdf",
    "b4.pdf",
    "g.pdf",
]

for pdf_file in pdf_files:
    if not os.path.exists(pdf_file):
        print(f"File not found: {pdf_file}")
        continue

    print(f"\n=== Processing: {pdf_file} ===")
    block = extract_relevant_block_from_pdf(pdf_file)
    print("\n--- Extracted Block ---")
    print(block)
    print("--- End Extracted Block ---\n")

    if not block:
        print("No valid block found in PDF!")
        continue

    billing_date = extract_billing_date(pdf_file)
    rows, skipped_any = extract_ab_und_zusetzungen(block)

    print("\n--- Parsed Entries ---")
    for row in rows:
        row['Billing Date'] = billing_date
        print(row)
    print("--- End Parsed Entries ---\n")

    if skipped_any:
        print(f"Manual review needed for '{pdf_file}'. The following entries were added:")
        for row in rows:
            print(f" - {row['Name']}")
    else:
        print(f"All entries added successfully for '{pdf_file}'.")
