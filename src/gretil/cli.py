import asyncio
import json
import logging
from typing import Optional
import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table

from .client import GRETILClient
from .config import (
    DEFAULT_CONCURRENCY,
    MANIFEST_PATH,
    RAW_LEGACY_DIR,
    RAW_XML_DIR,
    TEXTS_DIR,
)
from .converter import GRETILConverter
from .indexer import GRETILIndexer
from .scraper import GRETILScraper

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose debug logging.")
def main(verbose: bool):
    """Deterministic GRETIL Buddhist Sanskrit scraper and Markdown converter."""
    setup_logging(verbose)


@main.command()
@click.option(
    "--category",
    type=click.Choice(["rlbuddh", "bauddha", "all"]),
    default="rlbuddh",
    help="Category to index (rlbuddh = Buddhist Religious Literature, bauddha = Buddhist Philosophy).",
)
@click.option("--limit", type=int, default=None, help="Limit number of texts to index.")
@click.option("-f", "--force", is_flag=True, help="Re-fetch index page even if cached.")
def index(category: str, limit: Optional[int], force: bool):
    """Index GRETIL Buddhist Sanskrit texts into data/manifest.json."""
    console.print(
        Panel.fit(
            f"[bold cyan]Indexing GRETIL Buddhist Texts[/bold cyan]\n"
            f"Category: [yellow]{category}[/yellow]"
            + (f" | Limit: [yellow]{limit}[/yellow]" if limit else ""),
            title="GRETIL Indexer",
        )
    )

    async def run():
        async with GRETILClient() as client:
            indexer = GRETILIndexer(client)
            entries = await indexer.build_manifest(
                category=category, limit=limit, force=force
            )
            console.print(
                f"[bold green]✓[/bold green] Indexed {len(entries)} texts. Saved to [cyan]{MANIFEST_PATH}[/cyan]"
            )

    asyncio.run(run())


@main.command()
@click.option(
    "--category",
    type=click.Choice(["rlbuddh", "bauddha", "all"]),
    default="all",
    help="Category to scrape.",
)
@click.option("--limit", type=int, default=None, help="Limit number of texts to download.")
@click.option(
    "--concurrency",
    type=int,
    default=DEFAULT_CONCURRENCY,
    help="Concurrent download connections.",
)
@click.option("-f", "--force", is_flag=True, help="Re-fetch even if cached locally.")
def scrape(category: str, limit: Optional[int], concurrency: int, force: bool):
    """Scrape raw TEI XML and legacy files for texts listed in manifest."""
    console.print(
        Panel.fit(
            f"[bold green]Scraping GRETIL Texts[/bold green]\n"
            f"Category: [yellow]{category}[/yellow] | Concurrency: [yellow]{concurrency}[/yellow]"
            + (f" | Limit: [yellow]{limit}[/yellow]" if limit else ""),
            title="GRETIL Scraper",
        )
    )

    async def run():
        async with GRETILClient(concurrency=concurrency) as client:
            scraper = GRETILScraper(client)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                stats = await scraper.scrape_all(
                    category=category, limit=limit, force=force, progress=progress
                )
            console.print(
                f"[bold green]✓[/bold green] Downloaded {stats['success']}/{stats['total']} files."
                + (f" ([red]{stats['failed']} failed[/red])" if stats["failed"] else "")
            )

    asyncio.run(run())


@main.command()
@click.option(
    "--category",
    type=click.Choice(["rlbuddh", "bauddha", "all"]),
    default="all",
    help="Category to convert.",
)
@click.option("--limit", type=int, default=None, help="Limit number of texts to convert.")
def convert(category: str, limit: Optional[int]):
    """Convert cached TEI XML and legacy HTML texts to formatted Markdown."""
    console.print(
        Panel.fit(
            f"[bold yellow]Converting GRETIL Texts to Markdown[/bold yellow]\n"
            f"Category: [yellow]{category}[/yellow]"
            + (f" | Limit: [yellow]{limit}[/yellow]" if limit else ""),
            title="GRETIL Converter",
        )
    )

    converter = GRETILConverter()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        stats = converter.convert_all(
            category=category, limit=limit, progress=progress
        )

    console.print(
        f"[bold green]✓[/bold green] Converted {stats['converted_entries']}/{stats['total_entries']} texts into [cyan]{TEXTS_DIR}[/cyan]"
    )
    console.print(f"[bold green]✓[/bold green] Generated catalog index at [cyan]{TEXTS_DIR / 'CATALOG.md'}[/cyan]")


@main.command(name="all")
@click.option(
    "--category",
    type=click.Choice(["rlbuddh", "bauddha", "all"]),
    default="rlbuddh",
    help="Category to process (default: rlbuddh).",
)
@click.option("--limit", type=int, default=None, help="Limit number of texts to process.")
@click.option(
    "--concurrency",
    type=int,
    default=DEFAULT_CONCURRENCY,
    help="Concurrent download connections.",
)
@click.pass_context
def process_all(ctx, category: str, limit: Optional[int], concurrency: int):
    """Run full pipeline: index -> scrape -> convert."""
    console.print(
        Panel.fit(
            f"[bold magenta]Running Full GRETIL Pipeline (Index -> Scrape -> Convert)[/bold magenta]\n"
            f"Category: [yellow]{category}[/yellow] | Concurrency: [yellow]{concurrency}[/yellow]"
            + (f" | Limit: [yellow]{limit}[/yellow]" if limit else ""),
            title="GRETIL Full Pipeline",
        )
    )
    ctx.invoke(index, category=category, limit=limit, force=False)
    ctx.invoke(scrape, category=category, limit=limit, concurrency=concurrency, force=False)
    ctx.invoke(convert, category=category, limit=limit)
    console.print("[bold green]✓ Pipeline completed successfully![/bold green]")


@main.command()
def info():
    """Display repository status and counts."""
    table = Table(title="GRETIL Repository Status")
    table.add_column("Item", style="cyan")
    table.add_column("Count / Status", style="green")

    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        rl_count = sum(1 for e in manifest if e.get("section_id") == "RLBuddh")
        b_count = sum(1 for e in manifest if e.get("section_id") == "Bauddha")
        table.add_row("Manifest", f"✓ Exists ({len(manifest)} texts: {rl_count} RLBuddh, {b_count} Bauddha)")
    else:
        table.add_row("Manifest", "✗ Not found (run 'gretil index')")

    xml_cached = len(list(RAW_XML_DIR.glob("*.xml"))) if RAW_XML_DIR.exists() else 0
    legacy_cached = len(list(RAW_LEGACY_DIR.glob("*.htm*"))) if RAW_LEGACY_DIR.exists() else 0
    table.add_row("Cached TEI XML Files", str(xml_cached))
    table.add_row("Cached Legacy HTML Files", str(legacy_cached))

    md_files = len(list(TEXTS_DIR.glob("**/*.md"))) if TEXTS_DIR.exists() else 0
    table.add_row("Generated Markdown Files", str(md_files))

    console.print(table)


if __name__ == "__main__":
    main()
