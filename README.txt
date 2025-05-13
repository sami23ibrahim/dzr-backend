PDF Invoice Extractor - Project Overview
========================================

This project is a full-stack web application for extracting structured invoice data from PDF files using AI. It consists of a Python Flask backend and a React frontend.

What does it do?
----------------
- Lets users upload one or more invoice PDFs via a web interface.
- Extracts the relevant invoice data (including patient name, recipient, invoice numbers, amount, and billing date) from each PDF.
- Uses an AI model to parse complex table data from the PDFs.
- Displays all extracted data in a clean, searchable table in the browser.

How does it work?
-----------------

1. **Frontend (React - `invoice-viewer/`)**
   - Provides a web page where users can select and upload PDF files.
   - Sends the selected files to the backend via a POST request.
   - Receives the extracted data as JSON and displays it in a table.

2. **Backend (Flask - `backend.py`)**
   - Receives uploaded PDF files at the `/api/upload` endpoint.
   - For each PDF:
     - Extracts the text between 'Ab- und Zusetzungen' and 'Summe Ab- und Zusetzungen' (the invoice table).
     - Extracts the billing date from the top of the first page (e.g., after 'Abrechnungsdatum').
     - Sends the table block to an AI API (OpenRouter) to parse the rows into structured data.
     - Adds the billing date to each extracted row.
   - Returns all extracted rows as a JSON array to the frontend.

3. **AI Integration**
   - The backend uses the OpenRouter API to parse complex table data from the PDF text, making extraction robust even for tricky layouts.

Typical User Flow
-----------------
1. User opens the web app in their browser.
2. User uploads one or more PDF invoices.
3. The backend processes each PDF, extracts and parses the data, and sends it back.
4. The frontend displays all extracted invoice data in a table, including the billing date for each row.

Deployment
----------
- The app is designed to run locally for development.
- For production, the React frontend can be deployed to Vercel or similar, and the Flask backend to Render, Railway, or any Python-friendly host.

Files and Folders
-----------------
- `backend.py`         : Flask backend API for PDF upload and extraction
- `requirements.txt`   : Python dependencies for the backend
- `invoice-viewer/`    : React frontend app (user interface)

Contact
-------
For questions or contributions, see: https://github.com/sami23ibrahim/pdf-sorter.git 