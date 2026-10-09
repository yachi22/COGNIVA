import re


def clean_extracted_text(text: str) -> str:
    """
    Deterministic text cleaning for extracted document content.
    Faithful to source document:
    - Strips non-printable control characters while preserving newlines and tabs
    - Normalizes Windows (\r\n) and legacy Mac (\r) line endings to \n
    - Strips soft hyphens (\xad)
    - Removes trailing spaces from each line
    - Collapses multiple horizontal spaces into a single space
    - Collapses 3 or more consecutive blank lines into 2 blank lines (\n\n)
    - Strips leading and trailing whitespace
    """
    if not text:
        return ""

    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Remove soft hyphens and null bytes
    text = text.replace("\xad", "").replace("\x00", "")

    # 3. Strip non-printable ASCII control characters (keep \n, \t)
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 4. Collapse consecutive spaces/tabs on the same line (preserve newlines)
    text = re.sub(r"[ \t]+", " ", text)

    # 5. Remove whitespace at the end of each line
    lines = [line.strip() for line in text.split("\n")]

    # 6. Collapse consecutive blank lines (maximum 2 consecutive newlines)
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append("")
        else:
            blank_count = 0
            cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines).strip()
    return cleaned_text
