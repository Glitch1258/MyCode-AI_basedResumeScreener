"""app.py — Gradio entry point for the Resume Screening System."""
import logging
import os
import tempfile

import gradio as gr

from callbacks import (
    process_resumes, on_row_select, clear_slot1, clear_slot2,
)
from filter_callbacks import add_keywords, on_filters_changed, clear_all_filters
from pdf_viewer import purge_all_highlights
from rating_callbacks import (
    on_star_click_slot1, on_star_click_slot2, toggle_sort,
)
from results_callbacks import (
    open_save_dialog, cancel_save_dialog, save_to_db, save_csv_only,
    open_load_dialog, cancel_load_dialog, delete_selected_run, load_selected_run,
)
from results_ui import build_save_dialog, build_load_dialog
from resume_filter import MAX_FILTER_KEYWORDS
from star_rating import make_star_row
from ui_helpers import EMPTY_PREVIEW_HTML
from ui_styles import CSS, SCROLL_LEFT_JS, SCROLL_RIGHT_JS

logger = logging.getLogger(__name__)


def create_gradio_interface():
    try:
        n = purge_all_highlights()
        if n:
            logger.info(f"Purged {n} leftover highlight PDF(s) from previous sessions.")
    except Exception as e:
        logger.warning(f"Startup highlight cleanup failed (non-fatal): {e}")

    with gr.Blocks(
            title="Resume Screening System",
            css=CSS,
            theme=gr.themes.Soft(),
    ) as interface:
        # ---- State ----
        full_results_state = gr.State(value=None)
        view_state = gr.State(value=None)
        keyword_choices_state = gr.State(value=[])
        slot1_state = gr.State(value=None)
        slot2_state = gr.State(value=None)
        active_slot_state = gr.State(value=1)
        ratings_state = gr.State(value={})
        sort_by_rating_state = gr.State(value=False)

        # ---- Top inline row ----
        with gr.Row(elem_classes=["top-row"]):
            with gr.Column(scale=3):
                resume_dir = gr.File(
                    label="Resume Folder (select a folder containing PDF/DOCX files)",
                    file_count="multiple", file_types=[".pdf", ".docx"], height=200,
                )
            with gr.Column(scale=3, elem_classes=["filter-block"]):
                filter_keywords_input = gr.Textbox(
                    label="🔎 Filter keywords",
                    placeholder="e.g. python, machine learning, sql",
                    info="Comma-separated; case-insensitive; phrases OK.",
                    lines=1,
                )
                with gr.Row():
                    add_filters_btn = gr.Button("➕ Add keywords", size="sm", variant="secondary", scale=3)
                    clear_filters_btn = gr.Button("✖ Clear", size="sm", variant="stop", scale=2)
                    scroll_left_btn = gr.Button("◀", size="sm", scale=0, min_width=34, elem_classes=["scroll-arrow"])
                    scroll_right_btn = gr.Button("▶", size="sm", scale=0, min_width=34, elem_classes=["scroll-arrow"])
                active_filters_cb = gr.CheckboxGroup(
                    choices=[], value=[],
                    label=f"Active filters (max {MAX_FILTER_KEYWORDS})",
                    elem_classes=["filter-checkbox"],
                )
                filter_status = gr.Markdown("")
            with gr.Column(scale=3):
                jd_file = gr.File(
                    label="Job Description File (PDF / DOCX)",
                    file_count="single", file_types=[".pdf", ".docx"],
                )
            with gr.Column(scale=1):
                top_n = gr.Number(
                    label="Top N", value=100, minimum=1, maximum=500, step=1,
                )
                use_reranker = gr.Checkbox(
                    label="Rerank (BERT)", value=True,
                    info="OFF = SBERT only.",
                )

        # ---- Action row ----
        with gr.Row():
            process_btn = gr.Button("🔍 Screen Resumes", variant="primary", scale=2)
            save_btn = gr.Button("💾 Save Results", variant="secondary", scale=1)
            load_btn = gr.Button("📂 Load Results", variant="secondary", scale=1)
            sort_by_rating_btn = gr.Button("⭐ Sort by Rating", variant="secondary", scale=1)

        processing_banner = gr.Markdown(value="", visible=False)

        # ---- Tabs ----
        with gr.Tabs():
            with gr.Tab("Results & Preview"):
                with gr.Row():
                    with gr.Column(scale=15, min_width=180):
                        results_output = gr.Dataframe(
                            label="Candidates", interactive=False,
                            headers=["Candidate Name", "⭐"],
                            column_widths=["auto", "40px"],
                            wrap=True,
                            elem_classes=["name-table"],
                        )
                    with gr.Column(scale=85):
                        with gr.Row():
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot1_title = gr.Markdown("### Preview Slot 1")
                                    clear1_btn = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot1_stars = make_star_row()
                                slot1_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 1")
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot2_title = gr.Markdown("### Preview Slot 2")
                                    clear2_btn = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot2_stars = make_star_row()
                                slot2_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 2")
                        preview_status = gr.Markdown("")
                summary_output = gr.Markdown(label="Summary")

            with gr.Tab("Help"):
                gr.Markdown(f"""
                ### How to use
                1. Select a folder containing PDF/DOCX resumes
                2. Upload the job description (PDF or DOCX)
                3. Toggle **Rerank with Cross-Encoder** ON/OFF
                4. Click **🔍 Screen Resumes**
                5. **Click any Candidate Name** to load their highlighted PDF into the first **empty** preview slot.
                6. Click the **★ stars** under a preview to rate that candidate 1–10.
                7. Click **⭐ Sort by Rating** to toggle sorting the table by your ratings.
                8. Use **Open in new tab ↗** under a preview to open the highlighted resume
                9. Use **✖ Clear** to reset a slot
                10. Click **💾 Save Results** to save the whole run to the local database
                11. Click **📂 Load Results** to reopen a previously-saved run (or delete it)

                ### Persistence
                - Saved runs live in `./data/results.db` with their resume PDFs
                  snapshotted under `./data/runs/<run_id>/`.
                - Loading a run restores the full table, keywords, and your star ratings,
                  so every feature (filter, sort, preview, rate, save-as-CSV) works as usual.

                ### Keyword filtering
                - Type comma-separated keywords and click **➕ Add keywords** (max {MAX_FILTER_KEYWORDS}).
                - Results are filtered to candidates whose preprocessed resume text contains at least one keyword.
                - **Uncheck** a keyword to temporarily disable it.
                - Filter chips scroll horizontally — use **◀ ▶** to scroll, or drag the slim scrollbar.
                - Click **✖ Clear** to start over.
                """)

        # ---- Modal dialogs ----
        (save_dialog, save_name_input, save_confirm_btn,
         save_csv_btn, save_cancel_btn, save_dialog_status) = build_save_dialog()

        (load_dialog, load_radio, load_confirm_btn,
         load_delete_btn, load_cancel_btn, load_dialog_status) = build_load_dialog()

        # ---- Event wiring ----

        process_btn.click(
            fn=lambda: gr.update(
                value="⏳ **Screening resumes…** This can take a minute depending on file count and whether reranking is ON.",
                visible=True,
            ),
            inputs=None, outputs=[processing_banner],
        ).then(
            fn=process_resumes,
            inputs=[resume_dir, jd_file, top_n, use_reranker],
            outputs=[
                results_output, full_results_state, view_state,
                slot1_html, slot1_state,
                slot2_html, slot2_state,
                active_slot_state,
                summary_output,
                slot1_title, slot2_title,
                keyword_choices_state, active_filters_cb,
                ratings_state, sort_by_rating_state, sort_by_rating_btn,
                *slot1_stars, *slot2_stars,
            ],
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=None, outputs=[processing_banner],
        )

        # ---- Save flow ----
        save_btn.click(
            fn=open_save_dialog,
            inputs=[full_results_state],
            outputs=[save_dialog, save_name_input, save_dialog_status],
        )
        save_confirm_btn.click(
            fn=save_to_db,
            inputs=[save_name_input, full_results_state, ratings_state, summary_output],
            outputs=[save_dialog, save_dialog_status, save_name_input],
        )
        save_csv_btn.click(
            fn=save_csv_only,
            inputs=[full_results_state, ratings_state],
            outputs=[save_dialog_status],
        )
        save_cancel_btn.click(
            fn=cancel_save_dialog,
            inputs=None, outputs=[save_dialog, save_dialog_status],
        )

        # ---- Load flow ----
        load_btn.click(
            fn=open_load_dialog,
            inputs=None,
            outputs=[load_dialog, load_radio, load_dialog_status],
        )
        load_confirm_btn.click(
            fn=load_selected_run,
            inputs=[load_radio],
            outputs=[
                results_output, full_results_state, view_state,
                slot1_html, slot1_state,
                slot2_html, slot2_state,
                active_slot_state,
                summary_output,
                slot1_title, slot2_title,
                keyword_choices_state, active_filters_cb,
                ratings_state, sort_by_rating_state, sort_by_rating_btn,
                *slot1_stars, *slot2_stars,
                load_dialog, load_dialog_status,
            ],
        )
        load_delete_btn.click(
            fn=delete_selected_run,
            inputs=[load_radio],
            outputs=[load_radio, load_dialog_status],
        )
        load_cancel_btn.click(
            fn=cancel_load_dialog,
            inputs=None, outputs=[load_dialog, load_dialog_status],
        )

        # ---- Existing flows ----
        sort_by_rating_btn.click(
            fn=toggle_sort,
            inputs=[sort_by_rating_state, full_results_state,
                    active_filters_cb, ratings_state],
            outputs=[sort_by_rating_state, results_output, view_state, sort_by_rating_btn],
        )

        add_filters_btn.click(
            fn=add_keywords,
            inputs=[keyword_choices_state, active_filters_cb, filter_keywords_input],
            outputs=[
                keyword_choices_state, active_filters_cb,
                filter_keywords_input, filter_status,
            ],
        )
        active_filters_cb.change(
            fn=on_filters_changed,
            inputs=[full_results_state, active_filters_cb,
                    sort_by_rating_state, ratings_state],
            outputs=[results_output, view_state],
        )
        clear_filters_btn.click(
            fn=clear_all_filters,
            inputs=[full_results_state, sort_by_rating_state, ratings_state],
            outputs=[
                keyword_choices_state, active_filters_cb,
                filter_status, results_output, view_state,
            ],
        )

        scroll_left_btn.click(fn=None, js=SCROLL_LEFT_JS, queue=False)
        scroll_right_btn.click(fn=None, js=SCROLL_RIGHT_JS, queue=False)

        results_output.select(
            fn=on_row_select,
            inputs=[view_state, slot1_state, slot2_state,
                    active_slot_state, ratings_state],
            outputs=[
                slot1_html, slot1_state, slot2_html, slot2_state,
                active_slot_state, preview_status, slot1_title, slot2_title,
                *slot1_stars, *slot2_stars,
            ],
        )

        clear1_btn.click(
            fn=clear_slot1,
            inputs=[slot1_state, slot2_state, active_slot_state],
            outputs=[slot1_html, slot1_state, active_slot_state,
                     preview_status, slot1_title, *slot1_stars],
        )
        clear2_btn.click(
            fn=clear_slot2,
            inputs=[slot1_state, slot2_state, active_slot_state],
            outputs=[slot2_html, slot2_state, active_slot_state,
                     preview_status, slot2_title, *slot2_stars],
        )

        def _bind_stars(buttons, handler, slot_state_ref):
            for i, btn in enumerate(buttons, start=1):
                def make_fn(sv, _h=handler):
                    def fn(slot_val, ratings, full_results_df,
                           active_filters_cb, sort_by_rating_state):
                        return _h(sv, slot_val, ratings, full_results_df,
                                  active_filters_cb, sort_by_rating_state)

                    return fn

                btn.click(
                    fn=make_fn(i),
                    inputs=[slot_state_ref, ratings_state, full_results_state,
                            active_filters_cb, sort_by_rating_state],
                    outputs=[ratings_state, results_output, view_state, *buttons],
                )

        _bind_stars(slot1_stars, on_star_click_slot1, slot1_state)
        _bind_stars(slot2_stars, on_star_click_slot2, slot2_state)

    return interface


if __name__ == "__main__":
    interface = create_gradio_interface()
    interface.launch(
        share=False, server_name="0.0.0.0", server_port=7860,
        allowed_paths=[os.getcwd(), tempfile.gettempdir()],
        show_error=True,
    )
