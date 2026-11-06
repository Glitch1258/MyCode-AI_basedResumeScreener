"""ui_helpers.py — HTML builders and constants for the Gradio UI."""
import os


EMPTY_PREVIEW_HTML = (
    "<div style='display:flex;align-items:center;justify-content:center;"
    "height:100%;min-height:600px;border:2px dashed #bbb;border-radius:8px;"
    "color:#888;font-size:14px;'>Empty slot — click a candidate to preview</div>"
)


def pdf_iframe_html(highlighted_path: str, original_path: str, height: int = 620) -> str:
    """
    Build the inline preview HTML for one slot.
    The <iframe> src and the 'Open in new tab' link both point at the
    highlighted copy. original_path is only kept so the slot state shape
    stays the same; it is used elsewhere for the slot title.
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


def slot_from_state(slot, slot_num: int):
    """
    slot is None or (highlighted_path, original_path).
    Returns (html, title_markdown).
    """
    if not slot:
        return EMPTY_PREVIEW_HTML, f"### Preview Slot {slot_num}"
    try:
        highlighted, original = slot
    except Exception:
        return EMPTY_PREVIEW_HTML, f"### Preview Slot {slot_num}"
    html = pdf_iframe_html(highlighted, original)
    title = f"### Preview Slot {slot_num}: {os.path.basename(original)}"
    return html, title