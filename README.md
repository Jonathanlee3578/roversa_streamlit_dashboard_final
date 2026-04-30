## Local Testing Resources

This repo includes local testing files:

- `testing/create_fake_data.py` creates a fake local SQLite database for testing dashboard visuals without Google authentication.
- `testing/test_form_csv_load.py` checks whether an exported Google Form response CSV can be read successfully.
- `test_data/form_responses_test.csv` is an anonymized sample form response export used for testing column names and data loading.

Do not commit real student data, Google credentials, `roversa.db`, or files inside `processed_csvs/`.

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
