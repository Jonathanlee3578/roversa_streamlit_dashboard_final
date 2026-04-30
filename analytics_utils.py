import pandas as pd


def _series_or_empty(df: pd.DataFrame, column: str, default="") -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def add_robot_analytics_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with robust robot analytics columns added.

    Adds:
      - is_new_session
      - session_number
      - program_length
      - run_type
    """
    out = df.copy()
    if out.empty:
        for col, default in [
            ("is_new_session", pd.Series(dtype="bool")),
            ("session_number", pd.Series(dtype="int64")),
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

    program_raw = _series_or_empty(out, "Program", default="").fillna("").astype(str).str.strip()
    is_empty_program = program_raw.eq("") | program_raw.str.lower().eq("empty")
    out["program_length"] = 0
    out.loc[~is_empty_program, "program_length"] = (
        program_raw[~is_empty_program].str.split().str.len().fillna(0).astype(int)
    )

    button_raw = _series_or_empty(out, "Button", default="").fillna("").astype(str).str.strip()
    out["run_type"] = "Other"
    out.loc[button_raw.eq("Play"), "run_type"] = "Play"
    out.loc[button_raw.eq("Test"), "run_type"] = "Test"

    return out
