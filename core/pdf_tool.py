"""Document Tool: extracts clean text from an uploaded supplier PDF."""
import io

from pypdf import PdfReader


def extract_text(file_bytes: bytes) -> str:
    """Extract and lightly clean text from a PDF's bytes."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)
    full_text = "\n".join(pages_text)
    return _clean(full_text)


def _clean(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)
