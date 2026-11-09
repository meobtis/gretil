from collections import Counter
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from rich.progress import Progress

from .config import MANIFEST_PATH, RAW_LEGACY_DIR, RAW_XML_DIR, TEXTS_DIR
from .parser import parse_legacy_html, parse_tei_xml
from .utils import sanitize_filename

logger = logging.getLogger("gretil.converter")


class GRETILConverter:
    """Converts cached GRETIL TEI XML and legacy HTML into clean Markdown."""

    def __init__(self, output_dir: Path = TEXTS_DIR):
        self.output_dir = output_dir

    def load_manifest(self) -> List[Dict[str, Any]]:
        if not MANIFEST_PATH.exists():
            raise FileNotFoundError(
                f"Manifest not found at {MANIFEST_PATH}. Run 'gretil index' first."
            )
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def convert_entry(
        self,
        entry: Dict[str, Any],
        title_counts: Optional[Counter] = None,
    ) -> Optional[Path]:
        file_id = entry["id"]
        file_type = entry.get("file_type", "tei_xml")
        category = entry.get("category", "Buddhist Religious Literature")
        section_id = entry.get("section_id", "RLBuddh")

        cat_folder = "buddhist_religious_literature" if section_id == "RLBuddh" else "buddhist_philosophy"
        target_dir = self.output_dir / cat_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        if file_type == "tei_xml":
            xml_path = RAW_XML_DIR / f"{file_id}.xml"
            if not xml_path.exists():
                logger.warning(f"Raw XML missing for {file_id}")
                return None
            content = xml_path.read_text(encoding="utf-8")
            parsed = parse_tei_xml(content)
        else:
            legacy_path = RAW_LEGACY_DIR / f"{file_id}.htm"
            if not legacy_path.exists():
                logger.warning(f"Raw legacy HTML missing for {file_id}")
                return None
            content = legacy_path.read_text(encoding="utf-8", errors="ignore")
            parsed = parse_legacy_html(content)

        title = parsed["title"] or entry.get("catalog_title", file_id)

        frontmatter: Dict[str, Any] = {
            "title": title,
            "category": category,
            "gretil_id": file_id,
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

        yaml_header = yaml.dump(
            frontmatter,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ).strip()

        body_md = parsed["markdown"]
        full_content = f"---\n{yaml_header}\n---\n\n# {title}\n\n{body_md}\n"

        clean_t = sanitize_filename(title)
        if title_counts and title_counts.get(clean_t, 0) > 1:
            file_slug = sanitize_filename(f"{title}_{file_id}")
        else:
            file_slug = clean_t

        out_file = target_dir / f"{file_slug}.md"
        out_file.write_text(full_content, encoding="utf-8")

        return out_file

    def convert_all(
        self,
        category: str = "all",
        limit: Optional[int] = None,
        progress: Optional[Progress] = None,
    ) -> Dict[str, Any]:
        entries = self.load_manifest()

        if category == "rlbuddh":
            entries = [e for e in entries if e.get("section_id") == "RLBuddh"]
        elif category == "bauddha":
            entries = [e for e in entries if e.get("section_id") == "Bauddha"]

        if limit:
            entries = entries[:limit]

        # Pre-compute title counts for disambiguation
        title_counts: Counter = Counter()
        for e in entries:
            fid = e["id"]
            ftype = e.get("file_type", "tei_xml")
            if ftype == "tei_xml":
                p = RAW_XML_DIR / f"{fid}.xml"
                t = parse_tei_xml(p.read_text(encoding="utf-8"))["title"] if p.exists() else e["catalog_title"]
            else:
                p = RAW_LEGACY_DIR / f"{fid}.htm"
                t = parse_legacy_html(p.read_text(encoding="utf-8", errors="ignore"))["title"] if p.exists() else e["catalog_title"]
            title_counts[sanitize_filename(t or fid)] += 1

        task_id = None
        if progress:
            task_id = progress.add_task(
                f"[yellow]Converting {len(entries)} texts to Markdown...",
                total=len(entries),
            )

        converted_paths = []
        for e in entries:
            out = self.convert_entry(e, title_counts=title_counts)
            if out:
                converted_paths.append(out)
            if progress and task_id is not None:
                progress.advance(task_id)

        self.generate_catalog()

        return {
            "total_entries": len(entries),
            "converted_entries": len(converted_paths),
        }

    def generate_catalog(self):
        """Generate texts/CATALOG.md listing all GRETIL Buddhist texts with exact links."""
        if not MANIFEST_PATH.exists():
            return

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        # Map gretil_id to file path
        id_to_file: Dict[str, str] = {}
        if self.output_dir.exists():
            for md_file in self.output_dir.glob("**/*.md"):
                if md_file.name == "CATALOG.md":
                    continue
                try:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            fm = yaml.safe_load(parts[1])
                            if isinstance(fm, dict):
                                gid = fm.get("gretil_id")
                                if gid:
                                    rel = md_file.relative_to(self.output_dir)
                                    id_to_file[gid] = str(rel)
                except Exception as e:
                    logger.warning(f"Error parsing frontmatter in {md_file}: {e}")

        catalog_lines = [
            "# GRETIL Buddhist Sanskrit Texts - Catalog\n",
            "This catalog lists Buddhist Sanskrit texts from [GRETIL (Göttingen Register of Electronic Texts in Indian Languages)](https://gretil.sub.uni-goettingen.de/gretil.html).\n",
            f"**Total Texts Indexed:** {len(manifest)}\n",
            "## Table of Contents\n",
            "- [Buddhist Religious Literature (RLBuddh)](#buddhist-religious-literature-rlbuddh)",
            "- [Buddhist Philosophy (Bauddha)](#buddhist-philosophy-bauddha)",
            "\n---\n",
        ]

        for sec_id, sec_title in [
            ("RLBuddh", "Buddhist Religious Literature (RLBuddh)"),
            ("Bauddha", "Buddhist Philosophy (Bauddha)"),
        ]:
            sec_entries = [e for e in manifest if e.get("section_id") == sec_id]
            if not sec_entries:
                continue

            catalog_lines.append(f"## {sec_title}\n")
            catalog_lines.append(f"Total: {len(sec_entries)} texts\n")
            catalog_lines.append("| # | Title | GRETIL ID | Type | Markdown Link | Source |")
            catalog_lines.append("|---|---|---|---|---|---|")

            for e in sec_entries:
                idx = e.get("index", "")
                cat_title = e.get("catalog_title", "")
                gid = e.get("id", "")
                ftype = e.get("file_type", "")
                surl = e.get("source_url", "")

                rel_file = id_to_file.get(gid)
                if rel_file:
                    link_name = Path(rel_file).stem
                    link_str = f"[{link_name}]({rel_file})"
                else:
                    link_str = "*(not yet scraped)*"

                catalog_lines.append(
                    f"| {idx} | {cat_title} | `{gid}` | `{ftype}` | {link_str} | [Source]({surl}) |"
                )

            catalog_lines.append("\n---\n")

        catalog_path = self.output_dir / "CATALOG.md"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text("\n".join(catalog_lines), encoding="utf-8")
