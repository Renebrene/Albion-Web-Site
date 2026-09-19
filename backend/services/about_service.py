import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "about_company.json"
)


def get_about():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)
