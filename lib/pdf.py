"""PDF helpers: page count and first-page cover render."""

import io
import logging

import pypdfium2 as pdfium
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def count_pages(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def render_cover(data: bytes) -> bytes | None:
    try:
        doc = pdfium.PdfDocument(data)
        page = doc[0]
        width = page.get_width()
        bitmap = page.render(scale=600 / width if width else 1.5)
        img = bitmap.to_pil().convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=82)
        return out.getvalue()
    except Exception as exc:
        logger.warning("render_cover failed: %s", exc)
        return None
