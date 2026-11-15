"""results_store.py — SQLite persistence for screening results. No Gradio imports.

Layout:
    ./data/results.db            — one SQLite DB (single-user; WAL enabled)
    ./data/runs/<uuid>/          — per-run snapshot of every resume PDF used

A "run" captures everything needed to restore the app to its post-screening
state: the full results DataFrame (all columns + row_id), per-row keyword lists,
per-row preprocessed texts, the ratings dict, and the summary markdown. PDFs are
copied on save so loading a run works even if the original uploads were temp.
"""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getcwd()) / "data"
RUNS_DIR = DATA_DIR / "runs"
DB_PATH = DATA_DIR / "results.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Connection / schema
# --------------------------------------------------------------------------- #
@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db() -> None:
    with _connect() as conn:
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS screenings
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         name
                         TEXT
                         NOT
                         NULL
                         UNIQUE,
                         created_at
                         TEXT
                         NOT
                         NULL,
                         summary
                         TEXT,
                         results_json
                         TEXT
                         NOT
                         NULL,
                         full_keywords_json
                         TEXT,
                         processed_texts_json
                         TEXT,
                         ratings_json
                         TEXT,
                         folder_path
                         TEXT
                     )
                     """)


_init_db()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def list_runs() -> List[Dict]:
    """Return [{id, name, created_at, n_candidates}, ...] newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, results_json FROM screenings "
            "ORDER BY created_at DESC"
        ).fetchall()
    out = []
    for rid, name, created_at, results_json in rows:
        try:
            n = len(json.loads(results_json))
        except Exception:
            n = 0
        out.append({"id": rid, "name": name,
                    "created_at": created_at, "n_candidates": n})
    return out


def save_run(name: str, full_results_df: pd.DataFrame,
             ratings: Dict[str, int], summary: str) -> Dict:
    """Persist a run + its PDFs. Replaces any existing run with the same name."""
    name = (name or "").strip()
    if not name:
        return {"ok": False, "id": None, "message": "Please enter a name."}
    if full_results_df is None or full_results_df.empty:
        return {"ok": False, "id": None, "message": "Nothing to save."}

    run_uuid = uuid.uuid4().hex
    folder = RUNS_DIR / run_uuid
    folder.mkdir(parents=True, exist_ok=True)

    # Copy PDFs and rewrite "PDF Path" in a working copy
    df = full_results_df.copy()
    path_to_new: Dict[str, str] = {}
    for i in range(len(df)):
        src = str(df.at[i, "PDF Path"])
        if src in path_to_new:
            df.at[i, "PDF Path"] = path_to_new[src]
            continue
        src_path = Path(src)
        if not src_path.exists():
            path_to_new[src] = src
            continue
        dest = folder / src_path.name
        if dest.exists():
            dest = folder / f"{i}_{src_path.name}"
        try:
            shutil.copyfile(src_path, dest)
            path_to_new[src] = str(dest)
            df.at[i, "PDF Path"] = str(dest)
        except Exception as e:
            logger.warning(f"Could not copy {src}: {e}")
            path_to_new[src] = src

    try:
        results_json = df.to_json(orient="records")
    except Exception as e:
        shutil.rmtree(folder, ignore_errors=True)
        return {"ok": False, "id": None, "message": f"Serialization error: {e}"}

    full_keywords_json = json.dumps(full_results_df.attrs.get("full_keywords", []))
    processed_texts_json = json.dumps(full_results_df.attrs.get("processed_texts", []))

    # Ratings are keyed by PDF path. Since we just copied every PDF to a new
    # location and rewrote df["PDF Path"], the ratings dict has to be remapped
    # to the same new keys, or load_run() will fail to match them.
    remapped_ratings: Dict[str, int] = {}
    for old_path, value in (ratings or {}).items():
        new_path = path_to_new.get(str(old_path), str(old_path))
        remapped_ratings[new_path] = value
    ratings_json = json.dumps(remapped_ratings)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT id, folder_path FROM screenings WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                old_id, old_folder = existing
                conn.execute("DELETE FROM screenings WHERE id = ?", (old_id,))
                if old_folder and Path(old_folder).exists():
                    shutil.rmtree(old_folder, ignore_errors=True)

            cur = conn.execute(
                """INSERT INTO screenings
                   (name, created_at, summary, results_json,
                    full_keywords_json, processed_texts_json, ratings_json,
                    folder_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, created_at, summary or "", results_json,
                 full_keywords_json, processed_texts_json, ratings_json,
                 str(folder)),
            )
            new_id = cur.lastrowid
    except Exception as e:
        logger.exception("DB save failed")
        shutil.rmtree(folder, ignore_errors=True)
        return {"ok": False, "id": None, "message": f"DB error: {e}"}

    return {"ok": True, "id": new_id,
            "message": f"Saved '{name}' ({len(df)} candidates)."}


def load_run(run_id: int) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute(
            """SELECT id,
                      name,
                      created_at,
                      summary,
                      results_json,
                      full_keywords_json,
                      processed_texts_json,
                      ratings_json
               FROM screenings
               WHERE id = ?""", (run_id,)
        ).fetchone()
    if row is None:
        return None

    (rid, name, created_at, summary,
     results_json, fk_json, pt_json, ratings_json) = row

    try:
        df = pd.read_json(io.StringIO(results_json), orient="records")
    except Exception as e:
        logger.error(f"Could not parse results JSON: {e}")
        return None

    df.attrs["full_keywords"] = json.loads(fk_json) if fk_json else []
    df.attrs["processed_texts"] = json.loads(pt_json) if pt_json else []
    try:
        ratings = json.loads(ratings_json) if ratings_json else {}
    except Exception:
        ratings = {}

    return {"id": rid, "name": name, "created_at": created_at,
            "summary": summary or "", "results_df": df, "ratings": ratings}


def delete_run(run_id: int) -> Dict:
    with _connect() as conn:
        row = conn.execute(
            "SELECT folder_path FROM screenings WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return {"ok": False, "message": "Run not found."}
        conn.execute("DELETE FROM screenings WHERE id = ?", (run_id,))
    folder = row[0]
    if folder and Path(folder).exists():
        shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True, "message": "Deleted."}
