import logging
import os
import shutil
import tempfile
import pandas as pd
import gradio as gr
from datetime import datetime

from resume_screener import ResumeScreeningSystem
from pdf_viewer import (
    highlight_keywords_in_pdf,
    cleanup_old_highlights,
    get_keywords_for_row,
)

logger = logging.getLogger(__name__)

EMPTY_PREVIEW_HTML = (
    "<div style='display:flex;align-items:center;justify-content:center;"
    "height:100%;min-height:600px;border:2px dashed #bbb;border-radius:8px;"
    "color:#888;font-size:14px;'>Empty slot — click a candidate to preview</div>"
)


def create_gradio_interface():
    """Create the Gradio UI interface."""

    system = None

    try:
        n = cleanup_old_highlights()
        if n:
            logger.info(f"Cleaned up {n} old highlight PDF(s) from previous sessions.")
    except Exception as e:
        logger.warning(f"Temp cleanup failed (non-fatal): {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pdf_iframe_html(highlighted_path: str, original_path: str, height: int = 620) -> str:
        """
        Build the inline preview HTML for one slot.

        - The <iframe> src points at the HIGHLIGHTED copy.
        - The "Open in new tab" link ALSO points at the HIGHLIGHTED copy.
          (original_path is kept in the signature only so the slot state
          shape stays the same; it is not used for the link target.)
        """
        iframe_url = f"/gradio_api/file={highlighted_path}"
        link_url = f"/gradio_api/file={highlighted_path}"
        return f"""
        <div style="width:100%;height:{height}px;">
          <iframe src="{iframe_url}"
                  style="width:100%;height:100%;border:1px solid #ddd;border-radius:6px;"
                  title="Highlighted PDF"></iframe>
        </div>
        <p style="margin-top:6px;">
          <a href="{link_url}" target="_blank" rel="noopener">Open in new tab ↗</a>
        </p>
        """

    def _slot_from_state(slot, slot_num: int):
        """
        Given a slot state value (None or (highlighted_path, original_path)),
        return (html, title_markdown).

        The title uses `original_path` so it shows the candidate's actual
        resume filename (e.g. "DevOpsEngineer1.pdf"), not the highlight copy.
        """
        if not slot:
            return EMPTY_PREVIEW_HTML, f"### Preview Slot {slot_num}"
        try:
            highlighted, original = slot
        except Exception:
            return EMPTY_PREVIEW_HTML, f"### Preview Slot {slot_num}"
        html = _pdf_iframe_html(highlighted, original)
        title = f"### Preview Slot {slot_num}: {os.path.basename(original)}"
        return html, title

    # ------------------------------------------------------------------
    # Callback: screen resumes
    # ------------------------------------------------------------------
    def process_resumes(resume_dir, jd_file, top_n, use_reranker, progress=gr.Progress()):
        # Outputs (10):
        #   display_df, full_results_state,
        #   slot1_html, slot1_state,
        #   slot2_html, slot2_state,
        #   active_slot_state,
        #   summary,
        #   slot1_title, slot2_title
        def _empty_return(msg):
            return (
                pd.DataFrame(columns=["Candidate Name"]),
                None,
                EMPTY_PREVIEW_HTML,
                None,
                EMPTY_PREVIEW_HTML,
                None,
                1,
                msg,
                "### Preview Slot 1",
                "### Preview Slot 2",
            )

        if not resume_dir or not jd_file:
            return _empty_return("⚠️ Please select a resume folder and a job description file.")

        try:
            progress(0.0, desc="Initializing system...")
            nonlocal system
            system = ResumeScreeningSystem(top_n=int(top_n))

            progress(0.1, desc="Reading job description...")

            def _path(f):
                return f.name if hasattr(f, "name") else f

            jd_path = _path(jd_file)
            job_description = system.extract_text_from_file(jd_path)
            if not job_description:
                return _empty_return("❌ Could not extract text from job description file.")

            resume_items = resume_dir if isinstance(resume_dir, list) else [resume_dir]
            resume_paths = [
                _path(f) for f in resume_items
                if str(_path(f)).lower().endswith((".pdf", ".docx"))
            ]
            file_count = len(resume_paths)

            if file_count == 0:
                return _empty_return("⚠️ No PDF/DOCX files found in the selected folder.")

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
               Click any **Candidate Name** to load it into one of the two preview slots.
               Each new click alternates between the two slots.
               Use **Open in new tab ↗** under a preview to open the highlighted
               resume in a new browser tab.
               """

            progress(1.0, desc="Complete!")

            display_df = results_df[["Candidate Name"]].copy()

            return (
                display_df,
                results_df,
                EMPTY_PREVIEW_HTML,
                None,
                EMPTY_PREVIEW_HTML,
                None,
                1,
                summary,
                "### Preview Slot 1",
                "### Preview Slot 2",
            )

        except Exception as e:
            logger.error(f"Error in processing: {e}")
            return _empty_return(f"❌ Error: {str(e)}")

    # ------------------------------------------------------------------
    # Callback: save full results to CSV
    # ------------------------------------------------------------------
    def save_results(full_results_df):
        if full_results_df is None or full_results_df.empty:
            return "No results to save."

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_screening_results_{timestamp}.csv"
        to_save = full_results_df.drop(columns=["row_id"], errors="ignore")
        to_save.to_csv(filename, index=False)
        return f"Results saved to {filename} (full data with all columns)"

    # ------------------------------------------------------------------
    # Row click → rotate slots
    # ------------------------------------------------------------------
    def on_row_select(full_results_df, slot1, slot2, active_slot, evt: gr.SelectData):
        """
        active_slot is 1 or 2 — the slot that will receive the next PDF.
        The other slot keeps its current content visible (no wipe).

        slot1 / slot2 are None or (highlighted_path, original_path).

        Outputs (8):
            slot1_html, slot1_state,
            slot2_html, slot2_state,
            active_slot_state,
            preview_status,
            slot1_title, slot2_title
        """
        print(f">>> ROW SELECT FIRED. evt.index = {evt.index} active_slot={active_slot}")

        def _unchanged(msg=""):
            return (
                gr.update(), slot1,
                gr.update(), slot2,
                active_slot,
                msg,
                gr.update(),
                gr.update(),
            )

        if full_results_df is None or getattr(full_results_df, "empty", True):
            return _unchanged("")

        try:
            row = int(evt.index[0]) if isinstance(evt.index, (list, tuple)) else int(evt.index)
        except Exception:
            return _unchanged("")

        if row < 0 or row >= len(full_results_df):
            return _unchanged("")

        pdf_path, keywords, candidate_name = get_keywords_for_row(full_results_df, row)
        try:
            full_kw_lists = full_results_df.attrs.get("full_keywords")
            if full_kw_lists is not None and row < len(full_kw_lists):
                keywords = full_kw_lists[row]
        except Exception:
            pass

        if not pdf_path:
            return _unchanged("No PDF path for this candidate.")

        # Highlight (fallback to original on error)
        try:
            highlighted_path = highlight_keywords_in_pdf(pdf_path, keywords)
        except Exception as e:
            logger.error(f"Highlight failed: {e}")
            highlighted_path = pdf_path

        # Copy highlighted PDF into CWD so it is inside allowed_paths
        local_preview = os.path.join(os.getcwd(), os.path.basename(highlighted_path))
        try:
            shutil.copyfile(highlighted_path, local_preview)
        except Exception:
            local_preview = highlighted_path

        # Each slot stores (highlighted_path, original_path)
        new_slot_value = (local_preview, pdf_path)

        if active_slot == 1:
            new_s1, new_s2 = new_slot_value, slot2
            new_active = 2
        else:
            new_s1, new_s2 = slot1, new_slot_value
            new_active = 1

        html1, title1 = _slot_from_state(new_s1, 1)
        html2, title2 = _slot_from_state(new_s2, 2)

        status = (
            f"Loaded **{candidate_name}** into Slot {active_slot} — "
            f"{len(keywords)} keyword(s) highlighted. "
            f"(Next click → Slot {new_active})"
        )

        return (
            gr.update(value=html1),
            new_s1,
            gr.update(value=html2),
            new_s2,
            new_active,
            status,
            title1,
            title2,
        )

    # ------------------------------------------------------------------
    # Manual clear buttons
    # ------------------------------------------------------------------
    def clear_slot1(slot2, active_slot):
        return (
            gr.update(value=EMPTY_PREVIEW_HTML),
            None,
            1,
            "",
            "### Preview Slot 1",
        )

    def clear_slot2(slot1, active_slot):
        return (
            gr.update(value=EMPTY_PREVIEW_HTML),
            None,
            2,
            "",
            "### Preview Slot 2",
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
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
        slot2_state = gr.State(value=None)   # None or (highlighted_path, original_path)
        active_slot_state = gr.State(value=1)

        # ---- Inputs row ----
        with gr.Row():
            with gr.Column(scale=2):
                resume_dir = gr.File(
                    label="Resume Folder (select a folder containing PDF/DOCX files)",
                    file_count="multiple",
                    file_types=[".pdf", ".docx"],
                    height=200,
                )
            with gr.Column(scale=2):
                jd_file = gr.File(
                    label="Job Description File (PDF / DOCX)",
                    file_count="single",
                    file_types=[".pdf", ".docx"],
                )
            with gr.Column(scale=1):
                top_n = gr.Number(
                    label="Top N Candidates", value=100, minimum=1, maximum=500, step=1
                )
                use_reranker = gr.Checkbox(
                    label="Rerank with Cross-Encoder (BERT)",
                    value=True,
                    info="OFF = Sentence-BERT only (faster).",
                )

        with gr.Row():
            process_btn = gr.Button("🔍 Screen Resumes", variant="primary", scale=2)
            save_btn = gr.Button("💾 Save Results", variant="secondary", scale=1)

        processing_banner = gr.Markdown(value="", visible=False)

        # ---- Results & Preview tab ----
        with gr.Tabs():
            with gr.Tab("Results & Preview"):
                with gr.Row():
                    # Left: name table (15%)
                    with gr.Column(scale=15, min_width=140):
                        results_output = gr.Dataframe(
                            label="Candidates",
                            interactive=False,
                            headers=["Candidate Name"],
                            wrap=True,
                            elem_classes=["name-table"],
                        )

                    # Right: two side-by-side preview slots (85%)
                    with gr.Column(scale=85):
                        with gr.Row():
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot1_title = gr.Markdown("### Preview Slot 1")
                                    clear1_btn = gr.Button(
                                        "✖ Clear", variant="stop", size="sm", scale=0
                                    )
                                slot1_html = gr.HTML(
                                    value=EMPTY_PREVIEW_HTML,
                                    label="Preview 1",
                                )
                            with gr.Column(scale=1):
                                with gr.Row():
                                    slot2_title = gr.Markdown("### Preview Slot 2")
                                    clear2_btn = gr.Button(
                                        "✖ Clear", variant="stop", size="sm", scale=0
                                    )
                                slot2_html = gr.HTML(
                                    value=EMPTY_PREVIEW_HTML,
                                    label="Preview 2",
                                )

                        preview_status = gr.Markdown("")

                summary_output = gr.Markdown(label="Summary")
                save_status = gr.Textbox(label="Save Status", interactive=False)

            with gr.Tab("Help"):
                gr.Markdown("""
                ### How to use
                1. Select a folder containing PDF/DOCX resumes
                2. Upload the job description (PDF or DOCX)
                3. Toggle **Rerank with Cross-Encoder** ON/OFF
                4. Click **🔍 Screen Resumes** — a banner and spinner appear while it runs
                5. **Click any Candidate Name** to load their highlighted PDF:
                   - 1st click → Slot 1
                   - 2nd click → Slot 2
                   - 3rd click → Slot 1 (replaces what's there)
                   - 4th click → Slot 2 (replaces what's there)
                   - … and so on. The panel that is **not** the current target keeps
                     showing its previous PDF until the next click replaces it.
                6. Each slot's title shows the **original filename** being previewed
                7. Click **Open in new tab ↗** under a preview to open the highlighted
                   resume in a new browser tab
                8. Use **✖ Clear** on a slot to reset it to the dashed placeholder
                9. Click **💾 Save Results** to export the full CSV
                """)

        # ---- Event wiring ----
        process_btn.click(
            fn=lambda: gr.update(
                value="⏳ **Screening resumes…** This can take a minute depending on file count and whether reranking is ON.",
                visible=True,
            ),
            inputs=None,
            outputs=[processing_banner],
        ).then(
            fn=process_resumes,
            inputs=[resume_dir, jd_file, top_n, use_reranker],
            outputs=[
                results_output,
                full_results_state,
                slot1_html,
                slot1_state,
                slot2_html,
                slot2_state,
                active_slot_state,
                summary_output,
                slot1_title,
                slot2_title,
            ],
        ).then(
            fn=lambda: gr.update(visible=False),
            inputs=None,
            outputs=[processing_banner],
        )

        save_btn.click(fn=save_results, inputs=[full_results_state], outputs=[save_status])

        results_output.select(
            fn=on_row_select,
            inputs=[full_results_state, slot1_state, slot2_state, active_slot_state],
            outputs=[
                slot1_html,
                slot1_state,
                slot2_html,
                slot2_state,
                active_slot_state,
                preview_status,
                slot1_title,
                slot2_title,
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
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
        allowed_paths=[os.getcwd(), tempfile.gettempdir()],
        show_error=True,
    )