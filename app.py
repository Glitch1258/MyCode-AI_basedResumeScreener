"""app.py — Gradio entry point for the Resume Screening System."""
import logging
import os
import tempfile
from ui_styles import CSS, SCROLL_LEFT_JS, SCROLL_RIGHT_JS
import gradio as gr

from callbacks import (
    process_resumes, save_results, on_row_select,
    clear_slot1, clear_slot2,
)
from filter_callbacks import add_keywords, on_filters_changed, clear_all_filters
from pdf_viewer import cleanup_old_highlights
from resume_filter import MAX_FILTER_KEYWORDS
from ui_helpers import EMPTY_PREVIEW_HTML

logger = logging.getLogger(__name__)


def create_gradio_interface():
    try:
        n = cleanup_old_highlights()
        if n:
            logger.info(f"Cleaned up {n} old highlight PDF(s) from previous sessions.")
    except Exception as e:
        logger.warning(f"Temp cleanup failed (non-fatal): {e}")

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

        # ---- Top inline row (30vh total) ----
        # Order: resume | filter block | jd | top-N
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
                    add_filters_btn   = gr.Button("➕ Add keywords", size="sm", variant="secondary", scale=3)
                    clear_filters_btn = gr.Button("✖ Clear", size="sm", variant="stop", scale=2)
                    scroll_left_btn   = gr.Button("◀", size="sm", scale=0, min_width=34, elem_classes=["scroll-arrow"])
                    scroll_right_btn  = gr.Button("▶", size="sm", scale=0, min_width=34, elem_classes=["scroll-arrow"])
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
            save_btn    = gr.Button("💾 Save Results",   variant="secondary", scale=1)

        processing_banner = gr.Markdown(value="", visible=False)

        # ---- Tabs ----
        with gr.Tabs():
            with gr.Tab("Results & Preview"):
                with gr.Row():
                    with gr.Column(scale=15, min_width=140):
                        results_output = gr.Dataframe(
                            label="Candidates", interactive=False,
                            headers=["Candidate Name"], wrap=True,
                            elem_classes=["name-table"],
                        )
                    with gr.Column(scale=85):
                        with gr.Row():
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot1_title = gr.Markdown("### Preview Slot 1")
                                    clear1_btn  = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot1_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 1")
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot2_title = gr.Markdown("### Preview Slot 2")
                                    clear2_btn  = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot2_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 2")
                        preview_status = gr.Markdown("")
                summary_output = gr.Markdown(label="Summary")
                save_status    = gr.Textbox(label="Save Status", interactive=False)

            with gr.Tab("Help"):
                gr.Markdown(f"""
                ### How to use
                1. Select a folder containing PDF/DOCX resumes
                2. Upload the job description (PDF or DOCX)
                3. Toggle **Rerank with Cross-Encoder** ON/OFF
                4. Click **🔍 Screen Resumes**
                5. **Click any Candidate Name** to load their highlighted PDF into the first **empty** preview slot.
                6. Use **Open in new tab ↗** under a preview to open the highlighted resume
                7. Use **✖ Clear** to reset a slot
                8. Click **💾 Save Results** to export the full CSV

                ### Keyword filtering
                - Type comma-separated keywords and click **➕ Add keywords** (max {MAX_FILTER_KEYWORDS}).
                - Results are filtered to candidates whose preprocessed resume text contains at least one keyword.
                - **Uncheck** a keyword to temporarily disable it.
                - Filter chips scroll horizontally — use **◀ ▶** to scroll, or drag the slim scrollbar.
                - Click **✖ Clear** to start over.
                """)

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
            ],
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=None, outputs=[processing_banner],
        )

        save_btn.click(fn=save_results, inputs=[full_results_state], outputs=[save_status])

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
            inputs=[full_results_state, active_filters_cb],
            outputs=[results_output, view_state],
        )

        clear_filters_btn.click(
            fn=clear_all_filters,
            inputs=[full_results_state],
            outputs=[
                keyword_choices_state, active_filters_cb,
                filter_status, results_output, view_state,
            ],
        )

        # Scroll chips — pure client-side, no queue
        scroll_left_btn.click(fn=None, js=SCROLL_LEFT_JS,  queue=False)
        scroll_right_btn.click(fn=None, js=SCROLL_RIGHT_JS, queue=False)

        results_output.select(
            fn=on_row_select,
            inputs=[view_state, slot1_state, slot2_state, active_slot_state],
            outputs=[
                slot1_html, slot1_state, slot2_html, slot2_state,
                active_slot_state, preview_status, slot1_title, slot2_title,
            ],
        )

        # Clear slots — pass BOTH slot states so the callback can delete the file
        clear1_btn.click(
            fn=clear_slot1,
            inputs=[slot1_state, slot2_state, active_slot_state],
            outputs=[slot1_html, slot1_state, active_slot_state, preview_status, slot1_title],
        )
        clear2_btn.click(
            fn=clear_slot2,
            inputs=[slot1_state, slot2_state, active_slot_state],
            outputs=[slot2_html, slot2_state, active_slot_state, preview_status, slot2_title],
        )

    return interface


if __name__ == "__main__":
    interface = create_gradio_interface()
    interface.launch(
        share=False, server_name="0.0.0.0", server_port=7860,
        allowed_paths=[os.getcwd(), tempfile.gettempdir()],
        show_error=True,
    )