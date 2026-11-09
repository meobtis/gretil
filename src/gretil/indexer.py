import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from rich.progress import Progress

from .client import GRETILClient
from .config import BASE_URL, INDEX_URL, MANIFEST_PATH, RAW_DIR

logger = logging.getLogger("gretil.indexer")


class GRETILIndexer:
    """Indexes GRETIL Buddhist Sanskrit texts from gretil.html."""

    def __init__(self, client: GRETILClient):
        self.client = client

    async def fetch_index_page(self, force: bool = False) -> str:
        cache_path = RAW_DIR / "gretil_index.html"
        return await self.client.fetch(INDEX_URL, cache_path=cache_path, force=force)

    def extract_section_items(
        self,
        soup: BeautifulSoup,
        section_id: str,
        category_name: str,
    ) -> List[Dict[str, Any]]:
        container = soup.find(id=f"text-{section_id}")
        if not container:
            header = soup.find(id=section_id)
            if header:
                container = header.find_next_sibling("div")

        if not container:
            logger.warning(f"Section {section_id} not found in index HTML")
            return []

        ol = container.find("ol", class_="org-ol")
        items = ol.find_all("li", recursive=False) if ol else container.find_all("li", recursive=False)

        entries = []
        for idx, it in enumerate(items, start=1):
            title_line = it.get_text().splitlines()[0].strip()

            links = [a.get("href") for a in it.find_all("a") if a.get("href")]
            xml_links = [l for l in links if l.endswith(".xml")]
            htm_links = [l for l in links if l.endswith(".htm") and "1_sanskr" in l]

            download_url = None
            file_type = None

            if xml_links:
                download_url = xml_links[0]
                file_type = "tei_xml"
            elif htm_links:
                download_url = htm_links[0]
                file_type = "legacy_htm"

            if download_url:
                # Normalize relative URL to full URL
                full_url = download_url if download_url.startswith("http") else f"{BASE_URL}/{download_url.lstrip('/')}"
                file_id = Path(download_url).stem

                entries.append({
                    "id": file_id,
                    "index": idx,
                    "catalog_title": title_line,
                    "relative_url": download_url,
                    "source_url": full_url,
                    "file_type": file_type,
                    "section_id": section_id,
                    "category": category_name,
                })

        return entries

    async def build_manifest(
        self,
        category: str = "rlbuddh",
        limit: Optional[int] = None,
        force: bool = False,
        progress: Optional[Progress] = None,
    ) -> List[Dict[str, Any]]:
        html = await self.fetch_index_page(force=force)
        soup = BeautifulSoup(html, "html.parser")

        all_entries: List[Dict[str, Any]] = []

        if category in {"rlbuddh", "all"}:
            rl_entries = self.extract_section_items(
                soup, "RLBuddh", "Buddhist Religious Literature"
            )
            all_entries.extend(rl_entries)

        if category in {"bauddha", "all"}:
            bauddha_entries = self.extract_section_items(
                soup, "Bauddha", "Buddhist Philosophy"
            )
            all_entries.extend(bauddha_entries)

        if limit:
            all_entries = all_entries[:limit]

        # Save to manifest
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(
            json.dumps(all_entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return all_entries
