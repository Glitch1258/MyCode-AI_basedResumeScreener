"""app.py — Gradio entry point for the Resume Screening System."""
import logging
import os
import tempfile

import gradio as gr

from pdf_viewer import cleanup_old_highlights
from ui_helpers import EMPTY_PREVIEW_HTML
from callbacks import (
    process_resumes, save_results, on_row_select,
    clear_slot1, clear_slot2,
)

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
        css=".name-table { max-height: 760px; overflow-y: auto; }",
        theme=gr.themes.Soft(),
    ) as interface:
        gr.Markdown("""
        # 📄 Resume Screening System
        Select a folder containing PDF/DOCX resumes and a job description file to automatically screen and rank candidates.
        """)

        full_results_state = gr.State(value=None)
        slot1_state = gr.State(value=None)   # None or (highlighted_path, original_path)
        slot2_state = gr.State(value=None)
        active_slot_state = gr.State(value=1)

        with gr.Row():
            with gr.Column(scale=2):
                resume_dir = gr.File(
                    label="Resume Folder (select a folder containing PDF/DOCX files)",
                    file_count="multiple", file_types=[".pdf", ".docx"], height=200,
                )
            with gr.Column(scale=2):
                jd_file = gr.File(
                    label="Job Description File (PDF / DOCX)",
                    file_count="single", file_types=[".pdf", ".docx"],
                )
            with gr.Column(scale=1):
                top_n = gr.Number(
                    label="Top N Candidates", value=100, minimum=1, maximum=500, step=1,
                )
                use_reranker = gr.Checkbox(
                    label="Rerank with Cross-Encoder (BERT)", value=True,
                    info="OFF = Sentence-BERT only (faster).",
                )

        with gr.Row():
            process_btn = gr.Button("🔍 Screen Resumes", variant="primary", scale=2)
            save_btn = gr.Button("💾 Save Results", variant="secondary", scale=1)

        processing_banner = gr.Markdown(value="", visible=False)

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
                                    clear1_btn = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot1_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 1")
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot2_title = gr.Markdown("### Preview Slot 2")
                                    clear2_btn = gr.Button("✖ Clear", variant="stop", size="sm", scale=0)
                                slot2_html = gr.HTML(value=EMPTY_PREVIEW_HTML, label="Preview 2")
                        preview_status = gr.Markdown("")
                summary_output = gr.Markdown(label="Summary")
                save_status = gr.Textbox(label="Save Status", interactive=False)

            with gr.Tab("Help"):
                gr.Markdown("""
                ### How to use
                1. Select a folder containing PDF/DOCX resumes
                2. Upload the job description (PDF or DOCX)
                3. Toggle **Rerank with Cross-Encoder** ON/OFF
                4. Click **🔍 Screen Resumes**
                5. **Click any Candidate Name** to load their highlighted PDF into slots 1 and 2 alternately
                6. Use **Open in new tab ↗** under a preview to open the highlighted resume
                7. Use **✖ Clear** to reset a slot
                8. Click **💾 Save Results** to export the full CSV
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
                results_output, full_results_state,
                slot1_html, slot1_state,
                slot2_html, slot2_state,
                active_slot_state,
                summary_output,
                slot1_title, slot2_title,
            ],
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=None, outputs=[processing_banner],
        )

        save_btn.click(fn=save_results, inputs=[full_results_state], outputs=[save_status])

        results_output.select(
            fn=on_row_select,
            inputs=[full_results_state, slot1_state, slot2_state, active_slot_state],
            outputs=[
                slot1_html, slot1_state, slot2_html, slot2_state,
                active_slot_state, preview_status, slot1_title, slot2_title,
            ],
        )

        clear1_btn.click(
            fn=clear_slot1,
            inputs=[slot2_state, active_slot_state],
            outputs=[slot1_html, slot1_state, active_slot_state, preview_status, slot1_title],
        )
        clear2_btn.click(
            fn=clear_slot2,
            inputs=[slot1_state, active_slot_state],
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