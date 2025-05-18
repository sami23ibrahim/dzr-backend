# import re
# from typing import List, Dict, Tuple

# def extract_ab_und_zusetzungen(text: str) -> Tuple[List[Dict[str, str]], bool]:
#     main_row_pattern = re.compile(
#         r"^(.+?)\s+(\d{4,10}/\d{2}/\d{4})\s+([\d\s\(\)A-Za-z]+?)\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))$"
#     )
#     malformed_main_row_pattern = re.compile(
#         r"^(.+?)\s+\(\)\s+[\d\s\(\)A-Za-z]*\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$"
#     )

#     rows = []
#     skipped_any = False
#     lines = [line.strip() for line in text.split('\n') if line.strip()]
#     i = 0
#     while i < len(lines):
#         line = lines[i]
#         if main_row_pattern.match(line):
#             name, rechnungs_nr, ihre_nr, betrag = main_row_pattern.match(line).groups()
#             rechnungsempf = []
#             j = i + 1
#             while j < len(lines):
#                 next_line = lines[j]
#                 if (
#                     main_row_pattern.match(next_line) or
#                     malformed_main_row_pattern.match(next_line) or
#                     next_line.startswith("---") or
#                     "Betrag" in next_line or
#                     "Rechnungsempfängers" in next_line or
#                     re.match(r".*\(\)\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$", next_line)
#                 ):
#                     break
#                 rechnungsempf.append(next_line)
#                 j += 1
#             rows.append({
#                 "Name": name.strip(),
#                 "Rechnungs-Nr. DZR": rechnungs_nr.strip(),
#                 "Ihre Rechnungs-Nr.": ihre_nr.strip(),
#                 "Betrag": betrag.strip(),
#                 "Rechnungsempfängers": " ".join(rechnungsempf).strip()
#             })
#             i = j
#         else:
#             # If the line looks like a main candidate row but was skipped, set the flag
#             if re.match(r"^(.+?)\s+\d{4,10}/\d{2}/\d{4}", line):
#                 skipped_any = True
#             i += 1
#     return rows, skipped_any



# import re
# from typing import List, Dict, Tuple

# def extract_ab_und_zusetzungen(text: str) -> Tuple[List[Dict[str, str]], bool]:
#     main_row_pattern = re.compile(
#         r"^(.+?)\s+(\d{4,10}/\d{2}/\d{4})\s+([\d\s\(\)A-Za-z]+?)\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))$"
#     )
#     malformed_main_row_pattern = re.compile(
#         r"^(.+?)\s+\(\)\s+[\d\s\(\)A-Za-z]*\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$"
#     )

#     rows = []
#     skipped_any = False
#     lines = [line.strip() for line in text.split('\n') if line.strip()]
#     i = 0
#     while i < len(lines):
#         line = lines[i]
#         if main_row_pattern.match(line):
#             name, rechnungs_nr, ihre_nr, betrag = main_row_pattern.match(line).groups()
#             rechnungsempf = []
#             j = i + 1
#             while j < len(lines):
#                 next_line = lines[j]
#                 if (
#                     main_row_pattern.match(next_line) or
#                     malformed_main_row_pattern.match(next_line) or
#                     next_line.startswith("---") or
#                     "Betrag" in next_line or
#                     "Rechnungsempfängers" in next_line or
#                     re.match(r".*\(\)\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$", next_line)
#                 ):
#                     break
#                 rechnungsempf.append(next_line)
#                 j += 1
#             rows.append({
#                 "Name": name.strip(),
#                 "Rechnungs-Nr. DZR": rechnungs_nr.strip(),
#                 "Ihre Rechnungs-Nr.": ihre_nr.strip(),
#                 "Betrag": betrag.strip(),
#                 "Rechnungsempfängers": " ".join(rechnungsempf).strip()
#             })
#             i = j
#         else:
#             # Flag skipped lines that look like main entries, including those starting with a number/date
#             name_date = re.match(r"^[A-Za-zÄÖÜäöüß\- ]+\s+\d{4,10}/\d{2}/\d{4}", line)
#             date_name = re.match(r"^\d{4,10}/\d{2}/\d{4}\s+.+", line)
#             digit_date = re.match(r"^\d{4,10}/\d{2}/\d{4}", line)
#             if name_date or date_name or digit_date:
#                 skipped_any = True
#             i += 1
#     return rows, skipped_any



import re
from typing import List, Dict, Tuple

def extract_ab_und_zusetzungen(text: str) -> Tuple[List[Dict[str, str]], bool]:
    main_row_pattern = re.compile(
        r"^(.+?)\s+(\d{4,10}/\d{2}/\d{4})\s+([\d\s\(\)A-Za-z]+?)\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))$"
    )
    malformed_main_row_pattern = re.compile(
        r"^(.+?)\s+\(\)\s+[\d\s\(\)A-Za-z]*\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$"
    )

    rows = []
    skipped_any = False
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if main_row_pattern.match(line):
            name, rechnungs_nr, ihre_nr, betrag = main_row_pattern.match(line).groups()
            rechnungsempf = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if (
                    main_row_pattern.match(next_line) or
                    malformed_main_row_pattern.match(next_line) or
                    next_line.startswith("---") or
                    "Betrag" in next_line or
                    "Rechnungsempfängers" in next_line or
                    re.match(r".*\(\)\s*-?\d{1,3}(?:\.\d{3})*(?:,\d+)$", next_line)
                ):
                    break
                rechnungsempf.append(next_line)
                j += 1
            rows.append({
                "Name": name.strip(),
                "Rechnungs-Nr. DZR": rechnungs_nr.strip(),
                "Ihre Rechnungs-Nr.": ihre_nr.strip(),
                "Betrag": betrag.strip(),
                "Rechnungsempfängers": " ".join(rechnungsempf).strip()
            })
            i = j
        else:
            # More generic: flag if we skip ANY line that isn't matched as a main row
            skipped_any = True
            i += 1
    return rows, skipped_any
