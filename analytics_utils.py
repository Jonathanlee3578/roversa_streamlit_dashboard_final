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
