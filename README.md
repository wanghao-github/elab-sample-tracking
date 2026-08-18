# eLabFTW Sample Tracking

A lightweight Flask-based web application for tracking sample provenance and collaboration history in eLabFTW.

The application allows users to search eLabFTW items or experiments using either a Sample ID or a contributor name, reconstruct the chronological history of a sample, and visualize interactions between samples, contributors, experiments, instruments, and metadata through an interactive graph interface.

The repository also includes a synchronization utility (`elab_sync.py`) for transferring items and experiments between two eLabFTW instances.

---

## Features

### Sample Tracking

- Search eLabFTW records by:
  - Sample ID
  - Contributor name

- Supports:
  - Items
  - Experiments

- Optional:
  - Full-text matching
  - Summary generation inside eLabFTW

---

### Interactive Graph Visualization

The web interface generates an interactive graph similar to the Obsidian graph view.

#### Sample View

Displays:

- Sample nodes
- Contributors
- Experimental events
- Instruments
- Locations
- Composition metadata

Useful for reconstructing the lifecycle of a sample.

#### Contributor View

Displays:

- Contributors
- Associated samples
- Experimental records
- Measurements and instruments

Useful for exploring collaboration and sample exchange between groups.

---

### Chronological Timeline

Automatically reconstructs:

- Sample history
- Measurements
- Processing steps
- Contributor sequence

Each event contains:

- Timestamp
- Contributor
- Experiment type
- Metadata
- Direct link to eLabFTW

---

### Dynamic Metadata Table

The result table:

- Automatically detects all custom `extra_fields`
- Supports:
  - Column filtering
  - Search
  - Sorting
  - Expandable record body
  - QR codes

Default core fields:

- Sample Type
- Experiment Performed
- Sample Composition
- Instrument
- Location

---

### Summary Generation

Optionally generate a new eLabFTW item containing:

- Search result summary
- Chronological sample history
- Direct links to records

---

### QR Code Support

Each record includes a QR code pointing directly to the original eLabFTW entry.

---

## System Architecture

### Data Flow

```text
Browser
   ↓
Flask / Gunicorn
   ↓
eLabFTW REST API
   ↓
Metadata extraction + filtering
   ↓
Timeline + graph generation
   ↓
Interactive HTML rendering
```

---

## Project Structure

```text
elabftw_sample/
├── app.py
├── elabftw_api.py
├── elab_sync.py
├── templates/
│   ├── sample_id.html
│   ├── result_table.html
│   └── summary_body.html
└── README.md
```

---

## Installation

### 1. Clone Repository

```bash
git clone <repo-url>
cd elabftw_sample
```

### 2. Create Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -U pip wheel

pip install \
    flask \
    gunicorn \
    elabapi-python \
    qrcode \
    pillow \
    beautifulsoup4 \
    lxml
```

---

## Running Locally

### Development Mode

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

### Production Mode

Recommended deployment:

```text
Nginx → Gunicorn → Flask
```

Run Gunicorn manually:

```bash
gunicorn -w 2 -b 127.0.0.1:5000 app:app
```

---

## Deployment Example

### systemd Service

Example:

```ini
[Unit]
Description=Sample Tracking (Gunicorn)
After=network.target

[Service]
User=hao
WorkingDirectory=/home/hao/elabftw_sample
Environment="PATH=/home/hao/elabftw_sample/.venv/bin"

ExecStart=/home/hao/elabftw_sample/.venv/bin/gunicorn \
  --workers 2 \
  --bind 127.0.0.1:5000 \
  --timeout 120 \
  app:app

Restart=always

[Install]
WantedBy=multi-user.target
```

Useful commands:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sample-tracking
sudo systemctl restart sample-tracking
sudo systemctl status sample-tracking --no-pager
journalctl -u sample-tracking -f
```

---

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name flair.mw.tu-darmstadt.de;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:5000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Check and reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Configuration

Update the following values according to your eLabFTW deployment.

### In `app.py`

```python
ELAB_API_HOST = "https://your-server/api/v2"
ELAB_WEB_BASE = "https://your-server"
```

---

## Data Synchronization Utility

The repository includes `elab_sync.py` for synchronizing data between two eLabFTW instances.

### Environment Variables

```bash
export ELAB_SOURCE_HOST="https://source/api/v2"
export ELAB_SOURCE_API_KEY="SOURCE_KEY"

export ELAB_TARGET_HOST="https://target/api/v2"
export ELAB_TARGET_API_KEY="TARGET_KEY"
```

### Run Synchronization

Sync all:

```bash
python elab_sync.py
```

Sync only experiments:

```bash
python elab_sync.py --sync experiments
```

Sync only items:

```bash
python elab_sync.py --sync items
```

---

## Supported Metadata Extraction

The application supports:

- Standard eLabFTW metadata
- Nested `extra_fields`
- Grouped metadata structures
- SSL metadata templates
- User-defined custom fields

---

## Security Notes

- API keys should never be hardcoded.
- SSL verification is disabled by default for internal deployments.
- The Flask application should listen only on `127.0.0.1` when deployed behind Nginx.
- Designed primarily for internal laboratory and research environments.

---

## Intended Use Cases

- Sample provenance tracking
- Inter-group collaboration visualization
- Experimental workflow reconstruction
- FAIR data management support
- Laboratory information tracing
- Internal infrastructure demonstrations
- Research data management workflows

---

## Contributors

Powered by the FLAIR project.

Main contributors:

- Hao Wang
- Olaf Lindemann
- Hongbin Zhang

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
