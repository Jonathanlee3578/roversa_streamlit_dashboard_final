import pandas as pd


def _series_or_empty(df: pd.DataFrame, column: str, default="") -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def parse_program_commands(program) -> list[str]:
    """Parse Program into a whitespace-split lowercase command list."""
    if pd.isna(program):
        return []

    text = str(program).strip()
    if text == "" or text.lower() == "empty":
        return []

    return text.lower().split()


def simulate_program_path(commands: list[str]) -> pd.DataFrame:
    """Simulate a command path from origin using a simple heading model.

    Coordinate convention (easy to adjust if needed):
      - Start at (0, 0), heading East.
      - forward: move +1 along current heading.
      - reverse/backward: move -1 along current heading.
      - left: rotate heading 90° counterclockwise.
      - right: rotate heading 90° clockwise.
    """
    heading_order = ["E", "S", "W", "N"]  # clockwise order for right turns
    vectors = {"E": (1, 0), "S": (0, -1), "W": (-1, 0), "N": (0, 1)}
    heading_idx = 0
    x, y = 0, 0
    rows = [{"step": 0, "command": "START", "x": x, "y": y, "heading": heading_order[heading_idx]}]

    for step, cmd in enumerate(commands, start=1):
        if cmd == "left":
            heading_idx = (heading_idx - 1) % 4
        elif cmd == "right":
            heading_idx = (heading_idx + 1) % 4
        elif cmd in {"forward", "reverse", "backward"}:
            dx, dy = vectors[heading_order[heading_idx]]
            if cmd in {"reverse", "backward"}:
                dx, dy = -dx, -dy
            x += dx
            y += dy

        rows.append({"step": step, "command": cmd, "x": x, "y": y, "heading": heading_order[heading_idx]})

    return pd.DataFrame(rows)


def build_sankey_data(filtered_sessions: pd.DataFrame):
    """Build node/link data for a Plotly Sankey from valid Play/Test program rows."""
    if filtered_sessions.empty:
        return None

    work = filtered_sessions.copy()
    run_type = _series_or_empty(work, "run_type", default="")
    if "run_type" not in work.columns and "Button" in work.columns:
        button_raw = work["Button"].fillna("").astype(str).str.strip()
        run_type = button_raw.where(button_raw.isin(["Play", "Test"]), "Other")
    work["run_type"] = run_type

    work["program_commands"] = _series_or_empty(work, "program_commands", default=[]).apply(
        lambda v: v if isinstance(v, list) else parse_program_commands(v)
    )
    valid = work[(work["run_type"].isin(["Play", "Test"])) & (work["program_commands"].apply(len) > 0)].copy()
    if valid.empty:
        return None

    flows: dict[tuple[str, str], int] = {}
    for commands in valid["program_commands"]:
        for idx in range(len(commands)):
            source = f"S{idx + 1}: {commands[idx]}"
            target = f"S{idx + 2}: {commands[idx + 1]}" if idx + 1 < len(commands) else f"S{idx + 2}: END"
            flows[(source, target)] = flows.get((source, target), 0) + 1

    labels = sorted({n for edge in flows for n in edge})
    label_to_idx = {label: i for i, label in enumerate(labels)}
    source_indices = [label_to_idx[s] for s, _ in flows.keys()]
    target_indices = [label_to_idx[t] for _, t in flows.keys()]
    values = list(flows.values())

    return {"labels": labels, "source": source_indices, "target": target_indices, "value": values}


def build_path_map_data(filtered_sessions: pd.DataFrame) -> pd.DataFrame:
    """Build plottable path points for each valid Play/Test program row."""
    if filtered_sessions.empty:
        return pd.DataFrame()

    work = filtered_sessions.copy()
    run_type = _series_or_empty(work, "run_type", default="")
    if "run_type" not in work.columns and "Button" in work.columns:
        button_raw = work["Button"].fillna("").astype(str).str.strip()
        run_type = button_raw.where(button_raw.isin(["Play", "Test"]), "Other")
    work["run_type"] = run_type

    work["program_commands"] = _series_or_empty(work, "program_commands", default=[]).apply(
        lambda v: v if isinstance(v, list) else parse_program_commands(v)
    )
    valid = work[(work["run_type"].isin(["Play", "Test"])) & (work["program_commands"].apply(len) > 0)].copy()
    if valid.empty:
        return pd.DataFrame()

    records = []
    for row_idx, row in valid.reset_index(drop=True).iterrows():
        path_df = simulate_program_path(row["program_commands"])
        student_id = str(row.get("student_id", "unknown_student"))
        submission_key = str(row.get("submission_key", "unknown_submission"))
        run_label = f"{student_id} | {submission_key[-8:]} | row{row_idx}"
        for _, p in path_df.iterrows():
            records.append(
                {
                    "run_label": run_label,
                    "student_id": student_id,
                    "submission_key": submission_key,
                    "session_date": row.get("session_date", ""),
                    "run_type": row.get("run_type", ""),
                    "step": int(p["step"]),
                    "command": p["command"],
                    "x": int(p["x"]),
                    "y": int(p["y"]),
                    "heading": p["heading"],
                }
            )
    return pd.DataFrame(records)


def add_robot_analytics_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with robust robot analytics columns added.

    Adds:
      - is_new_session
      - session_number
      - program_commands
      - program_length
      - run_type
    """
    out = df.copy()
    if out.empty:
        for col, default in [
            ("is_new_session", pd.Series(dtype="bool")),
            ("session_number", pd.Series(dtype="int64")),
            ("program_commands", pd.Series(dtype="object")),
            ("program_length", pd.Series(dtype="int64")),
            ("run_type", pd.Series(dtype="object")),
        ]:
            out[col] = default
        return out

    session_raw = _series_or_empty(out, "Session", default="").fillna("").astype(str).str.strip()
    out["is_new_session"] = session_raw.str.upper().eq("NEW")

    if "submission_key" in out.columns:
        keys = out["submission_key"].fillna("__missing_submission_key__")
        out["session_number"] = out.groupby(keys)["is_new_session"].cumsum().clip(lower=1)
    else:
        out["session_number"] = out["is_new_session"].cumsum().clip(lower=1)

    program_raw = _series_or_empty(out, "Program", default="")
    out["program_commands"] = program_raw.apply(parse_program_commands)
    out["program_length"] = out["program_commands"].apply(len)

    button_raw = _series_or_empty(out, "Button", default="").fillna("").astype(str).str.strip()
    out["run_type"] = "Other"
    out.loc[button_raw.eq("Play"), "run_type"] = "Play"
    out.loc[button_raw.eq("Test"), "run_type"] = "Test"

    return out
