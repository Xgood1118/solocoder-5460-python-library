import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"

DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)

BOOKS_FILE = DATA_DIR / "books.json"
SHELVES_FILE = DATA_DIR / "shelves.json"
BORROW_RECORDS_FILE = DATA_DIR / "borrow_records.json"
MISPLACEMENT_RECORDS_FILE = DATA_DIR / "misplacement_records.json"
INSPECTION_RECORDS_FILE = DATA_DIR / "inspection_records.json"
CATEGORY_MAP_FILE = CONFIG_DIR / "category_map.json"
CUSTOM_PATHS_FILE = CONFIG_DIR / "custom_paths.json"

HTTP_PORT = int(os.environ.get("LIBRARY_HTTP_PORT", 5000))

FLOORS = 5
ZONES_PER_FLOOR = 8
ROWS_PER_ZONE = 6
LEVELS_PER_ROW = 6
BOOKS_PER_LEVEL = 30

ZONE_LABELS = [chr(ord('A') + i) for i in range(ZONES_PER_FLOOR)]

RESERVATION_AREA_CODE = "R-RES-0-0-0"


def load_json(filepath, default=None):
    if default is None:
        default = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
