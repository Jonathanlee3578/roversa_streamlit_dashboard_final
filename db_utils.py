import sqlite3
import pandas as pd

DB_PATH = "roversa.db"


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            submission_key TEXT PRIMARY KEY,
            form_timestamp TEXT,
            teacher_name TEXT,
            teacher_email TEXT,
            school TEXT,
            class_section TEXT,
            session_date TEXT,
            student_id TEXT,
            first_recorded_session TEXT,
            grade_level TEXT,
            age TEXT,
            gender TEXT,
            original_file_link TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_key TEXT,
            source_row_number INTEGER,
            teacher_name TEXT,
            teacher_email TEXT,
            school TEXT,
            class_section TEXT,
            student_id TEXT,
            session_date TEXT,
            first_recorded_session TEXT,
            grade_level TEXT,
            age TEXT,
            gender TEXT,
            form_timestamp TEXT,
            original_file_link TEXT,
            row_json TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_existing_submission_keys():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT submission_key FROM submissions")
    rows = cur.fetchall()
    conn.close()
    return {row[0] for row in rows}


def insert_submission(metadata: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO submissions (
            submission_key, form_timestamp, teacher_name, teacher_email,
            school, class_section, session_date, student_id,
            first_recorded_session, grade_level, age, gender, original_file_link
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        metadata["submission_key"],
        metadata["form_timestamp"],
        metadata["teacher_name"],
        metadata["teacher_email"],
        metadata["school"],
        metadata["class_section"],
        metadata["session_date"],
        metadata["student_id"],
        metadata["first_recorded_session"],
        metadata["grade_level"],
        metadata["age"],
        metadata["gender"],
        metadata["original_file_link"],
    ))

    conn.commit()
    conn.close()


def insert_session_rows(df: pd.DataFrame, metadata: dict):
    conn = get_connection()
    cur = conn.cursor()

    for idx, row in df.iterrows():
        cur.execute("""
            INSERT INTO session_rows (
                submission_key, source_row_number, teacher_name, teacher_email,
                school, class_section, student_id, session_date,
                first_recorded_session, grade_level, age, gender,
                form_timestamp, original_file_link, row_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata["submission_key"],
            idx,
            metadata["teacher_name"],
            metadata["teacher_email"],
            metadata["school"],
            metadata["class_section"],
            metadata["student_id"],
            metadata["session_date"],
            metadata["first_recorded_session"],
            metadata["grade_level"],
            metadata["age"],
            metadata["gender"],
            metadata["form_timestamp"],
            metadata["original_file_link"],
            row.to_json(),
        ))

    conn.commit()
    conn.close()


def read_submissions():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM submissions", conn)
    conn.close()
    return df


def read_session_rows():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM session_rows", conn)
    conn.close()
    return df
