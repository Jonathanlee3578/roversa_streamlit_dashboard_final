import io
import os
import re
from pathlib import Path

import pandas as pd
import requests
import gspread
import streamlit as st

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

from db_utils import (
    init_db,
    get_existing_submission_keys,
    insert_submission,
    insert_session_rows,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

COL_MAP = {
    "timestamp": "Timestamp",
    "teacher_name": "Teacher Name:",
    "teacher_email": "Teacher Email:",
    "school": "School/Organization",
    "class_section": "Class/section",
    "session_date": "Date of session",
    "student_id": "Student ID",
    "first_session": "Is this the Student's first recorded session",
    "grade_level": "Grade level of student",
    "age": "Age",
    "gender": "Gender",
    "file_upload": "Upload Session CSV file",
}

PROCESSED_CSV_DIR = Path("processed_csvs")
PROCESSED_CSV_DIR.mkdir(exist_ok=True)


def get_credentials():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def get_gspread_client():
    creds = get_credentials()
    return gspread.authorize(creds)


def load_form_responses():
    gc = get_gspread_client()
    sheet_name = st.secrets["google_form"]["sheet_name"]
    spreadsheet = gc.open(sheet_name)
    worksheet = spreadsheet.sheet1
    records = worksheet.get_all_records()
    return pd.DataFrame(records)


def make_submission_key(row):
    return (
        f"{row.get(COL_MAP['timestamp'], '')}|"
        f"{row.get(COL_MAP['student_id'], '')}|"
        f"{row.get(COL_MAP['session_date'], '')}"
    )


def clean_filename(text):
    text = str(text).strip()
    text = re.sub(r"[^\w\-]+", "_", text)
    return text


def parse_google_file_id(file_url):
    if not file_url:
        return None

    first_part = str(file_url).split(",")[0].strip()

    patterns = [
        r"id=([a-zA-Z0-9_-]+)",
        r"/d/([a-zA-Z0-9_-]+)",
        r"/file/d/([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, first_part)
        if match:
            return match.group(1)

    return None


def download_drive_csv(file_id, access_token):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    raw_bytes = io.BytesIO(response.content)

    try:
        return pd.read_csv(raw_bytes)
    except Exception:
        raw_bytes.seek(0)
        return pd.read_csv(raw_bytes, encoding="latin1")


def build_processed_csv_name(student_id, session_date, submission_key):
    student_id_clean = clean_filename(student_id)
    session_date_clean = clean_filename(session_date)
    key_suffix = clean_filename(submission_key)[-20:]
    return f"{student_id_clean}_{session_date_clean}_{key_suffix}.csv"


def sync_new_responses():
    init_db()

    responses_df = load_form_responses()
    if responses_df.empty:
        return {"new_submissions": 0, "new_rows": 0, "saved_csvs": 0}

    existing_keys = get_existing_submission_keys()
    creds = get_credentials()
    access_token = creds.token

    new_submissions = 0
    new_rows = 0
    saved_csvs = 0

    for _, row in responses_df.iterrows():
        submission_key = make_submission_key(row)

        if submission_key in existing_keys:
            continue

        file_url = row.get(COL_MAP["file_upload"], "")
        file_id = parse_google_file_id(file_url)

        if not file_id:
            continue

        session_df = download_drive_csv(file_id, access_token)

        # Add metadata columns directly to the dataframe
        session_df["teacher_name"] = str(row.get(COL_MAP["teacher_name"], ""))
        session_df["teacher_email"] = str(row.get(COL_MAP["teacher_email"], ""))
        session_df["school"] = str(row.get(COL_MAP["school"], ""))
        session_df["class_section"] = str(row.get(COL_MAP["class_section"], ""))
        session_df["student_id"] = str(row.get(COL_MAP["student_id"], ""))
        session_df["session_date"] = str(row.get(COL_MAP["session_date"], ""))
        session_df["first_recorded_session"] = str(row.get(COL_MAP["first_session"], ""))
        session_df["grade_level"] = str(row.get(COL_MAP["grade_level"], ""))
        session_df["age"] = str(row.get(COL_MAP["age"], ""))
        session_df["gender"] = str(row.get(COL_MAP["gender"], ""))
        session_df["form_timestamp"] = str(row.get(COL_MAP["timestamp"], ""))
        session_df["original_file_link"] = str(file_url)
        session_df["submission_key"] = submission_key

        processed_filename = build_processed_csv_name(
            student_id=row.get(COL_MAP["student_id"], ""),
            session_date=row.get(COL_MAP["session_date"], ""),
            submission_key=submission_key,
        )
        processed_csv_path = PROCESSED_CSV_DIR / processed_filename

        session_df.to_csv(processed_csv_path, index=False)

        metadata = {
            "submission_key": submission_key,
            "form_timestamp": str(row.get(COL_MAP["timestamp"], "")),
            "teacher_name": str(row.get(COL_MAP["teacher_name"], "")),
            "teacher_email": str(row.get(COL_MAP["teacher_email"], "")),
            "school": str(row.get(COL_MAP["school"], "")),
            "class_section": str(row.get(COL_MAP["class_section"], "")),
            "session_date": str(row.get(COL_MAP["session_date"], "")),
            "student_id": str(row.get(COL_MAP["student_id"], "")),
            "first_recorded_session": str(row.get(COL_MAP["first_session"], "")),
            "grade_level": str(row.get(COL_MAP["grade_level"], "")),
            "age": str(row.get(COL_MAP["age"], "")),
            "gender": str(row.get(COL_MAP["gender"], "")),
            "original_file_link": str(file_url),
            "processed_csv_path": str(processed_csv_path),
        }

        insert_submission(metadata)
        insert_session_rows(session_df, metadata)

        new_submissions += 1
        new_rows += len(session_df)
        saved_csvs += 1

    return {
        "new_submissions": new_submissions,
        "new_rows": new_rows,
        "saved_csvs": saved_csvs,
    }
