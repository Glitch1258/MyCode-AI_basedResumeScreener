import pandas as pd
import re
from fpdf import FPDF
import os

# ── 1. Load the dataset ──────────────────────────────────────────────
df = pd.read_csv("resume_dataset.csv")

# ── 2. Categories to export ──────────────────────────────────────────
target_categories = [
    "Data Science",
    "Web Designing",
    "Java Developer",
    "Python Developer",
    "DevOps Engineer",
    "Database",
    "Hadoop",
    "DotNet Developer",
]

# ── 3. Create output folder ──────────────────────────────────────────
output_dir = "resume_pdfs"
os.makedirs(output_dir, exist_ok=True)


# ── 4. Helper: sanitize text so FPDF (latin-1) won't crash ───────────
def sanitize(text: str) -> str:
    """
    FPDF's core fonts only support latin-1. Replace / drop anything else.
    Also normalise common encoding artefacts seen in the CSV.
    """
    if not isinstance(text, str):
        return ""
    # common mojibake fixes
    replacements = {
        "â¢": "-", "â": "-", "â": "-",
        "â": "'", "â": "'", "â": '"', "â": '"',
        "â¦": "...", "â": "-",
        "Ã¯": "i", "Ã©": "e", "Ã¨": "e", "Ã ": "a",
        "Â": "", "\u00a0": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    # keep only characters representable in latin-1
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ── 5. Helper: write one PDF ─────────────────────────────────────────
def write_pdf(resume_text: str, filepath: str):
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    cleaned = sanitize(resume_text)
    # multi_cell handles line breaks / wrapping automatically
    pdf.multi_cell(0, 5, cleaned)

    pdf.output(filepath)


# ── 6. Iterate categories & rows ─────────────────────────────────────
for category in target_categories:
    # exact match on the Category column
    subset = df[df["Category"].str.strip().str.lower() == category.lower()]

    if subset.empty:
        print(f"[!] No rows found for category: {category}")
        continue

    # safe folder / file name
    safe_cat = re.sub(r"[^\w\-]+", "_", category)

    for idx, row in enumerate(subset.itertuples(index=False), start=1):
        resume_text = row.Resume
        filename = f"{safe_cat}_resume_{idx:03d}.pdf"
        filepath = os.path.join(output_dir, filename)

        try:
            write_pdf(resume_text, filepath)
            print(f"[✓] Wrote {filepath}")
        except Exception as e:
            print(f"[✗] Failed {category} row {idx}: {e}")

print("\nDone. PDFs are in:", os.path.abspath(output_dir))