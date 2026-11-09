import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from rich.progress import Progress

from .client import GRETILClient
from .config import MANIFEST_PATH, RAW_LEGACY_DIR, RAW_XML_DIR

logger = logging.getLogger("gretil.scraper")


class GRETILScraper:
    """Downloads raw TEI XML and legacy files for texts listed in manifest.json."""

    def __init__(self, client: GRETILClient):
        self.client = client

    def load_manifest(self) -> List[Dict[str, Any]]:
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(
                f"Manifest not found at {MANIFEST_PATH}. Run 'gretil index' first."
            )
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def get_cache_path(self, entry: Dict[str, Any]) -> Path:
        file_id = entry["id"]
        file_type = entry.get("file_type", "tei_xml")
        if file_type == "tei_xml":
            return RAW_XML_DIR / f"{file_id}.xml"
        else:
            return RAW_LEGACY_DIR / f"{file_id}.htm"

    async def scrape_entry(self, entry: Dict[str, Any], force: bool = False) -> bool:
        url = entry["source_url"]
        cache_path = self.get_cache_path(entry)
        try:
            await self.client.fetch(url, cache_path=cache_path, force=force)
            return True
        except Exception as e:
            logger.error(f"Failed to download {entry['id']} from {url}: {e}")
            return False

    async def scrape_all(
        self,
        category: str = "all",
        limit: Optional[int] = None,
        force: bool = False,
        progress: Optional[Progress] = None,
    ) -> Dict[str, int]:
        entries = self.load_manifest()

        if category == "rlbuddh":
            entries = [e for e in entries if e.get("section_id") == "RLBuddh"]
        elif category == "bauddha":
            entries = [e for e in entries if e.get("section_id") == "Bauddha"]

        if limit:
            entries = entries[:limit]

        task_id = None
        if progress:
            task_id = progress.add_task(
                f"[green]Scraping {len(entries)} GRETIL texts...",
                total=len(entries),
            )

        success = 0
        failed = 0

        async def worker(item):
            nonlocal success, failed
            ok = await self.scrape_entry(item, force=force)
            if ok:
                success += 1
            else:
                failed += 1
            if progress and task_id is not None:
                progress.advance(task_id)

        await asyncio.gather(*(worker(e) for e in entries))

        return {
            "total": len(entries),
            "success": success,
            "failed": failed,
        }
