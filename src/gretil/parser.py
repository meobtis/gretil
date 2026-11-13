import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, NavigableString

from .utils import format_sanskrit_text


def parse_tei_xml(xml_content: str) -> Dict[str, Any]:
    """Parse a GRETIL TEI-conformant XML document into structured metadata and Markdown."""
    soup = BeautifulSoup(xml_content, "xml")

    # Header metadata
    header = soup.find("teiHeader")
    title = ""
    author = ""
    source_bibl = ""
    contributors = []
    licence = ""
    keywords = []

    if header:
        title_el = header.find("titleStmt")
        if title_el:
            t = title_el.find("title")
            title = t.get_text(strip=True) if t else ""
            a = title_el.find("author")
            author = a.get_text(strip=True) if a else ""

            for resp in title_el.find_all("respStmt"):
                r = resp.find("resp")
                n = resp.find("name")
                if r and n:
                    contributors.append(f"{r.get_text(strip=True)}: {n.get_text(strip=True)}")

        bibl_el = header.find("sourceDesc")
        if bibl_el:
            b = bibl_el.find("bibl")
            source_bibl = b.get_text(strip=True) if b else ""

        pub_el = header.find("publicationStmt")
        if pub_el:
            lic = pub_el.find("licence")
            licence = lic.get_text(strip=True) if lic else ""

        prof_el = header.find("profileDesc")
        if prof_el:
            for term in prof_el.find_all("term"):
                keywords.append(term.get_text(strip=True))

    tei_root = soup.find("TEI")
    xml_id = tei_root.get("xml:id", "") if tei_root else ""

    body = soup.find("body")
    if not body:
        return {
            "title": title,
            "author": author,
            "xml_id": xml_id,
            "source_bibl": source_bibl,
            "contributors": contributors,
            "licence": licence,
            "keywords": keywords,
            "markdown": "",
        }

    # Recursive node conversion to Markdown
    def convert_node(node, depth: int = 2) -> str:
        if isinstance(node, NavigableString):
            return str(node)

        tag = node.name
        if tag == "hi":
            rend = node.get("rend", "")
            inner = "".join(convert_node(c, depth) for c in node.children)
            if rend == "bold":
                return f"**{inner}**"
            elif rend in ("italic", "it"):
                return f"*{inner}*"
            return inner
        elif tag == "note":
            inner = "".join(convert_node(c, depth) for c in node.children).strip()
            return f" *({inner})* " if inner else ""
        elif tag == "pb":
            n = node.get("n", "")
            return f" `[p. {n}]` " if n else ""
        elif tag == "l":
            inner = "".join(convert_node(c, depth) for c in node.children).strip()
            return inner
        elif tag == "lg":
            lines = []
            pending = ""
            for c in node.children:
                if c.name == "l":
                    lines.append((pending + convert_node(c, depth)).strip())
                    pending = ""
                elif c.name is not None:
                    # A note or page break between or after the lines of the verse: keep it with the line before.
                    extra = convert_node(c, depth)
                    if lines:
                        lines[-1] = (lines[-1] + extra).strip()
                    else:
                        pending += extra
            out_lines = []
            for i, line in enumerate(lines):
                if i < len(lines) - 1:
                    out_lines.append(line + "  ")
                else:
                    out_lines.append(line)
            return "\n".join(out_lines) + "\n\n"
        elif tag == "head":
            inner = "".join(convert_node(c, depth) for c in node.children).strip()
            hashes = "#" * min(depth, 5)
            return f"{hashes} {inner}\n\n"
        elif tag == "div":
            n = node.get("n", "")
            has_head = any(c.name == "head" for c in node.children)
            parts = []
            if n and not has_head:
                hashes = "#" * min(depth, 5)
                parts.append(f"{hashes} Section {n}\n\n")
            for c in node.children:
                parts.append(convert_node(c, depth + 1))
            return "".join(parts)
        elif tag == "p":
            inner = "".join(convert_node(c, depth) for c in node.children).strip()
            # If paragraph contains verse lines (slashes/dandas), format them
            formatted = format_sanskrit_text(inner)
            return formatted + "\n\n"
        else:
            return "".join(convert_node(c, depth) for c in node.children)

    raw_markdown = convert_node(body, depth=2)
    # Collapse 3+ newlines
    clean_markdown = re.sub(r"\n{3,}", "\n\n", raw_markdown).strip()

    return {
        "title": title,
        "author": author,
        "xml_id": xml_id,
        "source_bibl": source_bibl,
        "contributors": contributors,
        "licence": licence,
        "keywords": keywords,
        "markdown": clean_markdown,
    }


def parse_legacy_html(html_content: str) -> Dict[str, Any]:
    """Parse legacy GRETIL .htm file into structured metadata and Markdown."""
    soup = BeautifulSoup(html_content, "html.parser")
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else ""

    # In legacy GRETIL files, text before <hr> contains publication info, and after <hr> is the text
    body = soup.find("body") or soup
    body_html = str(body)

    parts = re.split(r"<hr[^>]*>", body_html, flags=re.I)
    header_part = parts[0] if len(parts) > 1 else ""
    text_part = parts[-1] if len(parts) > 1 else body_html

    # Clean text part
    text_soup = BeautifulSoup(text_part, "html.parser")
    # remove scripts and styles
    for s in text_soup(["script", "style"]):
        s.decompose()

    raw_text = text_soup.get_text()
    clean_text = format_sanskrit_text(raw_text)

    # Header metadata
    header_soup = BeautifulSoup(header_part, "html.parser")
    header_lines = [l.strip() for l in header_soup.get_text().splitlines() if l.strip()]

    source_bibl = ""
    for l in header_lines:
        if l.lower().startswith("based on"):
            source_bibl = l

    return {
        "title": title or (header_lines[0] if header_lines else "Untitled"),
        "author": "",
        "xml_id": "",
        "source_bibl": source_bibl,
        "contributors": [l for l in header_lines if "input" in l.lower() or "by" in l.lower()],
        "licence": "GRETIL legacy reference",
        "keywords": ["Sanskrit -- Religious Literature -- Buddhist"],
        "markdown": clean_text,
    }
