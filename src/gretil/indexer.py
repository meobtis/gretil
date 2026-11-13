import json
import logging
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from .client import GRETILClient
from .config import BASE_URL, INDEX_URL, MANIFEST_PATH, RAW_DIR
from .selection import select

logger = logging.getLogger("gretil.indexer")

# The two sections GRETIL itself files under Buddhism: "Religious Literature / Buddhist" and "Philosophy / Buddhist".
BUDDHIST_SECTIONS = {"RLBuddh": "Buddhist Religious Literature", "Bauddha": "Buddhist Philosophy"}

# Parts of GRETIL's Sanskrit section that are not Sanskrit texts: excerpts from the Old Javanese section.
SKIPPED_SECTIONS = {"SktIndon_excerpts"}

TEI_RE = re.compile(r"corpustei/(?!transformations).*\.xml$")
OUTLINE_RE = re.compile(r"^outline-(\d+)$")


def clean_heading(text: str) -> str:
    """Section name without the parenthetical notes, e.g. 'Saiva (see also Philosophy / Saiva)' -> 'Saiva'."""
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class GRETILIndexer:
    """Indexes the Sanskrit texts of GRETIL (https://gretil.sub.uni-goettingen.de/gretil.html).

    The index page is an outline: language > section > subsection, each with a list of texts. The manifest records,
    for every text that GRETIL offers as TEI XML or as a legacy .htm file, its section path and where it lives in the
    repository, so that texts/ follows the same structure.
    """

    def __init__(self, client: GRETILClient):
        self.client = client

    async def fetch_index_page(self, force: bool = False) -> str:
        cache_path = RAW_DIR / "gretil_index.html"
        return await self.client.fetch(INDEX_URL, cache_path=cache_path, force=force)

    @staticmethod
    def section_chain(text_div: Tag) -> List[Tuple[str, str]]:
        """[(heading id, heading text), …] from the top level down to the section a list of texts belongs to."""
        chain: List[Tuple[str, str]] = []
        node = text_div.parent
        while node is not None:
            classes = node.get("class") or [] if hasattr(node, "get") else []
            if node.name == "div" and any(OUTLINE_RE.match(c) for c in classes):
                heading = node.find(re.compile(r"^h[1-6]$"), recursive=False)
                if heading is not None:
                    chain.append((heading.get("id") or "", heading.get_text(" ", strip=True)))
            node = node.parent
        return list(reversed(chain))

    def extract_entries(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        entries: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        positions: Dict[str, int] = {}

        for text_div in soup.find_all("div", class_=re.compile(r"outline-text-\d")):
            chain = self.section_chain(text_div)
            if not chain or chain[0][0] != "Sanskrit" or len(chain) < 2:
                continue  # other languages, introduction, secondary resources
            if any(sid in SKIPPED_SECTIONS for sid, _ in chain):
                continue
            section_id = chain[-1][0]
            names = [clean_heading(t) for _, t in chain[1:]]
            category = BUDDHIST_SECTIONS.get(section_id) or " / ".join(names)

            for lst in text_div.find_all(["ol", "ul"], recursive=False):
                for li in lst.find_all("li", recursive=False):
                    links = [a.get("href") for a in li.find_all("a") if a.get("href")]
                    xml_links = [l for l in links if TEI_RE.search(l)]
                    htm_links = [l for l in links if l.endswith(".htm") and "1_sanskr" in l and "transformations" not in l]
                    if xml_links:
                        url, file_type = xml_links[0], "tei_xml"
                    elif htm_links:
                        url, file_type = htm_links[0], "legacy_htm"
                    else:
                        continue  # a cross-reference, or a text that lives elsewhere (e.g. TITUS)

                    positions[section_id] = positions.get(section_id, 0) + 1
                    file_id = Path(url).stem
                    full_url = url if url.startswith("http") else f"{BASE_URL}/{url.lstrip('/')}"
                    section_name = " / ".join(names)
                    if file_id in entries:  # listed in several sections: keep the first, note the others
                        entries[file_id].setdefault("also_in", []).append(section_name)
                        continue
                    entries[file_id] = {
                        "id": file_id,
                        "index": positions[section_id],
                        "catalog_title": li.get_text().splitlines()[0].strip(),
                        "relative_url": url,
                        "source_url": full_url,
                        "file_type": file_type,
                        "section_id": section_id,
                        "category": category,
                        "section": section_name,
                        "folder": "/".join(slug(n) for n in names),
                        "buddhist": section_id in BUDDHIST_SECTIONS,
                        "language": "sa",
                    }
        return list(entries.values())

    async def build_manifest(
        self,
        category: str = "sanskrit",
        limit: Optional[int] = None,
        force: bool = False,
        progress=None,
    ) -> List[Dict[str, Any]]:
        html = await self.fetch_index_page(force=force)
        soup = BeautifulSoup(html, "html.parser")
        # The manifest always has every Sanskrit text, so that the repository stays complete;
        # `category` only narrows what a run of the tool is reported on.
        all_entries = self.extract_entries(soup)

        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(all_entries, ensure_ascii=False, indent=2), encoding="utf-8")

        selected = select(all_entries, category)
        return selected[:limit] if limit else selected
