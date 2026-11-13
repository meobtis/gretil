from pathlib import Path

BASE_URL = "https://gretil.sub.uni-goettingen.de"
INDEX_URL = f"{BASE_URL}/gretil.html"

# Directory layout
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_XML_DIR = RAW_DIR / "xml"
RAW_LEGACY_DIR = RAW_DIR / "legacy"
MANIFEST_PATH = DATA_DIR / "manifest.json"
UNAVAILABLE_PATH = DATA_DIR / "unavailable.json"
TEXTS_DIR = PROJECT_ROOT / "texts"

# Request headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Network defaults
DEFAULT_CONCURRENCY = 4  # GRETIL is a university server: be gentle
REQUEST_DELAY = 0.2  # seconds to wait after each download
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 4
