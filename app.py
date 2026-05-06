import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics_utils import (
    add_robot_analytics_fields,
    build_path_map_data,
    build_sankey_data,
)
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


def ensure_columns(df: pd.DataFrame, defaults: dict) -> pd.DataFrame:
    out = df.copy()
    for col, default in defaults.items():
        if col not in out.columns:
            out[col] = default
    return out


def normalize_program_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Program/program_length columns after joins that may add suffixes."""
    out = df.copy()
    if "Program" not in out.columns:
        if "Program_x" in out.columns:
            out["Program"] = out["Program_x"]
        elif "Program_y" in out.columns:
            out["Program"] = out["Program_y"]
    if "program_length" not in out.columns:
        if "program_length_x" in out.columns:
            out["program_length"] = out["program_length_x"]
        elif "program_length_y" in out.columns:
            out["program_length"] = out["program_length_y"]
    return out.drop(columns=[c for c in ["Program_x", "Program_y", "program_length_x", "program_length_y"] if c in out.columns])


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

st.subheader("Program Visualization Controls")
st.caption("Choose which Play/Test program runs are used by the Sankey and Eagle-Eye visuals.")
st.caption(
    "Each Program Run is one Play/Test row. One uploaded file can contain multiple sessions, "
    "and each session can contain multiple program runs."
)
run_cols = [
    "Program", "program_commands", "program_length", "student_id", "teacher_name", "class_section",
    "submission_key", "session_number", "source_row_number", "Time (seconds)", "session_date", "run_type",
]
program_runs = analytics_df.copy()
for col in run_cols:
    if col not in program_runs.columns:
        program_runs[col] = None
program_runs = program_runs[program_runs["run_type"].isin(["Play", "Test"])].copy()
program_runs["program_commands"] = program_runs["program_commands"].apply(lambda x: x if isinstance(x, list) else [])
program_runs["program_length"] = pd.to_numeric(program_runs["program_length"], errors="coerce").fillna(0).astype(int)
program_runs["Program"] = program_runs["Program"].fillna("").astype(str).str.strip()
program_runs["is_empty_program"] = program_runs["program_length"].eq(0)
include_empty_programs = st.checkbox("Include empty programs", value=False)
if not include_empty_programs:
    program_runs = program_runs[~program_runs["is_empty_program"]].copy()

if program_runs.empty:
    st.info("No valid Play/Test program rows available for current filters.")
else:
    selected_run_types = st.multiselect("Run Type", ["Play", "Test"], default=["Play", "Test"])
    control_df = program_runs[program_runs["run_type"].isin(selected_run_types)].copy()

    student_options = sorted(control_df["student_id"].dropna().astype(str).unique().tolist())
    selected_students_ctrl = st.multiselect("Students", student_options, default=student_options)
    if selected_students_ctrl:
        control_df = control_df[control_df["student_id"].astype(str).isin(selected_students_ctrl)].copy()

    submission_options = sorted(control_df["submission_key"].dropna().astype(str).unique().tolist())
    selected_submissions = st.multiselect("Submission / Uploaded File", submission_options, default=submission_options)
    if selected_submissions:
        control_df = control_df[control_df["submission_key"].astype(str).isin(selected_submissions)].copy()

    session_options = sorted(pd.to_numeric(control_df["session_number"], errors="coerce").dropna().astype(int).unique().tolist())
    selected_sessions = st.multiselect("Session Number", session_options, default=session_options)
    if selected_sessions:
        control_df = control_df[pd.to_numeric(control_df["session_number"], errors="coerce").astype("Int64").isin(selected_sessions)].copy()

    if not control_df.empty and control_df["program_length"].notna().any():
        min_len = int(control_df["program_length"].min())
        max_len = int(control_df["program_length"].max())
        selected_len = st.slider("Program Length Range", min_len, max_len, (min_len, max_len))
        control_df = control_df[control_df["program_length"].between(selected_len[0], selected_len[1], inclusive="both")]

    comparison_mode = st.selectbox(
        "Comparison Mode",
        [
            "All selected program runs",
            "Latest run per student",
            "Longest run per student",
            "Latest run per student per session",
        ],
        index=1,
    )
    if not control_df.empty:
        control_df["time_num"] = pd.to_numeric(control_df["Time (seconds)"], errors="coerce")
        control_df["row_num"] = pd.to_numeric(control_df["source_row_number"], errors="coerce")
        if comparison_mode == "Latest run per student":
            control_df = control_df.sort_values(["student_id", "time_num", "row_num"]).groupby("student_id", as_index=False).tail(1)
        elif comparison_mode == "Longest run per student":
            control_df = control_df.sort_values(["student_id", "program_length", "time_num", "row_num"]).groupby("student_id", as_index=False).tail(1)
        elif comparison_mode == "Latest run per student per session":
            control_df = control_df.sort_values(["student_id", "session_number", "time_num", "row_num"]).groupby(
                ["student_id", "session_number"], as_index=False
            ).tail(1)

    control_df["file_label"] = _short_submission_label(control_df["submission_key"].fillna("").astype(str))
    control_df["run_label"] = (
        control_df["student_id"].astype(str) + " | Session " +
        "File " + control_df["file_label"].astype(str) + " | Session " +
        control_df["session_number"].fillna(1).astype(int).astype(str) + " | row " +
        control_df["source_row_number"].fillna(-1).astype(int).astype(str) + " | " +
        control_df["run_type"].astype(str) + " | " + control_df["Program"].replace("", "Empty")
    )
    run_labels = control_df["run_label"].tolist()
    selected_run_labels = st.multiselect("Program Run selector", run_labels, default=run_labels)
    selected_runs_df = control_df[control_df["run_label"].isin(selected_run_labels)].copy()

    if selected_runs_df.empty:
        st.info("No program runs selected. Please choose one or more runs.")
    else:
        path_df = build_path_map_data(selected_runs_df)
        final_points = (
            path_df.sort_values(["run_label", "step"])
            .groupby("run_label", as_index=False).tail(1)[["run_label", "student_id", "x", "y"]]
            .rename(columns={"x": "final_x", "y": "final_y"})
        )
        final_points["final_coordinate"] = "(" + final_points["final_x"].astype(str) + ", " + final_points["final_y"].astype(str) + ")"
        selected_runs_df = selected_runs_df.merge(final_points[["run_label", "final_x", "final_y", "final_coordinate"]], on="run_label", how="left")
        selected_runs_df["program_commands_str"] = selected_runs_df["program_commands"].apply(lambda cmds: " ".join(cmds))
        with st.expander("Debug: Selected Program Runs", expanded=False):
            st.dataframe(selected_runs_df, use_container_width=True)

        st.subheader("Program Divergence Sankey")
        st.caption("Shows common step-to-step command paths and where selected runs diverge. Includes END nodes.")
        sankey_data = build_sankey_data(selected_runs_df)
        if sankey_data:
            total_runs = len(selected_runs_df)
            link_custom = [f"{v} runs ({(v / total_runs) * 100:.1f}%)" for v in sankey_data["value"]]
            sankey_fig = go.Figure(
                data=[
                    go.Sankey(
                        node=dict(label=sankey_data["labels"], pad=15, thickness=16),
                        link=dict(
                            source=sankey_data["source"], target=sankey_data["target"], value=sankey_data["value"],
                            customdata=link_custom,
                            hovertemplate="Count: %{value}<br>%{customdata}<extra></extra>",
                        ),
                    )
                ]
            )
            sankey_fig.update_layout(height=520, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(sankey_fig, use_container_width=True)
            seqs = selected_runs_df["program_commands"].apply(lambda c: " ".join(c))
            common_first = selected_runs_df["program_commands"].apply(lambda c: c[0] if len(c) else "None").mode()
            common_coord = final_points["final_coordinate"].mode()
            st.markdown(
                f"- Selected program runs: **{total_runs}**\n"
                f"- Unique command sequences: **{seqs.nunique()}**\n"
                f"- Most common first command: **{common_first.iloc[0] if not common_first.empty else 'N/A'}**\n"
                f"- Most common final coordinate: **{common_coord.iloc[0] if not common_coord.empty else 'N/A'}**"
            )
            with st.expander("Sankey Source Data", expanded=False):
                cols = ["student_id", "teacher_name", "class_section", "submission_key", "session_number", "source_row_number",
                        "run_type", "Time (seconds)", "Program", "program_commands", "program_length", "final_coordinate"]
                st.dataframe(selected_runs_df[[c for c in cols if c in selected_runs_df.columns]], use_container_width=True)
            with st.expander("Debug: Sankey Transitions", expanded=False):
                st.dataframe(sankey_data["transitions_df"], use_container_width=True)
        else:
            st.info("No valid selected programs available to build Sankey.")

        st.subheader("Eagle-Eye Program Path Map")
        st.caption("Simulated intended path (not measured trajectory). Start=(0,0), heading East; turns are 90°; movement is one grid unit.")
        if path_df.empty:
            st.info("No valid selected programs available to simulate paths.")
        else:
            max_step = int(path_df["step"].max())
            show_full_path = st.checkbox("Show full path", value=True)
            playback_step = st.slider("Playback step", 0, max_step, max_step)
            path_display = path_df if show_full_path else path_df[path_df["step"] <= playback_step].copy()
            path_display["coord"] = "(" + path_display["x"].astype(str) + ", " + path_display["y"].astype(str) + ")"
            metadata_cols = [c for c in ["run_label", "Program", "program_length"] if c in selected_runs_df.columns and (c == "run_label" or c not in path_display.columns)]
            path_display = path_display.merge(selected_runs_df[metadata_cols], on="run_label", how="left")
            path_display = normalize_program_columns(path_display)
            hover_cols = [
                "student_id",
                "session_number",
                "source_row_number",
                "run_type",
                "Program",
                "program_length",
                "command",
                "coord",
            ]
            hover_cols = [c for c in hover_cols if c in path_display.columns]

            max_abs = int(max(path_display["x"].abs().max(), path_display["y"].abs().max(), 1))
            path_fig = px.line(path_display.sort_values(["run_label", "step"]), x="x", y="y", color="run_label",
                               line_group="run_label", markers=True,
                               hover_data=hover_cols)
            path_fig.update_xaxes(range=[-max_abs - 1, max_abs + 1], zeroline=True, showgrid=True, title="X")
            path_fig.update_yaxes(range=[-max_abs - 1, max_abs + 1], zeroline=True, showgrid=True, scaleanchor="x", scaleratio=1, title="Y")
            path_fig.add_annotation(x=max_abs * 0.7, y=max_abs * 0.7, text="Quadrant I", showarrow=False)
            path_fig.add_annotation(x=-max_abs * 0.7, y=max_abs * 0.7, text="Quadrant II", showarrow=False)
            path_fig.add_annotation(x=-max_abs * 0.7, y=-max_abs * 0.7, text="Quadrant III", showarrow=False)
            path_fig.add_annotation(x=max_abs * 0.7, y=-max_abs * 0.7, text="Quadrant IV", showarrow=False)
            path_fig.update_layout(height=560, legend_title_text="Program Runs")
            st.plotly_chart(path_fig, use_container_width=True)
            with st.expander("Debug: Eagle-Eye Path Points", expanded=False):
                st.dataframe(path_df, use_container_width=True)

            coord_options = sorted(final_points["final_coordinate"].dropna().unique().tolist())
            selected_coord = st.selectbox("Inspect final coordinate", coord_options)
            st.dataframe(
                selected_runs_df[selected_runs_df["final_coordinate"] == selected_coord][
                    ["teacher_name", "class_section", "student_id", "session_date", "submission_key", "session_number",
                     "source_row_number", "run_type", "Time (seconds)", "Program", "program_length", "final_coordinate"]
                ].sort_values(["student_id", "session_number", "source_row_number"]),
                use_container_width=True,
            )

            st.download_button(
                "Download selected program runs CSV",
                data=ensure_columns(
                    normalize_program_columns(selected_runs_df),
                    {
                        "teacher_name": "", "class_section": "", "student_id": "", "session_date": "", "submission_key": "",
                        "session_number": "", "source_row_number": "", "run_type": "", "Time (seconds)": "", "Program": "",
                        "program_commands_str": "", "program_length": 0, "final_x": "", "final_y": "", "final_coordinate": "",
                    },
                )[["teacher_name", "class_section", "student_id", "session_date", "submission_key",
                   "session_number", "source_row_number", "run_type", "Time (seconds)", "Program",
                   "program_commands_str", "program_length", "final_x", "final_y", "final_coordinate"]]
                .rename(columns={"program_commands_str": "program_commands"}).to_csv(index=False),
                file_name="selected_program_runs.csv",
                mime="text/csv",
            )
            path_export = path_df.merge(final_points[["run_label", "final_x", "final_y", "final_coordinate"]], on="run_label", how="left").rename(columns={"step": "step_number"})
            run_cols = ["run_label", "teacher_name", "class_section", "student_id", "session_date", "submission_key",
                        "session_number", "source_row_number", "run_type", "Time (seconds)", "Program", "program_commands",
                        "program_length", "final_x", "final_y", "final_coordinate"]
            path_export = path_export.drop(columns=[c for c in run_cols if c in path_export.columns and c != "run_label"])
            path_export = path_export.merge(selected_runs_df[[c for c in run_cols if c in selected_runs_df.columns]], on="run_label", how="left")
            path_export = normalize_program_columns(path_export)
            path_export = ensure_columns(
                path_export,
                {
                    "run_label": "", "teacher_name": "", "class_section": "", "student_id": "", "session_date": "",
                    "submission_key": "", "session_number": "", "source_row_number": "", "run_type": "",
                    "Time (seconds)": "", "Program": "", "program_commands": "", "program_length": 0,
                    "step_number": 0, "command": "", "x": 0, "y": 0, "final_x": "", "final_y": "", "final_coordinate": "",
                },
            )
            st.download_button(
                "Download eagle-eye path points CSV",
                data=ensure_columns(
                    path_export,
                    {
                        "run_label": "", "teacher_name": "", "class_section": "", "student_id": "", "session_date": "",
                        "submission_key": "", "session_number": "", "source_row_number": "", "run_type": "",
                        "Time (seconds)": "", "Program": "", "program_commands": "", "program_length": 0,
                        "step_number": 0, "command": "", "x": 0, "y": 0, "final_x": "", "final_y": "", "final_coordinate": "",
                    },
                )[["run_label", "teacher_name", "class_section", "student_id", "session_date", "submission_key",
                   "session_number", "source_row_number", "run_type", "Time (seconds)", "Program", "program_commands",
                   "program_length", "step_number", "command", "x", "y", "final_x", "final_y", "final_coordinate"]].to_csv(index=False),
                file_name="eagle_eye_path_points.csv",
                mime="text/csv",
            )
            if sankey_data:
                st.download_button(
                    "Download Sankey transitions CSV",
                    data=sankey_data["transitions_df"].to_csv(index=False),
                    file_name="program_sankey_transitions.csv",
                    mime="text/csv",
                )

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
