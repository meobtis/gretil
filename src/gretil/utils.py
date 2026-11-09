import re
import unicodedata
from typing import List

ILLEGAL_FS_CHARS = re.compile(r'[/\\:*?"<>|]+')
EXTRA_WHITESPACE = re.compile(r'\s+')

# Matches double dandas or double slashes (// or || or ॥) at end of line with optional verse numbers
VERSE_END_REGEX = re.compile(
    r'(//|\|\||\u0965)\s*(\d+|[०-९]+)?\s*(//|\|\||\u0965)?\s*$'
)

# Matches single danda or single slash or comma at end of line (half-verse / pāda)
# Negative lookahead/lookbehind ensures it is not part of // or ||
HALF_VERSE_REGEX = re.compile(
    r'((?<!/)/(?!/)|(?<!\|)\|(?!\|)|(?<!\u0965)\u0964(?!\u0965)|,)\s*$'
)


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """Sanitize string for safe use in file/folder names across Mac/Linux/Windows.

    Preserves IAST Roman diacritics and Devanagari.
    """
    if not name:
        return "untitled"
    name = unicodedata.normalize("NFC", name)
    name = ILLEGAL_FS_CHARS.sub("_", name)
    name = EXTRA_WHITESPACE.sub(" ", name).strip(". ")
    if len(name) > max_length:
        name = name[:max_length].rstrip(". _")
    return name or "untitled"


def format_sanskrit_text(raw_text: str) -> str:
    """Format Sanskrit text into clean Markdown.

    - Verse lines ending in / or | get two trailing spaces for Markdown hard breaks.
    - Verse ends ending in // or || get a blank line after the verse stanza.
    - Normalizes unicode spaces and collapses multiple blank lines.
    """
    if not raw_text:
        return ""

    raw_text = raw_text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw_text.split("\n")

    cleaned_input: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned_input.append(stripped)

    formatted_lines: List[str] = []
    for line in cleaned_input:
        if VERSE_END_REGEX.search(line):
            formatted_lines.append(line)
            formatted_lines.append("")
        elif HALF_VERSE_REGEX.search(line):
            formatted_lines.append(line + "  ")
        else:
            # Prose line or header
            formatted_lines.append(line)
            formatted_lines.append("")

    res = "\n".join(formatted_lines)
    res = re.sub(r"\n{3,}", "\n\n", res).strip()
    return res
