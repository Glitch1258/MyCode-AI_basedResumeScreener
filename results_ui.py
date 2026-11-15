"""results_ui.py — Gradio UI builders for the save/load modal dialogs.

No DB, no callbacks. Returns component handles for results_callbacks.py.
"""
from __future__ import annotations

import gradio as gr


def build_save_dialog():
    """Return (dialog, name_input, confirm_btn, csv_btn, cancel_btn, status_md)."""
    with gr.Column(visible=False, elem_classes=["modal-overlay"]) as dialog:
        with gr.Column(elem_classes=["modal-box"]):
            gr.Markdown("### 💾 Save Screening Results")
            name_input = gr.Textbox(
                label="Name for this run",
                placeholder="e.g. Senior Python Dev — Oct 2025",
                lines=1,
            )
            with gr.Row():
                confirm_btn = gr.Button("Save to Database", variant="primary", scale=2)
                csv_btn = gr.Button("Also save CSV", variant="secondary", scale=1)
                cancel_btn = gr.Button("Cancel", variant="stop", scale=1)
            status_md = gr.Markdown("")
    return dialog, name_input, confirm_btn, csv_btn, cancel_btn, status_md


def build_load_dialog():
    """Return (dialog, radio, load_btn, delete_btn, cancel_btn, status_md)."""
    with gr.Column(visible=False, elem_classes=["modal-overlay"]) as dialog:
        with gr.Column(elem_classes=["modal-box"]):
            gr.Markdown("### 📂 Load Saved Screening")
            radio = gr.Radio(choices=[], label="Saved runs (newest first)")
            with gr.Row():
                load_btn = gr.Button("Load", variant="primary", scale=2)
                delete_btn = gr.Button("🗑 Delete", variant="stop", scale=1)
                cancel_btn = gr.Button("Cancel", variant="secondary", scale=1)
            status_md = gr.Markdown("")
    return dialog, radio, load_btn, delete_btn, cancel_btn, status_md
