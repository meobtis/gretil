"""Check that the Markdown of each TEI text has the same letters as the TEI text itself.

Usage: uv run python scripts/check_coverage.py [--all]

For every text converted from TEI XML, compares the number of letters in the TEI <text> element (without variant
readings that are not part of the running text: sic, orig and rdg inside choice/app) with the number of letters in the
Markdown file. A ratio far from 1 means that text was lost (below 1) or that editorial alternatives were printed as text
(above 1). Prints the outliers, or every text with --all.
"""

import glob
import json
import re
import sys
from pathlib import Path

import yaml
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
TEI = "{http://www.tei-c.org/ns/1.0}"
LETTERS = re.compile(r"[A-Za-zÀ-ɏḀ-ỿऀ-ॿ]")
ALTERNATIVES = {TEI + "sic", TEI + "orig", TEI + "rdg", TEI + "abbr"}


def tei_letters(path: Path) -> int:
    root = etree.parse(str(path), etree.XMLParser(recover=True, huge_tree=True)).getroot()
    text = root.find(f".//{TEI}text")
    if text is None:
        return 0
    total = 0
    for el in text.iter():
        if not isinstance(el.tag, str):
            continue
        if el.text and not any(a in ALTERNATIVES for a in (el, *el.iterancestors())):
            total += len(LETTERS.findall(el.text))
        if el.tail and not any(a in ALTERNATIVES for a in el.iterancestors()):
            total += len(LETTERS.findall(el.tail))
    return total


def main() -> None:
    show_all = "--all" in sys.argv
    manifest = {e["id"]: e for e in json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))}
    rows = []
    for md in glob.glob(str(ROOT / "texts/**/*.md"), recursive=True):
        if md.endswith("CATALOG.md"):
            continue
        raw = Path(md).read_text(encoding="utf-8")
        _, head, body = raw.split("---\n", 2)
        gid = yaml.safe_load(head)["gretil_id"]
        entry = manifest.get(gid)
        if not entry or entry["file_type"] != "tei_xml":
            continue
        src = tei_letters(ROOT / "data/raw/xml" / f"{gid}.xml")
        out = len(LETTERS.findall(re.sub(r"`\[p\. [^\]]*\]`|^#+ Section \S+$", "", body, flags=re.M)))
        rows.append((out / src if src else 0, gid, src, out))
    rows.sort()
    bad = [r for r in rows if not 0.97 <= r[0] <= 1.03]
    for r in (rows if show_all else bad):
        print(f"{r[0]:6.3f}  {r[1][:56]:56} tei={r[2]:>9} md={r[3]:>9}")
    print(f"{len(rows)} TEI texts checked; {len(bad)} outside 0.97–1.03")


if __name__ == "__main__":
    main()
