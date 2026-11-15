"""rating.py — Pure logic for user ratings (1–10) on candidates.

No Gradio imports. Used by rating_callbacks.py, callbacks.py, filter_callbacks.py.

Ratings are stored in a plain dict keyed by the candidate's original PDF path
(the "PDF Path" column from the screening DataFrame). Using the path (rather
than row_id or table index) keeps ratings stable across filtering and sorting.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

DEFAULT_RATING = 1
MIN_RATING = 1
MAX_RATING = 10


# --------------------------------------------------------------------------- #
# Initialisation / mutation
# --------------------------------------------------------------------------- #
def initialize_ratings(full_results_df: Optional[pd.DataFrame]) -> Dict[str, int]:
    """Return {pdf_path: DEFAULT_RATING} for every candidate in the DataFrame."""
    if full_results_df is None or getattr(full_results_df, "empty", True):
        return {}
    if "PDF Path" not in full_results_df.columns:
        return {}
    return {str(p): DEFAULT_RATING for p in full_results_df["PDF Path"]}


def clamp_rating(value) -> int:
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_RATING
    return max(MIN_RATING, min(MAX_RATING, v))


def set_rating(ratings: Optional[Dict[str, int]], pdf_path: Optional[str],
               new_rating) -> Dict[str, int]:
    out = dict(ratings or {})
    if not pdf_path:
        return out
    out[str(pdf_path)] = clamp_rating(new_rating)
    return out


def get_rating(ratings: Optional[Dict[str, int]], pdf_path: Optional[str]) -> int:
    if not ratings or not pdf_path:
        return DEFAULT_RATING
    return int(ratings.get(str(pdf_path), DEFAULT_RATING))


# --------------------------------------------------------------------------- #
# DataFrame views
# --------------------------------------------------------------------------- #
def _restore_attrs(src: pd.DataFrame, dst: pd.DataFrame) -> None:
    for k, v in src.attrs.items():
        dst.attrs[k] = v


def apply_ratings_to_df(full_results_df: Optional[pd.DataFrame],
                        ratings: Dict[str, int]) -> Optional[pd.DataFrame]:
    """Return a copy of full_results_df with a 'User Rating' column applied."""
    if full_results_df is None:
        return None
    out = full_results_df.copy()
    _restore_attrs(full_results_df, out)
    if "PDF Path" in out.columns:
        out["User Rating"] = out["PDF Path"].astype(str).map(
            lambda p: int(ratings.get(str(p), DEFAULT_RATING)) if ratings else DEFAULT_RATING
        )
    else:
        out["User Rating"] = DEFAULT_RATING
    _restore_attrs(full_results_df, out)
    return out


def sort_by_user_rating(df: pd.DataFrame, ratings: Dict[str, int],
                        ascending: bool = False) -> pd.DataFrame:
    """Stable-sort a results DataFrame by the user-rating dict (desc by default)."""
    if df is None or getattr(df, "empty", True) or "PDF Path" not in df.columns:
        return df

    out = df.copy()
    _restore_attrs(df, out)

    ratings = ratings or {}
    out["_rating_key"] = out["PDF Path"].astype(str).map(
        lambda p: int(ratings.get(str(p), DEFAULT_RATING))
    )
    out = (out.sort_values("_rating_key", ascending=ascending, kind="stable")
           .drop(columns=["_rating_key"])
           .reset_index(drop=True))
    _restore_attrs(df, out)
    return out


def make_display_df(view_df: Optional[pd.DataFrame],
                    ratings: Optional[Dict[str, int]] = None) -> pd.DataFrame:
    """The two-column table shown in the UI: Candidate Name + ★ rating."""
    empty = pd.DataFrame(columns=["Candidate Name", "⭐"])
    if view_df is None or getattr(view_df, "empty", True) or "Candidate Name" not in view_df.columns:
        return empty

    display = view_df[["Candidate Name"]].copy()
    if "PDF Path" in view_df.columns and ratings:
        display["⭐"] = view_df["PDF Path"].astype(str).map(
            lambda p: int(ratings.get(str(p), DEFAULT_RATING))
        )
    else:
        display["⭐"] = DEFAULT_RATING
    return display
