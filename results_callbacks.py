"""results_callbacks.py — Gradio handlers for save/load dialogs.

Bridges results_ui.py (UI) to results_store.py (persistence).
"""
from __future__ import annotations

import logging
from datetime import datetime

import gradio as gr

from callbacks import save_results as save_results_csv
from rating import DEFAULT_RATING, make_display_df
from results_store import delete_run, list_runs, load_run, save_run
from star_rating import star_updates
from ui_helpers import EMPTY_PREVIEW_HTML

logger = logging.getLogger(__name__)


def _runs_to_choices(runs):
    return [
        (f"{r['name']}  —  {r['created_at']}  ({r['n_candidates']} candidates)", r["id"])
        for r in runs
    ]


# --------------------------------------------------------------------------- #
# Save dialog
# --------------------------------------------------------------------------- #
def open_save_dialog(full_results_df):
    """Outputs: save_dialog, save_name_input, save_dialog_status."""
    default = f"Screening {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    warn = ""
    if full_results_df is None or getattr(full_results_df, "empty", True):
        warn = "⚠️ No results to save — run a screening first."
    return gr.update(visible=True), gr.update(value=default), warn


def cancel_save_dialog():
    return gr.update(visible=False), ""


def save_to_db(name, full_results_df, ratings, summary):
    """Outputs: save_dialog, save_dialog_status, save_name_input."""
    if full_results_df is None or getattr(full_results_df, "empty", True):
        return gr.update(), "⚠️ Nothing to save.", gr.update()
    result = save_run(name, full_results_df, ratings or {}, summary or "")
    if result["ok"]:
        return gr.update(visible=False), "", gr.update(value="")
    return gr.update(), f"❌ {result['message']}", gr.update()


def save_csv_only(full_results_df, ratings):
    """Outputs: save_dialog_status."""
    msg = save_results_csv(full_results_df, ratings)
    return f"📄 {msg}"


# --------------------------------------------------------------------------- #
# Load dialog
# --------------------------------------------------------------------------- #
def open_load_dialog():
    """Outputs: load_dialog, load_radio, load_dialog_status."""
    runs = list_runs()
    if not runs:
        return (gr.update(visible=True),
                gr.update(choices=[], value=None),
                "No saved runs yet — run a screening and click 💾 Save Results.")
    return (gr.update(visible=True),
            gr.update(choices=_runs_to_choices(runs), value=None),
            "")


def cancel_load_dialog():
    return gr.update(visible=False), ""


def delete_selected_run(run_id):
    """Outputs: load_radio, load_dialog_status."""
    if not run_id:
        return gr.update(), "⚠️ Select a run first."
    result = delete_run(int(run_id))
    runs = list_runs()
    status = ("🗑 " if result["ok"] else "❌ ") + result["message"]
    return gr.update(choices=_runs_to_choices(runs), value=None), status


def _load_unchanged(msg=""):
    """38 no-op outputs matching load_selected_run."""
    return (
        gr.update(), gr.update(), gr.update(),  # results, full, view
        gr.update(), gr.update(),  # slot1 html, state
        gr.update(), gr.update(),  # slot2 html, state
        gr.update(),  # active slot
        gr.update(),  # summary
        gr.update(), gr.update(),  # slot titles
        gr.update(), gr.update(),  # kw state, cb
        gr.update(), gr.update(), gr.update(),  # ratings, sort, sort_btn
        *[gr.update()] * 10,  # slot1 stars
        *[gr.update()] * 10,  # slot2 stars
        gr.update(),  # load_dialog
        msg,  # load_dialog_status
    )


def load_selected_run(run_id):
    """Outputs: 16 state/UI + 20 stars + load_dialog + status = 38."""
    if not run_id:
        return _load_unchanged("⚠️ Select a run first.")
    data = load_run(int(run_id))
    if data is None:
        return _load_unchanged("❌ Could not load that run.")

    df = data["results_df"]
    ratings = data["ratings"] or {}
    summary = data["summary"] or ""

    return (
        make_display_df(df, ratings),  # results_output
        df,  # full_results_state
        df.copy(),  # view_state
        EMPTY_PREVIEW_HTML, None,  # slot1
        EMPTY_PREVIEW_HTML, None,  # slot2
        1,  # active_slot_state
        summary,  # summary_output
        "### Preview Slot 1", "### Preview Slot 2",  # slot titles
        [], gr.update(choices=[], value=[]),  # keyword reset
        ratings,  # ratings_state
        False,  # sort state
        gr.update(value="⭐ Sort by Rating"),  # sort button
        *star_updates(DEFAULT_RATING),  # slot1 stars
        *star_updates(DEFAULT_RATING),  # slot2 stars
        gr.update(visible=False),  # close dialog
        f"✅ Loaded '{data['name']}' ({len(df)} candidates).",
    )
