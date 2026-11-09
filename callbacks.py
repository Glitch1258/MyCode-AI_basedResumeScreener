"""callbacks.py — Gradio event handlers for the Resume Screening app."""
import logging
import os
import shutil
from datetime import datetime

import gradio as gr
import pandas as pd

from pdf_viewer import highlight_keywords_in_pdf
from resume_screener import ResumeScreeningSystem
from ui_helpers import EMPTY_PREVIEW_HTML, slot_from_state

logger = logging.getLogger(__name__)


def _path(f):
    return f.name if hasattr(f, "name") else f


def _empty_results(msg):
    """Returns 13 outputs matching process_resumes."""
    return (
        pd.DataFrame(columns=["Candidate Name"]),
        None,
        None,
        EMPTY_PREVIEW_HTML,
        None,
        EMPTY_PREVIEW_HTML,
        None,
        1,
        msg,
        "### Preview Slot 1",
        "### Preview Slot 2",
        [],
        gr.update(choices=[], value=[]),
    )


def process_resumes(resume_dir, jd_file, top_n, use_reranker, progress=gr.Progress()):
    if not resume_dir or not jd_file:
        return _empty_results("⚠️ Please select a resume folder and a job description file.")

    try:
        progress(0.0, desc="Initializing system...")
        system = ResumeScreeningSystem(top_n=int(top_n))

        progress(0.1, desc="Reading job description...")
        job_description = system.extract_text_from_file(_path(jd_file))
        if not job_description:
            return _empty_results("❌ Could not extract text from job description file.")

        resume_items = resume_dir if isinstance(resume_dir, list) else [resume_dir]
        resume_paths = [
            _path(f) for f in resume_items
            if str(_path(f)).lower().endswith((".pdf", ".docx"))
        ]
        file_count = len(resume_paths)
        if file_count == 0:
            return _empty_results("⚠️ No PDF/DOCX files found in the selected folder.")

        progress(0.2, desc=f"Processing {file_count} resumes...")
        results_df = system.screen_resumes(
            resume_paths, job_description, use_reranker=bool(use_reranker)
        )

        progress(0.9, desc="Generating summary...")
        top_name = results_df.iloc[0]['Candidate Name'] if not results_df.empty else 'N/A'
        if use_reranker and not results_df.empty:
            top_score = f"{results_df.iloc[0]['Final Cross-Encoder Score']:.3f}"
            match_counts = (
                f"- Strong Matches: {len(results_df[results_df['Category'] == 'Strong Match'])}\n"
                f"- Partial Matches: {len(results_df[results_df['Category'] == 'Partial Match'])}\n"
                f"- Weak Matches: {len(results_df[results_df['Category'] == 'Weak Match'])}\n"
            )
        else:
            top_score = (
                f"{results_df.iloc[0]['Initial Similarity Score']:.3f} (SBERT only)"
                if not results_df.empty else 'N/A'
            )
            match_counts = "- Category: N/A (Reranker OFF)\n"

        summary = f"""
           ## ✅ Screening Complete
           - **Files found in selected folder: {file_count}**
           - Total candidates processed: {len(results_df)}
           {match_counts}- Top candidate: {top_name}
           - Top score: {top_score}

           ### Model Information
           - Sentence-BERT Model: all-MiniLM-L6-v2
           - Cross-Encoder Model: cross-encoder/ms-marco-MiniLM-L-6-v2
           - Reranker: {'ON' if use_reranker else 'OFF'}
           - Top N candidates passed to Cross-Encoder: {system.top_n}

           ### Tip
           Add **filter keywords** above to narrow results. Each click on a
           Candidate Name loads their highlighted PDF into the first available preview slot.
           Clear a slot (✖) to free it up.
           """

        progress(1.0, desc="Complete!")
        display_df = results_df[["Candidate Name"]].copy()

        return (
            display_df,
            results_df,
            results_df.copy(),
            EMPTY_PREVIEW_HTML,
            None,
            EMPTY_PREVIEW_HTML,
            None,
            1,
            summary,
            "### Preview Slot 1",
            "### Preview Slot 2",
            [],
            gr.update(choices=[], value=[]),
        )

    except Exception as e:
        logger.error(f"Error in processing: {e}")
        return _empty_results(f"❌ Error: {str(e)}")


def save_results(full_results_df):
    if full_results_df is None or full_results_df.empty:
        return "No results to save."
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"resume_screening_results_{timestamp}.csv"
    to_save = full_results_df.drop(columns=["row_id"], errors="ignore")
    to_save.to_csv(filename, index=False)
    return f"Results saved to {filename} (full data with all columns)"


def on_row_select(view_df, slot1, slot2, active_slot, evt: gr.SelectData):
    """Row click → fill first empty slot (slot1 preferred)."""

    def _unchanged(msg=""):
        return (gr.update(), slot1, gr.update(), slot2,
                active_slot, msg, gr.update(), gr.update())

    if view_df is None or getattr(view_df, "empty", True):
        return _unchanged("")

    if slot1 is not None and slot2 is not None:
        return _unchanged(
            "⚠️ Both preview slots are full. Click **✖ Clear** on one "
            "slot to load another candidate."
        )

    try:
        row = int(evt.index[0]) if isinstance(evt.index, (list, tuple)) else int(evt.index)
    except Exception:
        return _unchanged("")

    if row < 0 or row >= len(view_df):
        return _unchanged("")

    row_data = view_df.iloc[row]
    pdf_path = row_data.get("PDF Path")
    candidate_name = row_data.get("Candidate Name")

    try:
        row_id = int(row_data["row_id"])
    except (KeyError, ValueError, TypeError):
        row_id = row

    keywords = []
    try:
        full_kw_lists = view_df.attrs.get("full_keywords")
        if full_kw_lists is not None and 0 <= row_id < len(full_kw_lists):
            keywords = list(full_kw_lists[row_id])
    except Exception:
        pass

    if not keywords:
        raw = row_data.get("Extracted Keywords", "") or ""
        if isinstance(raw, (list, tuple)):
            keywords = [str(k) for k in raw]
        else:
            keywords = [k.strip() for k in str(raw).split(",") if k.strip()]

    if not pdf_path:
        return _unchanged("No PDF path for this candidate.")

    try:
        highlighted_path = highlight_keywords_in_pdf(pdf_path, keywords)
    except Exception as e:
        logger.error(f"Highlight failed: {e}")
        highlighted_path = pdf_path

    local_preview = os.path.join(os.getcwd(), os.path.basename(highlighted_path))
    try:
        shutil.copyfile(highlighted_path, local_preview)
    except Exception:
        local_preview = highlighted_path

    new_slot_value = (local_preview, pdf_path)

    if slot1 is None:
        target_slot = 1
        new_s1, new_s2 = new_slot_value, slot2
        new_active = 2 if slot2 is None else 1
    else:
        target_slot = 2
        new_s1, new_s2 = slot1, new_slot_value
        new_active = 2

    html1, title1 = slot_from_state(new_s1, 1)
    html2, title2 = slot_from_state(new_s2, 2)

    status = (
        f"Loaded **{candidate_name}** into Slot {target_slot} — "
        f"{len(keywords)} keyword(s) highlighted."
    )

    return (
        gr.update(value=html1), new_s1,
        gr.update(value=html2), new_s2,
        new_active, status, title1, title2,
    )


def _delete_file(path):
    """Best-effort delete of a single file."""
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted highlighted PDF: {path}")
    except Exception as e:
        logger.warning(f"Could not delete {path}: {e}")


def clear_slot1(slot1, slot2, active_slot):
    # Delete the highlighted PDF that was being served for slot 1
    if slot1:
        try:
            local_preview, _original = slot1
            _delete_file(local_preview)
        except Exception:
            pass
    return (gr.update(value=EMPTY_PREVIEW_HTML), None, 1, "", "### Preview Slot 1")


def clear_slot2(slot1, slot2, active_slot):
    # Delete the highlighted PDF that was being served for slot 2
    if slot2:
        try:
            local_preview, _original = slot2
            _delete_file(local_preview)
        except Exception:
            pass
    new_active = 1 if slot1 is None else 2
    return (gr.update(value=EMPTY_PREVIEW_HTML), None, new_active, "", "### Preview Slot 2")