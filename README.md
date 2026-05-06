# Roversa Streamlit Dashboard

This dashboard syncs Google Form submissions, downloads each uploaded CSV from Google Drive, enriches every CSV row with form metadata, stores data in SQLite, and provides Streamlit filters and charts for teacher, student, class/section, and robot-session analytics.

The goal is to move Roversa Robotics session data from scattered CSV uploads into a cleaner dashboard system where data can be filtered, inspected, and visualized.

---

## 1) Install

Create and activate a virtual environment.

### Mac/Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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
- **Program Divergence Sankey**: shows step-to-step command flow (`Step N -> Step N+1`) for valid Play/Test program runs, including END nodes for shorter programs.
- **Eagle-Eye Program Path Map**: simulates each Play/Test program as a top-down route from origin for visual comparison across students/runs.

## 7) New visual analytics details

### Program Divergence Sankey

- Uses the `Program` column as a whitespace-separated command list.
- Includes only rows where:
  - Button-derived run type is `Play` or `Test`.
  - Program is non-empty and not `Empty`.
- Builds flow counts between adjacent commands:
  - Example: `forward right forward` becomes:
    - `S1: forward -> S2: right`
    - `S2: right -> S3: forward`
    - and final `S3: forward -> S4: END`
- Honors all sidebar filters (teacher, class/section, student, date range).

### Eagle-Eye Program Path Map

- Simulates intended movement from each valid Play/Test `Program`.
- Each run starts at `(0, 0)` with heading East.
- Movement assumptions:
  - `forward` = move one unit in current heading
  - `reverse`/`backward` = move one unit backward relative to heading
  - `left` = rotate 90° left
  - `right` = rotate 90° right
- Plots one line per student/program run.
- Shows final coordinates and allows selecting a coordinate to inspect matching students/runs.
- This is simulated command intent, **not** physical robot trajectory.

## 8) Testing with fake data for new visuals

1. Generate local fake SQLite data:

```bash
python create_fake_data.py
```

2. Run dashboard:

```bash
streamlit run app.py
```

3. Verify visuals:
   - Filter to `Ms. Smith` + `Period 1` to see shared prefixes and divergence from `forward`.
   - Check overlap in final coordinates using the coordinate selector under Eagle-Eye map.
   - Confirm friendly info messages appear when filters remove valid Play/Test programs.

## 9) Limitations

- Path map is discrete-grid simulation and depends on command vocabulary in `Program`.
- Unknown commands are currently ignored for movement but retained as steps.
- Heading/axis convention can be adjusted in code if Roversa’s canonical orientation differs.
- Sankey operates at command-token level; it does not infer intent beyond sequence transitions.
