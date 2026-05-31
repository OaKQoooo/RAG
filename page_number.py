import re


def detect_document_page(page, pdf_page: int, page_offset=None):
    """Read a printed page number from the footer, with an optional manual offset."""
    if page_offset is not None:
        document_page = pdf_page - int(page_offset)
        return str(document_page) if document_page > 0 else None

    footer_top = page.height * 0.88
    footer = page.crop((0, footer_top, page.width, page.height)).extract_text() or ""
    patterns = [
        r"第\s*(\d+)\s*页",
        r"-\s*(\d+)\s*-",
        r"^\s*(\d+)\s*/\s*\d+\s*$",
        r"^\s*(\d+)\s*$",
    ]
    for line in reversed(footer.splitlines()):
        for pattern in patterns:
            match = re.search(pattern, line.strip())
            if match:
                return match.group(1)
    return None
