# Roversa Streamlit Dashboard

This dashboard syncs Google Form submissions, downloads each uploaded CSV from Google Drive, enriches every CSV row with form metadata, stores data in SQLite, and provides Streamlit filters for teacher, student, and class/section.

## 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Configure secrets

Create `.streamlit/secrets.toml` (do **not** commit it):

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"

[google_form]
sheet_name = "<exact Google Sheet name>"
```

Also share the response sheet and uploaded files with the service account email.

## 3) Run app

```bash
streamlit run app.py
```

## 4) Workflow

1. Click **Sync New Responses**.
2. New form submissions are deduplicated by `submission_key`.
3. Each uploaded CSV is downloaded and enriched.
4. Enriched copies are saved under `processed_csvs/`.
5. Data is stored in `roversa.db` (`submissions` and `session_rows`).
6. Use sidebar filters for teacher, student, and class/section.

## 5) Quick verification

- Run Sync twice with no new form entries.
- The second run should report `0 new submissions`, `0 new rows`, and `0 processed CSVs`.

## 6) Robot analytics fields in the dashboard

The filtered session table and charts include these derived fields:

- `is_new_session`: `True` when `Session == "NEW"`.
- `session_number`: cumulative count of NEW rows within each `submission_key`.
- `program_length`: number of commands in `Program` (blank/NaN/`Empty` = `0`).
- `run_type`: derived from `Button` (`Play`, `Test`, or `Other`).

Additional analytics shown in Streamlit:

- **Empty Program Runs**: count of Play/Test rows where `program_length == 0`.
- **Time Spent per Session**: calculated as `max(Time (seconds)) - min(Time (seconds))` within each session.
