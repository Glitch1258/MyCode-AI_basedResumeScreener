"""filter_callbacks.py — Gradio callbacks for the keyword-filter UI."""
from __future__ import annotations

import re
from typing import List

import gradio as gr
import pandas as pd

from rating import make_display_df, sort_by_user_rating
from resume_filter import MAX_FILTER_KEYWORDS, clean_keywords, filter_results_df


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _split_input(raw: str) -> List[str]:
    if not raw:
        return []
    parts: List[str] = []
    for chunk in re.split(r"[,;]", raw):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _render_view(full_results_df, active_keywords, sort_active, ratings):
    """Filter, optionally sort by rating, and produce the display DataFrame."""
    view = filter_results_df(full_results_df, list(active_keywords or []))
    if sort_active:
        view = sort_by_user_rating(view, ratings or {}, ascending=False)
    return make_display_df(view, ratings), view


# --------------------------------------------------------------------------- #
# Add keywords
# --------------------------------------------------------------------------- #
def add_keywords(current_choices, current_active, raw_input):
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
# Filter on checkbox change (sort + ratings threaded through)
# --------------------------------------------------------------------------- #
def on_filters_changed(full_results_df, active_keywords, sort_by_rating, ratings):
    """Outputs: results_output, view_state"""
    display, view = _render_view(full_results_df, active_keywords,
                                 sort_by_rating, ratings)
    return display, view


# --------------------------------------------------------------------------- #
# Clear all
# --------------------------------------------------------------------------- #
def clear_all_filters(full_results_df, sort_by_rating, ratings):
    """Outputs: keyword_choices_state, active_filters_cb, filter_status,
                results_output, view_state"""
    display, view = _render_view(full_results_df, [], sort_by_rating, ratings)
    return (
        [],
        gr.update(choices=[], value=[]),
        "Cleared all filter keywords.",
        display,
        view,
    )
