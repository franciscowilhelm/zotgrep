#!/usr/bin/env python3
"""Generate a .env file with ZOTERO_PUBLICATION_TITLE_FILTER from a CSV list."""

from pathlib import Path

INPUT_CSV = Path(__file__).with_name("abs_43_filter.csv")
OUTPUT_ENV = Path(__file__).with_name("abs_43_filter.env")

lines = [line.strip() for line in INPUT_CSV.read_text(encoding="utf-8").splitlines()]
items = [line for line in lines if line]
value = ", ".join(items)
OUTPUT_ENV.write_text(f'ZOTERO_PUBLICATION_TITLE_FILTER="{value}"\n', encoding="utf-8")
print(f"Wrote {OUTPUT_ENV}")
