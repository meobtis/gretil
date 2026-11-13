from collections import Counter, defaultdict
import json
import logging
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml
from rich.progress import Progress

from .config import MANIFEST_PATH, RAW_LEGACY_DIR, RAW_XML_DIR, TEXTS_DIR
from .parser import parse_legacy_html, parse_tei_xml
from .selection import select
from .utils import sanitize_filename

logger = logging.getLogger("gretil.converter")

# A folder with more texts than this is split into sub-folders by the first letter of the title.
BUCKET_LIMIT = 60


def bucket_of(title: str) -> str:
    """Sub-folder for a title: its first letter without diacritics (a, b, …), or 0-9 / _ ."""
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lstrip(" \"'([“‘")
    first = folded[:1].lower()
    if first.isalpha():
        return first
    return "0-9" if first.isdigit() else "_"


class GRETILConverter:
    """Converts cached GRETIL TEI XML and legacy HTML into clean Markdown, in folders that follow GRETIL's sections."""

    def __init__(self, output_dir: Path = TEXTS_DIR):
        self.output_dir = output_dir

    def load_manifest(self) -> List[Dict[str, Any]]:
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(
                f"Manifest not found at {MANIFEST_PATH}. Run 'gretil index' first."
            )
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def parse_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        file_id = entry["id"]
        if entry.get("file_type", "tei_xml") == "tei_xml":
            path = RAW_XML_DIR / f"{file_id}.xml"
            if not path.exists():
                return None
            parsed = parse_tei_xml(path.read_text(encoding="utf-8"))
        else:
            path = RAW_LEGACY_DIR / f"{file_id}.htm"
            if not path.exists():
                return None
            parsed = parse_legacy_html(path.read_text(encoding="utf-8", errors="ignore"))
            # The legacy parser does not know the section; the manifest does.
            parsed["keywords"] = ["Sanskrit -- " + entry["section"].replace(" / ", " -- ")]
        parsed["title"] = parsed["title"].lstrip("% ").strip() or entry.get("catalog_title", file_id)  # legacy titles can start "% "
        return parsed

    def front_matter(self, entry: Dict[str, Any], parsed: Dict[str, Any]) -> str:
        frontmatter: Dict[str, Any] = {
            "title": parsed["title"],
            "category": entry.get("category", ""),
            "section": entry.get("section", ""),
            "buddhist": bool(entry.get("buddhist")),
            "language": entry.get("language", "sa"),
            "gretil_id": entry["id"],
            "source_url": entry["source_url"],
        }
        if parsed.get("author"):
            frontmatter["author"] = parsed["author"]
        if parsed.get("source_bibl"):
            frontmatter["source_edition"] = parsed["source_bibl"]
        if parsed.get("contributors"):
            frontmatter["contributors"] = parsed["contributors"]
        if parsed.get("licence"):
            frontmatter["licence"] = parsed["licence"]
        if parsed.get("keywords"):
            frontmatter["keywords"] = parsed["keywords"]
        if entry.get("also_in"):
            frontmatter["also_in"] = entry["also_in"]
        return yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()

    def convert_all(
        self,
        category: str = "sanskrit",
        limit: Optional[int] = None,
        progress: Optional[Progress] = None,
    ) -> Dict[str, Any]:
        entries = select(self.load_manifest(), category)
        if limit:
            entries = entries[:limit]

        task_id = None
        if progress:
            task_id = progress.add_task(f"[yellow]Converting {len(entries)} texts to Markdown...", total=len(entries))

        parsed: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for e in entries:
            p = self.parse_entry(e)
            if p is None:
                logger.warning(f"Raw file missing for {e['id']}")
            else:
                parsed.append((e, p))
            if progress and task_id is not None:
                progress.advance(task_id)

        # Folder of each text: the manifest's section folder, split by first letter if it is large.
        per_folder = Counter(e["folder"] for e, _ in parsed)
        placed: List[Tuple[Dict[str, Any], Dict[str, Any], Path, str]] = []
        for e, p in parsed:
            folder = Path(e["folder"])
            if per_folder[e["folder"]] > BUCKET_LIMIT:
                folder = folder / bucket_of(p["title"])
            placed.append((e, p, folder, sanitize_filename(p["title"])))

        # Two texts with one title in one folder (e.g. several recensions): add the GRETIL id to each.
        clashes = Counter((folder, name) for _, _, folder, name in placed)

        if category == "sanskrit" and not limit and self.output_dir.exists():
            shutil.rmtree(self.output_dir)  # start clean: files move when GRETIL's sections or titles change

        written = 0
        for e, p, folder, name in placed:
            if clashes[(folder, name)] > 1:
                name = sanitize_filename(f"{p['title']}_{e['id']}")
            target_dir = self.output_dir / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            head = self.front_matter(e, p)
            (target_dir / f"{name}.md").write_text(
                f"---\n{head}\n---\n\n# {p['title']}\n\n{p['markdown']}\n", encoding="utf-8"
            )
            written += 1

        self.generate_catalog()
        return {"total_entries": len(entries), "converted_entries": written}

    def generate_catalog(self):
        """Generate texts/CATALOG.md: all texts by GRETIL section, with links to the Markdown and to GRETIL."""
        if not MANIFEST_PATH.exists():
            return
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        id_to_file: Dict[str, str] = {}
        for md_file in self.output_dir.glob("**/*.md"):
            if md_file.name == "CATALOG.md":
                continue
            head = md_file.read_text(encoding="utf-8", errors="ignore")[:6000]
            if head.startswith("---"):
                try:
                    fm = yaml.safe_load(head.split("---", 2)[1])
                except yaml.YAMLError as err:
                    logger.warning(f"Error parsing frontmatter in {md_file}: {err}")
                    continue
                if isinstance(fm, dict) and fm.get("gretil_id"):
                    id_to_file[fm["gretil_id"]] = md_file.relative_to(self.output_dir).as_posix()

        by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for e in manifest:
            by_section[e["section"]].append(e)
        converted = sum(1 for e in manifest if e["id"] in id_to_file)
        buddhist = sum(1 for e in manifest if e.get("buddhist"))

        lines = [
            "# GRETIL Sanskrit texts: catalog\n",
            "All Sanskrit texts of [GRETIL (Göttingen Register of Electronic Texts in Indian Languages)]"
            "(https://gretil.sub.uni-goettingen.de/gretil.html), by GRETIL's own sections.\n",
            f"**Texts listed:** {len(manifest)} ({buddhist} Buddhist: the sections *Religious Literature / Buddhist* and "
            f"*Philosophy / Buddhist*). **Converted:** {converted}.\n",
            "## Sections\n",
        ]
        for section, items in by_section.items():
            lines.append(f"- {section} ({len(items)})")
        lines.append("\n---\n")

        for section, items in by_section.items():
            lines.append(f"## {section}\n")
            lines.append(f"Total: {len(items)} texts. Folder: `{items[0]['folder']}/`\n")
            lines.append("| # | Title | GRETIL ID | Type | Markdown Link | Source |")
            lines.append("|---|---|---|---|---|---|")
            for e in items:
                rel = id_to_file.get(e["id"])
                link = f"[{Path(rel).stem}]({rel.replace(' ', '%20')})" if rel else "*(not available)*"
                lines.append(
                    f"| {e['index']} | {e['catalog_title']} | `{e['id']}` | `{e['file_type']}` | {link} | "
                    f"[Source]({e['source_url']}) |"
                )
            lines.append("\n---\n")

        catalog_path = self.output_dir / "CATALOG.md"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text("\n".join(lines), encoding="utf-8")
