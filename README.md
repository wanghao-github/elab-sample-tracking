# eLabFTW Sample Tracking Web App

A lightweight Flask-based web application for querying and summarizing eLabFTW items or experiments by Sample-ID, with optional summary generation and QR code support.

This repository also includes a utility script (elab_sync.py) for synchronizing data between two eLabFTW instances.

---

## Features

- Search eLabFTW items or experiments by Sample-ID  
- Optional full-text matching (title + body)  
- Extract structured metadata from extra_fields  
- Display results in a sortable table  
- Expandable body content and QR codes  
- Generate a summary entry in eLabFTW  
- Auto-fill and auto-submit via URL parameters  
- Optional data sync tool between servers  

---

## Core Logic

### Data Flow

User Input → Flask → eLabFTW API → Filter → Render → (Optional) Save Summary

### Query Process

1. User inputs:
   - Sample-ID  
   - API key  
   - Data type (items or experiments)  
   - Matching mode  

2. Backend:
   - Fetches data from eLabFTW API  
   - Extracts metadata (extra_fields)  
   - Matches:
     - default: Sample-ID prefix  
     - optional: full text (title + body)  

3. Output:
   - Table view  
   - Each row contains metadata, link, QR code, expandable body  

---

## Project Structure

elabftw_sample/
├── app.py  
├── elabftw_api.py  
├── elab_sync.py  
├── templates/  
│   ├── sample_id.html  
│   ├── result_table.html  
│   └── summary_body.html  

---

## Installation

### 1. Clone

git clone <repo-url>  
cd elabftw_sample  

### 2. Create environment

python -m venv venv  
source venv/bin/activate  

### 3. Install dependencies

pip install flask elabapi_python qrcode pillow beautifulsoup4  

---

## Running

python app.py  

Open:

http://localhost:5000  

---

## Deployment

Typical setup:

Nginx → Flask (port 5000)

---

## Configuration

Update these values:

- API host in app.py  
- base_url in app.py  
- domain in templates  
- API config in elabftw_api.py  

---

## Data Sync Tool

Set environment variables:

export ELAB_SOURCE_HOST="https://source/api/v2"  
export ELAB_SOURCE_API_KEY="SOURCE_KEY"  
export ELAB_TARGET_HOST="https://target/api/v2"  
export ELAB_TARGET_API_KEY="TARGET_KEY"  

Run:

python elab_sync.py  

---

## Notes

- Do not hardcode API keys  
- SSL verification is disabled by default  
- Designed for internal/research use  

