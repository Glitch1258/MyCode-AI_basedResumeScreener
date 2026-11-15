CSS = """
/* ---- Star rating row ---- */
.star-row {
    gap: 4px !important;
    flex-wrap: nowrap !important;
    margin: 4px 0 8px 0 !important;
}
.star-btn {
    min-width: 30px !important;
    max-width: 30px !important;
    padding: 0 !important;
    font-size: 18px !important;
    line-height: 1 !important;
}
.top-row {
    height: 30vh !important;
    max-height: 30vh !important;
    min-height: 30vh !important;
    overflow: hidden !important;
}
.top-row > * {
    height: 100% !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

/* -------- Filter block (single unit) -------- */
.filter-block {
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
}
.filter-block .filter-checkbox {
    flex: 1 1 auto !important;
    min-height: 80px !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}
.filter-block .filter-checkbox > label,
.filter-block .filter-checkbox > span,
.filter-block .filter-checkbox > .label-wrap {
    flex: 0 0 auto !important;
}
.filter-block .filter-checkbox .wrap,
.filter-block .filter-checkbox .grid {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    max-height: 100% !important;
}
.filter-block .filter-checkbox .wrap label,
.filter-block .filter-checkbox .grid label {
    flex: 0 0 auto !important;
    white-space: nowrap !important;
    margin-right: 4px !important;
}
.filter-block .filter-checkbox .wrap::-webkit-scrollbar,
.filter-block .filter-checkbox .grid::-webkit-scrollbar {
    height: 6px;
}
.filter-block .filter-checkbox .wrap::-webkit-scrollbar-thumb,
.filter-block .filter-checkbox .grid::-webkit-scrollbar-thumb {
    background: #bbb;
    border-radius: 3px;
}

/* Narrow arrow buttons */
.scroll-arrow {
    min-width: 34px !important;
    max-width: 34px !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    font-weight: bold !important;
}

.name-table { max-height: 760px; overflow-y: auto; }

/* ---- Modal overlay (save/load dialogs) ---- */
.modal-overlay {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    background: rgba(0, 0, 0, 0.5) !important;
    z-index: 9999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
}
.modal-box {
    background: var(--block-background-fill, var(--background-fill-primary, #ffffff)) !important;
    color: var(--body-text-color, inherit) !important;
    border: 1px solid var(--border-color-primary, #e5e7eb) !important;
    border-radius: 12px !important;
    padding: 22px 26px !important;
    min-width: 420px !important;
    max-width: 640px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
    display: block !important;
}
"""

SCROLL_LEFT_JS = """
() => {
    document
        .querySelectorAll('.filter-block .filter-checkbox .wrap, .filter-block .filter-checkbox .grid')
        .forEach(el => el.scrollBy({ left: -el.clientWidth * 0.8, behavior: 'smooth' }));
}
"""

SCROLL_RIGHT_JS = """
() => {
    document
        .querySelectorAll('.filter-block .filter-checkbox .wrap, .filter-block .filter-checkbox .grid')
        .forEach(el => el.scrollBy({ left: el.clientWidth * 0.8, behavior: 'smooth' }));
}
"""
