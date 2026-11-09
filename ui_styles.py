CSS = """
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

/* Chip container: one horizontal scrolling row */
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

/* Individual chips keep their intrinsic width */
.filter-block .filter-checkbox .wrap label,
.filter-block .filter-checkbox .grid label {
    flex: 0 0 auto !important;
    white-space: nowrap !important;
    margin-right: 4px !important;
}

/* Slim horizontal scrollbar */
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