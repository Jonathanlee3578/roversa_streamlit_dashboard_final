import json
import pandas as pd
import streamlit as st

from db_utils import init_db, read_submissions, read_session_rows
from sync_google_form import sync_new_responses

st.set_page_config(page_title="Roversa Dashboard", layout="wide")


@st.cache_data
def load_submissions():
    return read_submissions()


@st.cache_data
def load_session_data():
    df = read_session_rows()

    if not df.empty and "row_json" in df.columns:
        expanded = df["row_json"].apply(json.loads).apply(pd.Series)
        df = pd.concat([df.drop(columns=["row_json"]), expanded], axis=1)

    return df


init_db()

st.title("Roversa Robotics Dashboard")

if st.button("Sync New Responses"):
    result = sync_new_responses()
    st.cache_data.clear()
    st.success(
        f"Added {result['new_submissions']} new submissions, "
        f"{result['new_rows']} new session rows, and "
        f"saved {result['saved_csvs']} processed CSV files."
    )

submissions_df = load_submissions()
session_df = load_session_data()

if submissions_df.empty:
    st.info("No data yet. Click 'Sync New Responses' to load Google Form data.")
    st.stop()

st.sidebar.header("Filters")

teacher_options = sorted(submissions_df["teacher_name"].dropna().unique().tolist())
student_options = sorted(submissions_df["student_id"].dropna().unique().tolist())
class_options = sorted(submissions_df["class_section"].dropna().unique().tolist())

selected_teachers = st.sidebar.multiselect("Teacher", teacher_options)
selected_students = st.sidebar.multiselect("Student", student_options)
selected_classes = st.sidebar.multiselect("Class/Section", class_options)

filtered_submissions = submissions_df.copy()
filtered_sessions = session_df.copy()

if selected_teachers:
    filtered_submissions = filtered_submissions[
        filtered_submissions["teacher_name"].isin(selected_teachers)
    ]
    filtered_sessions = filtered_sessions[
        filtered_sessions["teacher_name"].isin(selected_teachers)
    ]

if selected_students:
    filtered_submissions = filtered_submissions[
        filtered_submissions["student_id"].isin(selected_students)
    ]
    filtered_sessions = filtered_sessions[
        filtered_sessions["student_id"].isin(selected_students)
    ]

if selected_classes:
    filtered_submissions = filtered_submissions[
        filtered_submissions["class_section"].isin(selected_classes)
    ]
    filtered_sessions = filtered_sessions[
        filtered_sessions["class_section"].isin(selected_classes)
    ]

c1, c2, c3 = st.columns(3)
c1.metric("Teachers", filtered_submissions["teacher_name"].nunique())
c2.metric("Students", filtered_submissions["student_id"].nunique())
c3.metric("Submissions", len(filtered_submissions))

st.subheader("Submissions by Teacher")
teacher_counts = (
    filtered_submissions.groupby("teacher_name")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)
if not teacher_counts.empty:
    st.bar_chart(teacher_counts.set_index("teacher_name"))

st.subheader("Unique Students by Teacher")
student_counts = (
    filtered_submissions.groupby("teacher_name")["student_id"]
    .nunique()
    .reset_index(name="student_count")
    .sort_values("student_count", ascending=False)
)
if not student_counts.empty:
    st.bar_chart(student_counts.set_index("teacher_name"))

st.subheader("Filtered Session Data")
st.dataframe(filtered_sessions, use_container_width=True, height=500)
