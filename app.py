import json

import pandas as pd
import streamlit as st

from analytics_utils import add_robot_analytics_fields
from db_utils import init_db, read_session_rows, read_submissions
from sync_google_form import sync_new_responses

st.set_page_config(page_title="Roversa Dashboard", layout="wide")


@st.cache_data
def load_submissions():
    return read_submissions()


@st.cache_data
def load_session_data():
    """Load expanded session rows for filtering and display in Streamlit."""
    df = read_session_rows()
    if not df.empty and "row_json" in df.columns:
        expanded = df["row_json"].apply(json.loads).apply(pd.Series)
        df = pd.concat([df.drop(columns=["row_json"]), expanded], axis=1)
    return df


def _short_submission_label(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    return s.apply(lambda x: x if len(x) <= 28 else f"{x[:12]}...{x[-12:]}")


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

if st.sidebar.button("Clear filters"):
    for key in ["filter_teachers", "filter_classes", "filter_students", "filter_date_range"]:
        if key in st.session_state:
            del st.session_state[key]

# Cascading option source is submissions_df, progressively narrowed.
working_options_df = submissions_df.copy()

teacher_options = (
    sorted(working_options_df["teacher_name"].dropna().astype(str).unique().tolist())
    if "teacher_name" in working_options_df.columns
    else []
)
selected_teachers = st.sidebar.multiselect("Teacher", teacher_options, key="filter_teachers")
if selected_teachers and "teacher_name" in working_options_df.columns:
    working_options_df = working_options_df[working_options_df["teacher_name"].astype(str).isin(selected_teachers)]

class_options = (
    sorted(working_options_df["class_section"].dropna().astype(str).unique().tolist())
    if "class_section" in working_options_df.columns
    else []
)
selected_classes = st.sidebar.multiselect("Class/Section", class_options, key="filter_classes")
if selected_classes and "class_section" in working_options_df.columns:
    working_options_df = working_options_df[working_options_df["class_section"].astype(str).isin(selected_classes)]

student_options = (
    sorted(working_options_df["student_id"].dropna().astype(str).unique().tolist())
    if "student_id" in working_options_df.columns
    else []
)
selected_students = st.sidebar.multiselect("Student", student_options, key="filter_students")

# Optional date-range filter, only if session_date can be parsed.
selected_date_range = None
session_dates = None
if "session_date" in submissions_df.columns:
    parsed_dates = pd.to_datetime(submissions_df["session_date"], errors="coerce")
    if parsed_dates.notna().any():
        min_date = parsed_dates.min().date()
        max_date = parsed_dates.max().date()
        selected_date_range = st.sidebar.date_input(
            "Session Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="filter_date_range",
        )
        session_dates = parsed_dates.dt.date

# Apply final selected filters to both submissions and session rows.
filtered_submissions = submissions_df.copy()
filtered_sessions = session_df.copy()

if selected_teachers:
    if "teacher_name" in filtered_submissions.columns:
        filtered_submissions = filtered_submissions[filtered_submissions["teacher_name"].astype(str).isin(selected_teachers)]
    if "teacher_name" in filtered_sessions.columns:
        filtered_sessions = filtered_sessions[filtered_sessions["teacher_name"].astype(str).isin(selected_teachers)]

if selected_classes:
    if "class_section" in filtered_submissions.columns:
        filtered_submissions = filtered_submissions[filtered_submissions["class_section"].astype(str).isin(selected_classes)]
    if "class_section" in filtered_sessions.columns:
        filtered_sessions = filtered_sessions[filtered_sessions["class_section"].astype(str).isin(selected_classes)]

if selected_students:
    if "student_id" in filtered_submissions.columns:
        filtered_submissions = filtered_submissions[filtered_submissions["student_id"].astype(str).isin(selected_students)]
    if "student_id" in filtered_sessions.columns:
        filtered_sessions = filtered_sessions[filtered_sessions["student_id"].astype(str).isin(selected_students)]

if selected_date_range and session_dates is not None:
    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        if "session_date" in filtered_submissions.columns:
            filtered_submissions_dates = pd.to_datetime(filtered_submissions["session_date"], errors="coerce").dt.date
            filtered_submissions = filtered_submissions[
                filtered_submissions_dates.between(start_date, end_date, inclusive="both")
            ]
        if "session_date" in filtered_sessions.columns:
            filtered_sessions_dates = pd.to_datetime(filtered_sessions["session_date"], errors="coerce").dt.date
            filtered_sessions = filtered_sessions[
                filtered_sessions_dates.between(start_date, end_date, inclusive="both")
            ]

st.sidebar.markdown("---")
st.sidebar.caption("Selection summary")
st.sidebar.write(f"Teachers selected: {len(selected_teachers)}")
st.sidebar.write(f"Classes selected: {len(selected_classes)}")
st.sidebar.write(f"Students selected: {len(selected_students)}")
st.sidebar.write(f"Filtered submissions: {len(filtered_submissions)}")

# Analytics fields are derived on a copy to avoid mutating cached source data.
analytics_df = add_robot_analytics_fields(filtered_sessions)

c1, c2, c3 = st.columns(3)
c1.metric("Teachers", filtered_submissions["teacher_name"].nunique() if "teacher_name" in filtered_submissions.columns else 0)
c2.metric("Students", filtered_submissions["student_id"].nunique() if "student_id" in filtered_submissions.columns else 0)
c3.metric("Submissions", len(filtered_submissions))

st.subheader("Submissions by Teacher")
if not filtered_submissions.empty and "teacher_name" in filtered_submissions.columns:
    teacher_counts = (
        filtered_submissions.groupby("teacher_name").size().reset_index(name="count").sort_values("count", ascending=False)
    )
    st.bar_chart(teacher_counts.set_index("teacher_name"))

st.subheader("Unique Students by Teacher")
if not filtered_submissions.empty and {"teacher_name", "student_id"}.issubset(filtered_submissions.columns):
    student_counts = (
        filtered_submissions.groupby("teacher_name")["student_id"]
        .nunique()
        .reset_index(name="student_count")
        .sort_values("student_count", ascending=False)
    )
    st.bar_chart(student_counts.set_index("teacher_name"))

st.subheader("Sessions per Uploaded File")
if not analytics_df.empty and {"submission_key", "is_new_session"}.issubset(analytics_df.columns):
    session_counts = (
        analytics_df.groupby("submission_key", dropna=False)["is_new_session"]
        .sum()
        .reset_index(name="session_count")
    )
    session_counts["submission_label"] = _short_submission_label(session_counts["submission_key"])
    st.bar_chart(session_counts.set_index("submission_label")[["session_count"]])
else:
    st.info("No session markers available yet.")

st.subheader("Program Length Across Sessions")
st.caption("Program length is command sequence length, not a measure of student skill.")
st.caption("Only sessions with Play or Test runs are shown. Sessions with no program run are excluded.")
if not analytics_df.empty and {"run_type", "program_length"}.issubset(analytics_df.columns):
    program_trend = analytics_df[analytics_df["run_type"].isin(["Play", "Test"])].copy()
    if not program_trend.empty:
        if "session_number" in program_trend.columns:
            program_trend["session_number"] = pd.to_numeric(program_trend["session_number"], errors="coerce")
            program_trend = program_trend.dropna(subset=["session_number"])
            program_trend["session_number"] = program_trend["session_number"].astype(int)
        else:
            program_trend["session_number"] = 1

        if "submission_key" not in program_trend.columns:
            program_trend["submission_key"] = "filtered_data"
        program_trend["submission_key"] = program_trend["submission_key"].fillna("filtered_data").astype(str)

        if not program_trend.empty:
            program_trend = (
                program_trend.groupby(["submission_key", "session_number"], dropna=False)["program_length"]
                .max()
                .reset_index()
                .sort_values(["submission_key", "session_number"])
            )
            program_trend["submission_label"] = _short_submission_label(program_trend["submission_key"])
            program_trend["display_label"] = (
                program_trend["submission_label"] + " - Session " + program_trend["session_number"].astype(str)
            )
            st.line_chart(program_trend.set_index("display_label")[["program_length"]])
        else:
            st.info("No valid session numbers found for Play/Test runs.")
    else:
        st.info("No Play/Test runs found for current filters.")

st.subheader("Button Press Breakdown")
if not analytics_df.empty and "Button" in analytics_df.columns:
    button_series = analytics_df["Button"].fillna("").astype(str).str.strip()
    button_counts = button_series[button_series != ""].value_counts().rename_axis("Button").reset_index(name="count")
    if not button_counts.empty:
        st.bar_chart(button_counts.set_index("Button")[['count']])
    else:
        st.info("No button press data found for current filters.")

st.subheader("Empty Program Runs")
if not analytics_df.empty and {"run_type", "program_length", "session_number"}.issubset(analytics_df.columns):
    empty_runs = analytics_df[(analytics_df["run_type"].isin(["Play", "Test"])) & (analytics_df["program_length"] == 0)]
    st.metric("Empty Program Runs", int(len(empty_runs)))

st.subheader("Time Spent per Session")
if not analytics_df.empty and "Time (seconds)" in analytics_df.columns:
    time_df = analytics_df.copy()
    time_df["time_seconds_num"] = pd.to_numeric(time_df["Time (seconds)"], errors="coerce")
    time_df = time_df.dropna(subset=["time_seconds_num"])
    group_cols = ["session_number"]
    if "submission_key" in time_df.columns:
        group_cols = ["submission_key", "session_number"]

    if not time_df.empty:
        durations = (
            time_df.groupby(group_cols)["time_seconds_num"].agg(["min", "max"]).reset_index()
        )
        durations["duration_seconds"] = (durations["max"] - durations["min"]).clip(lower=0)
        if "submission_key" in durations.columns:
            durations["session_label"] = _short_submission_label(durations["submission_key"]) + " | S" + durations["session_number"].astype(str)
            st.bar_chart(durations.set_index("session_label")[["duration_seconds"]])
        else:
            st.line_chart(durations.set_index("session_number")[["duration_seconds"]])
    else:
        st.info("No numeric Time (seconds) values available for current filters.")
else:
    st.info("Time (seconds) column not found in the filtered data.")

with st.expander("Debug: Program Parser Output", expanded=False):
    debug_cols = ["Program", "program_commands", "program_length", "Button", "run_type", "session_number", "submission_key"]
    available_debug_cols = [c for c in debug_cols if c in analytics_df.columns]
    if available_debug_cols:
        st.dataframe(analytics_df[available_debug_cols], use_container_width=True, height=220)
    else:
        st.info("Debug columns are not available in the current filtered data.")

st.subheader("Filtered Session Data")
st.dataframe(analytics_df, use_container_width=True, height=420)

st.subheader("Submissions Table")
st.dataframe(filtered_submissions, use_container_width=True, height=280)
