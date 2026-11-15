"""star_rating.py — UI helpers for the 1–10 star rating widget.

Gradio-native: a Row of 10 small buttons. Filled stars use variant "primary";
empty stars use "secondary". Clicking star i sets the rating to i.
"""
import gradio as gr

from rating import DEFAULT_RATING, MAX_RATING, MIN_RATING

STAR_FILLED = "★"
STAR_EMPTY = "☆"
NUM_STARS = MAX_RATING  # 10


def make_star_row():
    """Build the star Row and return its 10 buttons."""
    with gr.Row(elem_classes=["star-row"]):
        buttons = [
            gr.Button(
                value=STAR_FILLED if i <= DEFAULT_RATING else STAR_EMPTY,
                size="sm", scale=0, min_width=32,
                elem_classes=["star-btn"],
            )
            for i in range(MIN_RATING, NUM_STARS + 1)
        ]
    return buttons


def star_updates(rating: int):
    """10 gr.update() objects reflecting `rating` (for widget refresh)."""
    rating = max(MIN_RATING, min(NUM_STARS, int(rating)))
    return [
        gr.update(
            value=STAR_FILLED if i <= rating else STAR_EMPTY,
            variant="primary" if i <= rating else "secondary",
        )
        for i in range(MIN_RATING, NUM_STARS + 1)
    ]
