#!/usr/bin/env python3
"""Generate an interactive web recipe book from organized markdown files."""

import re
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

RECIPES_DIR = Path("recipes")
TEMPLATES_DIR = Path("templates")
OUTPUT_HTML = Path("recipe_book_web.html")

CATEGORY_ORDER = [
    "Breakfast",
    "Appetizers",
    "Soups",
    "Salads",
    "Sides",
    "Mains",
    "Breads",
    "Sauces",
    "Desserts",
    "Drinks",
]


def extract_title(md_text: str) -> str:
    match = re.match(r'^#\s+(.+)', md_text, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled Recipe"


def extract_search_text(md_text: str) -> str:
    """Return lowercased plain text for client-side search (title + all content)."""
    # Strip markdown syntax characters
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md_text)  # [text](url) → text
    text = re.sub(r'[#*`>_~]', ' ', text)
    text = re.sub(r'https?://\S+', ' ', text)                 # remove bare URLs
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def md_to_recipe_html(md_text: str) -> str:
    """Convert markdown to HTML and wrap meta lines in a .meta div."""
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    html = re.sub(
        r'(<p><strong>(?:Source|Date saved|Yields|Total time):</strong>.*?</p>\s*)+',
        lambda m: f'<div class="meta">{m.group(0)}</div>',
        html,
    )
    return html


def collect_recipes() -> dict[str, list[dict]]:
    """Walk the recipes directory and return recipes grouped by category."""
    categories: dict[str, list[dict]] = {}
    recipe_id = 0

    for md_file in sorted(RECIPES_DIR.rglob("*.md")):
        if md_file.name == "INDEX.md":
            continue

        rel = md_file.relative_to(RECIPES_DIR)
        category = rel.parts[0].replace("_", " ").title() if len(rel.parts) > 1 else "Uncategorized"

        md_text = md_file.read_text(encoding="utf-8")
        categories.setdefault(category, []).append({
            "id": recipe_id,
            "title": extract_title(md_text),
            "html": md_to_recipe_html(md_text),
            "search_text": extract_search_text(md_text),
            "file": str(md_file),
        })
        recipe_id += 1

    order_map = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    sorted_cats = dict(sorted(
        categories.items(),
        key=lambda x: (order_map.get(x[0], 99), x[0])
    ))

    for cat in sorted_cats:
        sorted_cats[cat].sort(key=lambda r: r["title"].lower())

    return sorted_cats


def build_web():
    categories = collect_recipes()
    total = sum(len(r) for r in categories.values())

    if total == 0:
        print("No recipes found in recipes/. Run organize.py first.")
        return

    print(f"Building web book: {total} recipes across {len(categories)} categories")
    for cat, recs in categories.items():
        print(f"  {cat}: {len(recs)}")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("web.html")

    html_content = template.render(
        title="Recipe Book",
        subtitle=f"Collected recipes — {datetime.now().strftime('%B %Y')}",
        categories=categories,
        total_count=total,
    )

    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"\nSaved → {OUTPUT_HTML}")


if __name__ == "__main__":
    build_web()
