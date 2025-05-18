from backend import extract_relevant_block
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python print_block.py <yourfile.pdf>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    block = extract_relevant_block(pdf_path)
    if block:
        print("\n--- BLOCK TO SEND TO AI ---\n")
        print(block)
        print("\n--- END BLOCK ---\n")
    else:
        print("No relevant block found in the PDF.")

        #   python print_block.py yourfile.pdf