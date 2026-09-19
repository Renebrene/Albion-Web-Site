import json
from pathlib import Path

DATA_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "contacts.json"
)


def get_contacts():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)
