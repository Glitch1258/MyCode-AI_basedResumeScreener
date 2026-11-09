"""
pdf_viewer.py

Standalone helpers for:
  - Highlighting keywords inside a real PDF (using PyMuPDF / fitz).
  - Producing a temp PDF that Gradio's gr.PDF component can render.

No Gradio imports here on purpose — this module is UI-agnostic and testable.

Requires:
    pip install pymupdf
"""

from __future__ import annotations

import re
import tempfile
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pymupdf as fitz  # PyMuPDF (avoids the deprecated `fitz` shim)

# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------

_TEMP_DIR = Path(tempfile.gettempdir()) / "resume_screener_highlights"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, keep alnum + spaces. Used for fuzzy compare."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_keywords(keywords: Iterable[str]) -> List[str]:
    """
    De-duplicate, drop empties/short tokens, keep multi-word phrases.

    RAKE returns phrases like "machine learning", "python", "data analysis".
    We keep them as-is (fitz.search_for is literal) but filter junk.
    """
    seen = set()
    out: List[str] = []
    for kw in keywords:
        if not kw:
            continue
        kw = kw.strip()
        if len(kw) < 2:
            continue
        key = _normalize(kw)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(kw)
    return out


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def highlight_keywords_in_pdf(
        pdf_path: str,
        keywords: Iterable[str],
        *,
        max_keywords: int = 40,
        color: Tuple[float, float, float] = (1.0, 0.9, 0.0),  # yellow-ish
        open_result: bool = False,
) -> str:
    """
    Open `pdf_path`, highlight every occurrence of each keyword, and return
    the path of a NEW temp PDF with highlights baked in.

    Args:
        pdf_path:      source PDF
        keywords:      list of keyword strings (e.g. from RAKE)
        max_keywords:  safety cap so we don't blow up on huge lists
        color:         RGB 0..1 highlight color
        open_result:   if True, opens the resulting PDF (debugging only)

    Returns:
        Absolute path to the highlighted temp PDF.

    Raises:
        FileNotFoundError: if source PDF doesn't exist
        RuntimeError:      if PyMuPDF fails to open or save

    Notes:
        - Scanned / image-only PDFs will produce ZERO highlights (no text layer).
        - Keywords that don't literally appear in the PDF produce no highlight.
        - Highlight annotations are added via page.add_highlight_annot(rect),
          which is a standard PDF annotation — opens in any viewer.
    """
    src = Path(pdf_path)
    if not src.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    kws = _clean_keywords(keywords)[:max_keywords]

    try:
        doc = fitz.open(str(src))
    except Exception as e:
        raise RuntimeError(f"Could not open PDF {pdf_path}: {e}") from e

    total_hits = 0
    try:
        for kw in kws:
            for page in doc:
                try:
                    rects = page.search_for(kw, quads=False)
                except Exception:
                    rects = []
                for rect in rects:
                    try:
                        annot = page.add_highlight_annot(rect)
                        annot.set_colors(stroke=color)
                        annot.update()
                        total_hits += 1
                    except Exception:
                        # Non-fatal — skip bad rects
                        continue

        out_name = f"highlight_{uuid.uuid4().hex[:10]}_{src.stem}.pdf"
        out_path = _TEMP_DIR / out_name
        doc.save(str(out_path), garbage=3, deflate=True)
    finally:
        doc.close()

    if open_result:
        try:
            import webbrowser
            webbrowser.open(out_path.as_uri())
        except Exception:
            pass

    # Optional: log how many hits we got (useful when wiring up)
    print(f"[pdf_viewer] Highlighted {total_hits} occurrence(s) "
          f"across {len(kws)} keyword(s) → {out_path}")

    return str(out_path)


def cleanup_old_highlights(max_age_seconds: int = 3600) -> int:
    """
    Delete highlight temp files older than `max_age_seconds`.
    Call this occasionally (e.g. on app start) so /tmp doesn't fill up.

    Returns number of files deleted.
    """
    import os
    import time

    now = time.time()
    deleted = 0
    for f in _TEMP_DIR.glob("highlight_*.pdf"):
        try:
            if now - f.stat().st_mtime > max_age_seconds:
                os.remove(f)
                deleted += 1
        except OSError:
            continue
    return deleted


def get_keywords_for_row(
        full_results_df,
        row_index: int,
        *,
        keyword_column: str = "Extracted Keywords",
) -> Tuple[Optional[str], List[str], Optional[str]]:
    """
    Given the full results DataFrame (the hidden one in gr.State) and a row
    index (0-based), return (pdf_path, keywords_list, candidate_name).

    Handles the 'Extracted Keywords' column being a comma-joined string.
    Returns (None, [], None) if the row is invalid.
    """
    if full_results_df is None or not hasattr(full_results_df, "iloc"):
        return None, [], None
    if row_index < 0 or row_index >= len(full_results_df):
        return None, [], None

    row = full_results_df.iloc[row_index]
    pdf_path = row.get("PDF Path")
    name = row.get("Candidate Name")

    raw_kw = row.get(keyword_column, "") or ""
    if isinstance(raw_kw, (list, tuple)):
        keywords = [str(k) for k in raw_kw]
    else:
        keywords = [k.strip() for k in str(raw_kw).split(",") if k.strip()]

    return pdf_path, keywords, name
