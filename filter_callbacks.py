"""filter_callbacks.py — Gradio callbacks for the keyword-filter UI."""
from __future__ import annotations

import re
from typing import List

import gradio as gr
import pandas as pd

from resume_filter import MAX_FILTER_KEYWORDS, clean_keywords, filter_results_df


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _split_input(raw: str) -> List[str]:
    """Parse the textbox into individual keywords (comma or semicolon separated)."""
    if not raw:
        return []
    parts: List[str] = []
    for chunk in re.split(r"[,;]", raw):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _make_display_df(view_df: pd.DataFrame) -> pd.DataFrame:
    if view_df is None or view_df.empty or "Candidate Name" not in view_df.columns:
        return pd.DataFrame(columns=["Candidate Name"])
    return view_df[["Candidate Name"]].copy()


# --------------------------------------------------------------------------- #
# Add keywords
# --------------------------------------------------------------------------- #
def add_keywords(current_choices, current_active, raw_input):
    """Add user-typed keywords to the active filter list.

    Outputs: keyword_choices_state, active_filters_cb, filter_keywords_input, filter_status
    Note: does NOT re-run the filter itself — the CheckboxGroup `.change` event
    fires when `active_filters_cb` is updated, which handles filtering.
    """
    new_kws = _split_input(raw_input)
    if not new_kws:
        return current_choices, gr.update(), raw_input, "Type some keywords first."

    existing_norm = {k.lower() for k in current_choices}
    truly_new = [k for k in new_kws if k.lower() not in existing_norm]

    if not truly_new:
        return current_choices, gr.update(), "", "Those keyword(s) are already in the list."

    combined = clean_keywords(list(current_choices) + truly_new)
    prev_checked = {k.lower() for k in (current_active or [])}
    new_norm = {k.lower() for k in truly_new}
    new_active = [
        k for k in combined
        if k.lower() in prev_checked or k.lower() in new_norm
    ]

    status = f"Added {len(truly_new)} keyword(s) — {len(combined)} total."
    if len(combined) >= MAX_FILTER_KEYWORDS:
        status += f" (max {MAX_FILTER_KEYWORDS})"

    return (
        combined,
        gr.update(choices=combined, value=new_active),
        "",
        status,
    )


# --------------------------------------------------------------------------- #
# Filter on checkbox change
# --------------------------------------------------------------------------- #
def on_filters_changed(full_results_df, active_keywords):
    """Re-filter the results when the checkbox value changes.

    Outputs: results_output, view_state
    """
    view_df = filter_results_df(full_results_df, list(active_keywords or []))
    return _make_display_df(view_df), view_df


# --------------------------------------------------------------------------- #
# Clear all
# --------------------------------------------------------------------------- #
def clear_all_filters(full_results_df):
    """Reset filters to empty and unfilter the results.

    Outputs: keyword_choices_state, active_filters_cb, filter_status,
             results_output, view_state
    """
    view_df = filter_results_df(full_results_df, [])
    return (
        [],
        gr.update(choices=[], value=[]),
        "Cleared all filter keywords.",
        _make_display_df(view_df),
        view_df,
    )
