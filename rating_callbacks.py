"""rating_callbacks.py — Gradio handlers for the star rating + sort toggle."""
from __future__ import annotations

import gradio as gr
import pandas as pd

from rating import make_display_df, set_rating, sort_by_user_rating
from resume_filter import filter_results_df
from star_rating import NUM_STARS, star_updates


def _build_view(full_results_df, active_keywords, ratings, sort_active):
    view = filter_results_df(full_results_df, list(active_keywords or []))
    if sort_active:
        view = sort_by_user_rating(view, ratings or {}, ascending=False)
    return view


def _star_click_body(star_value, slot_value, ratings,
                     full_results_df, active_keywords, sort_active):
    """Outputs: ratings_state, results_output, view_state, *10 star updates."""
    noop = (ratings, gr.update(), gr.update(), *[gr.update()] * NUM_STARS)
    if not slot_value:
        return noop
    try:
        _h, pdf_path = slot_value
    except Exception:
        return noop
    if not pdf_path:
        return noop

    new_ratings = set_rating(ratings, pdf_path, star_value)
    view = _build_view(full_results_df, active_keywords, new_ratings, sort_active)
    return (
        new_ratings,
        make_display_df(view, new_ratings),
        view,
        *star_updates(star_value),
    )


def on_star_click_slot1(star_value, slot1, ratings,
                        full_results_df, active_keywords, sort_active):
    return _star_click_body(star_value, slot1, ratings,
                            full_results_df, active_keywords, sort_active)


def on_star_click_slot2(star_value, slot2, ratings,
                        full_results_df, active_keywords, sort_active):
    return _star_click_body(star_value, slot2, ratings,
                            full_results_df, active_keywords, sort_active)


def toggle_sort(sort_active, full_results_df, active_keywords, ratings):
    if full_results_df is None or getattr(full_results_df, "empty", True):
        return sort_active, gr.update(), gr.update(), gr.update()

    new_sort = not bool(sort_active)
    view = _build_view(full_results_df, active_keywords, ratings, new_sort)
    label = "✅ Sorted by Rating (click to undo)" if new_sort else "⭐ Sort by Rating"
    return new_sort, make_display_df(view, ratings), view, gr.update(value=label)
