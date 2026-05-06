import os
import sqlite3
import pandas as pd

DB_PATH = "roversa.db"


def reset_database():
    """Delete old local test database so each test starts fresh."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def create_tables(conn):
    """Create the same tables used by the Streamlit app."""
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
            original_file_link TEXT,
            processed_csv_path TEXT
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


def insert_submission(conn, metadata):
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO submissions (
            submission_key, form_timestamp, teacher_name, teacher_email,
            school, class_section, session_date, student_id,
            first_recorded_session, grade_level, age, gender,
            original_file_link, processed_csv_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        metadata["processed_csv_path"],
    ))

    conn.commit()


def insert_session_rows(conn, metadata, session_df):
    cur = conn.cursor()

    for idx, row in session_df.iterrows():
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


def make_session(rows):
    """
    Turn a list of row dictionaries into a robot CSV-style dataframe.
    Missing columns are filled so the fake data matches the real file shape.
    """
    df = pd.DataFrame(rows)

    required_cols = [
        "Time (seconds)",
        "Session",
        "Button",
        "Program",
        "LeftComp",
        "RightComp",
        "DriveTime",
        "TurnTime",
        "Language",
        "Battery",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df["LeftComp"] = df["LeftComp"].replace("", 0)
    df["RightComp"] = df["RightComp"].replace("", 0)
    df["DriveTime"] = df["DriveTime"].replace("", 1250)
    df["TurnTime"] = df["TurnTime"].replace("", 670)
    df["Language"] = df["Language"].replace("", 1)
    df["Battery"] = df["Battery"].replace("", 4.25)

    return df[required_cols]


def main():
    reset_database()

    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    fake_submissions = [
        {
            "submission_key": "fake_submission_001",
            "form_timestamp": "2026-04-30 09:00:00",
            "teacher_name": "Ms. Smith",
            "teacher_email": "smith@example.com",
            "school": "Roversa Test School",
            "class_section": "Period 1",
            "session_date": "2026-04-30",
            "student_id": "S001",
            "first_recorded_session": "Yes",
            "grade_level": "5",
            "age": "10",
            "gender": "Prefer not to say",
            "original_file_link": "fake_link_001",
            "processed_csv_path": "processed_csvs/fake_submission_001.csv",
        },
        {
            "submission_key": "fake_submission_002",
            "form_timestamp": "2026-04-30 09:30:00",
            "teacher_name": "Ms. Smith",
            "teacher_email": "smith@example.com",
            "school": "Roversa Test School",
            "class_section": "Period 1",
            "session_date": "2026-04-30",
            "student_id": "S002",
            "first_recorded_session": "Yes",
            "grade_level": "5",
            "age": "11",
            "gender": "Prefer not to say",
            "original_file_link": "fake_link_002",
            "processed_csv_path": "processed_csvs/fake_submission_002.csv",
        },
        {
            "submission_key": "fake_submission_003",
            "form_timestamp": "2026-04-30 10:00:00",
            "teacher_name": "Mr. Johnson",
            "teacher_email": "johnson@example.com",
            "school": "Roversa Test School",
            "class_section": "Period 2",
            "session_date": "2026-04-30",
            "student_id": "S003",
            "first_recorded_session": "No",
            "grade_level": "6",
            "age": "12",
            "gender": "Prefer not to say",
            "original_file_link": "fake_link_003",
            "processed_csv_path": "processed_csvs/fake_submission_003.csv",
        },
        {
            "submission_key": "fake_submission_004",
            "form_timestamp": "2026-04-30 10:30:00",
            "teacher_name": "Mr. Johnson",
            "teacher_email": "johnson@example.com",
            "school": "Roversa Test School",
            "class_section": "Period 2",
            "session_date": "2026-04-30",
            "student_id": "S004",
            "first_recorded_session": "Yes",
            "grade_level": "6",
            "age": "12",
            "gender": "Prefer not to say",
            "original_file_link": "fake_link_004",
            "processed_csv_path": "processed_csvs/fake_submission_004.csv",
        },
        {
            "submission_key": "fake_submission_005",
            "form_timestamp": "2026-04-30 11:00:00",
            "teacher_name": "Dr. Lee",
            "teacher_email": "lee@example.com",
            "school": "Roversa Test School",
            "class_section": "After School Club",
            "session_date": "2026-04-30",
            "student_id": "S005",
            "first_recorded_session": "No",
            "grade_level": "7",
            "age": "13",
            "gender": "Prefer not to say",
            "original_file_link": "fake_link_005",
            "processed_csv_path": "processed_csvs/fake_submission_005.csv",
        },
    ]

    fake_sessions = {
        "fake_submission_001": make_session([
            {"Time (seconds)": 0, "Session": "NEW", "Battery": 4.30},
            {"Time (seconds)": 5, "Button": "Forward"},
            {"Time (seconds)": 10, "Button": "Play", "Program": "forward right forward"},
            {"Time (seconds)": 18, "Button": "Left"},
            {"Time (seconds)": 22, "Button": "Test", "Program": "forward left forward"},
            {"Time (seconds)": 35, "Session": "NEW", "Battery": 4.24},
            {"Time (seconds)": 40, "Button": "Forward"},
            {"Time (seconds)": 45, "Button": "Right"},
            {"Time (seconds)": 52, "Button": "Play", "Program": "forward right reverse"},
            {"Time (seconds)": 60, "Button": "Test", "Program": "Empty"},
        ]),
        "fake_submission_002": make_session([
            {"Time (seconds)": 0, "Session": "NEW", "Battery": 4.28},
            {"Time (seconds)": 4, "Button": "Forward"},
            {"Time (seconds)": 8, "Button": "Forward"},
            {"Time (seconds)": 12, "Button": "Right"},
            {"Time (seconds)": 20, "Button": "Play", "Program": "forward forward right forward"},
            {"Time (seconds)": 32, "Button": "Clear"},
            {"Time (seconds)": 45, "Button": "Forward"},
            {"Time (seconds)": 50, "Button": "Forward"},
            {"Time (seconds)": 60, "Button": "Left"},
            {"Time (seconds)": 70, "Button": "Play", "Program": "forward forward left reverse"},
            {"Time (seconds)": 95, "Button": "Test", "Program": "forward left right reverse"},
        ]),
        "fake_submission_003": make_session([
            {"Time (seconds)": 0, "Session": "NEW", "Battery": 4.25},
            {"Time (seconds)": 6, "Button": "Play", "Program": "Empty"},
            {"Time (seconds)": 12, "Button": "Right"},
            {"Time (seconds)": 20, "Button": "Play", "Program": "right"},
            {"Time (seconds)": 30, "Session": "NEW", "Battery": 4.22},
            {"Time (seconds)": 38, "Button": "Forward"},
            {"Time (seconds)": 46, "Button": "Left"},
            {"Time (seconds)": 54, "Button": "Forward"},
            {"Time (seconds)": 65, "Button": "Play", "Program": "forward left forward"},
            {"Time (seconds)": 80, "Session": "NEW", "Battery": 4.20},
            {"Time (seconds)": 86, "Button": "Reverse"},
            {"Time (seconds)": 92, "Button": "Right"},
            {"Time (seconds)": 100, "Button": "Play", "Program": "reverse right"},
            {"Time (seconds)": 114, "Button": "Test", "Program": "reverse right forward"},
        ]),
        "fake_submission_004": make_session([
            {"Time (seconds)": 0, "Session": "NEW", "Battery": 4.35},
            {"Time (seconds)": 10, "Button": "Forward"},
            {"Time (seconds)": 20, "Button": "Forward"},
            {"Time (seconds)": 30, "Button": "Forward"},
            {"Time (seconds)": 40, "Button": "Forward"},
            {"Time (seconds)": 50, "Button": "Left"},
            {"Time (seconds)": 75, "Button": "Play", "Program": "forward forward forward forward left"},
            {"Time (seconds)": 100, "Session": "NEW", "Battery": 4.31},
            {"Time (seconds)": 110, "Button": "Forward"},
            {"Time (seconds)": 120, "Button": "Forward"},
            {"Time (seconds)": 130, "Button": "Left"},
            {"Time (seconds)": 140, "Button": "Forward"},
            {"Time (seconds)": 150, "Button": "Forward"},
            {"Time (seconds)": 160, "Button": "Left"},
            {"Time (seconds)": 185, "Button": "Play", "Program": "forward forward left forward forward left"},
            {"Time (seconds)": 210, "Button": "Test", "Program": "forward forward left forward forward left"},
            {"Time (seconds)": 230, "Session": "NEW", "Battery": 4.29},
            {"Time (seconds)": 238, "Button": "Play", "Program": "forward right forward left"},
            {"Time (seconds)": 248, "Button": "Test", "Program": "forward right forward right"},
        ]),
        "fake_submission_005": make_session([
            {"Time (seconds)": 0, "Session": "NEW", "Battery": 4.18},
            {"Time (seconds)": 15, "Button": "Forward"},
            {"Time (seconds)": 30, "Button": "Left"},
            {"Time (seconds)": 45, "Button": "Right"},
            {"Time (seconds)": 60, "Button": "Reverse"},
            {"Time (seconds)": 90, "Button": "Play", "Program": "forward left right reverse"},
            {"Time (seconds)": 140, "Session": "NEW", "Battery": 4.12},
            {"Time (seconds)": 155, "Button": "Forward"},
            {"Time (seconds)": 170, "Button": "Forward"},
            {"Time (seconds)": 185, "Button": "Forward"},
            {"Time (seconds)": 200, "Button": "Left"},
            {"Time (seconds)": 215, "Button": "Forward"},
            {"Time (seconds)": 230, "Button": "Right"},
            {"Time (seconds)": 260, "Button": "Play", "Program": "forward forward forward left forward right"},
            {"Time (seconds)": 290, "Button": "Test", "Program": "forward forward forward left forward right"},
            {"Time (seconds)": 330, "Session": "NEW", "Battery": 4.05},
            {"Time (seconds)": 340, "Button": "Play", "Program": "Empty"},
            {"Time (seconds)": 355, "Button": "Clear"},
            {"Time (seconds)": 370, "Button": "Forward"},
            {"Time (seconds)": 385, "Button": "Play", "Program": "forward"},
        ]),
    }

    for metadata in fake_submissions:
        insert_submission(conn, metadata)
        insert_session_rows(conn, metadata, fake_sessions[metadata["submission_key"]])

    conn.close()

    print("Larger fake Roversa database created successfully.")
    print("Created 5 submissions across 3 teachers.")
    print("Now run: python -m streamlit run app.py")


if __name__ == "__main__":
    main()
