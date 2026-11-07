"""resume_filter.py — Pure logic for keyword-based filtering of screening results.

UI-agnostic: no Gradio imports. Implements faceted-search-style keyword filtering
over the *preprocessed* resume text (`processed_text`) — the same text fed to
Sentence-BERT. Benefits:
  - case insensitive (text is lowercased)
  - phrase-aware (multi-word keywords match consecutive tokens)
  - consistent with the ranking model's view of the resume

Limitation: `ResumeScreeningSystem.preprocess_text` drops tokens with len <= 2,
so very short keywords ("AI", "ML", "R") won't match via this path. If you need
those, swap `matches_processed_text` for a `raw_text` regex (see notes at bottom).
"""
from __future__ import annotations

import re
from typing import Iterable, List

import pandas as pd


MAX_FILTER_KEYWORDS = 25


# --------------------------------------------------------------------------- #
# Keyword helpers
# --------------------------------------------------------------------------- #
def normalize_keyword(keyword: str) -> str:
    """Normalized key for dedupe/comparison (preserves display form separately)."""
    return re.sub(r"\s+", " ", str(keyword).lower().strip())


def keyword_tokens(keyword: str) -> List[str]:
    """Tokenize a user keyword with the same character normalization as
    `preprocess_text` (lowercase, non-alnum -> space). We deliberately do NOT
    drop short tokens here — filtering happens via regex word-boundaries."""
    text = str(keyword).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


def clean_keywords(keywords: Iterable[str]) -> List[str]:
    """Dedupe, strip, drop empties; cap at MAX_FILTER_KEYWORDS.
    Preserves the user's original spelling/case for display."""
    seen: set[str] = set()
    out: List[str] = []
    for kw in keywords:
        if kw is None:
            continue
        kw = str(kw).strip()
        if len(kw) < 2:
            continue
        key = normalize_keyword(kw)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(kw)
        if len(out) >= MAX_FILTER_KEYWORDS:
            break
    return out


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
def matches_processed_text(processed_text: str, keyword: str) -> bool:
    """True iff `keyword` appears in `processed_text` (space-joined tokens).

    Word boundaries prevent false positives ("art" inside "start").
    Multi-word keywords must appear as consecutive tokens.
    """
    if not processed_text:
        return False
    tokens = keyword_tokens(keyword)
    if not tokens:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(t) for t in tokens) + r"\b"
    return re.search(pattern, processed_text) is not None


# --------------------------------------------------------------------------- #
# Main filtering
# --------------------------------------------------------------------------- #
def filter_results_df(
    full_results_df: pd.DataFrame,
    keywords: List[str],
    *,
    require_all: bool = False,
) -> pd.DataFrame:
    """Filter results by keywords. Any-match by default (faceted-search style).

    Matching uses ``full_results_df.attrs['processed_texts']``. Returns a
    fresh DataFrame (never mutates the input) with all original columns and
    attrs preserved, so row_id lookups and highlighting keep working.
    """
    if full_results_df is None:
        return pd.DataFrame()

    keywords = clean_keywords(keywords)

    df = full_results_df.copy()
    for k, v in full_results_df.attrs.items():
        df.attrs[k] = v

    if not keywords:
        return df

    processed_texts = df.attrs.get("processed_texts")
    if processed_texts is None:
        return _fallback_filter(df, keywords, require_all)

    n = len(df)
    pts = list(processed_texts)
    if len(pts) < n:
        pts = pts + [""] * (n - len(pts))

    row_ids = (
        df["row_id"].astype(int).tolist()
        if "row_id" in df.columns
        else list(range(n))
    )
    keep_mask: List[bool] = []
    for rid in row_ids:
        text = pts[rid] if 0 <= rid < len(pts) else ""
        if require_all:
            ok = all(matches_processed_text(text, kw) for kw in keywords)
        else:
            ok = any(matches_processed_text(text, kw) for kw in keywords)
        keep_mask.append(ok)

    filtered = df[keep_mask].reset_index(drop=True)
    for k, v in full_results_df.attrs.items():
        filtered.attrs[k] = v
    return filtered


def _fallback_filter(df: pd.DataFrame, keywords: List[str], require_all: bool) -> pd.DataFrame:
    """Best-effort filter on results produced before `processed_texts` existed."""
    if "Extracted Keywords" not in df.columns:
        return df
    norm_kws = [normalize_keyword(k) for k in keywords]
    keep = []
    for val in df["Extracted Keywords"].fillna("").astype(str):
        hay = normalize_keyword(val)
        ok = all(kw in hay for kw in norm_kws) if require_all else any(kw in hay for kw in norm_kws)
        keep.append(ok)
    out = df[keep].reset_index(drop=True)
    for k, v in df.attrs.items():
        out.attrs[k] = v
    return out

# If you ever want raw_text-based matching instead, replace matches_processed_text with:
#     def matches_raw_text(raw_text: str, keyword: str) -> bool:
#         if not raw_text:
#             return False
#         # word-boundary, case-insensitive, tolerant of punctuation around keyword
#         pat = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
#         return re.search(pat, raw_text, flags=re.IGNORECASE) is not None