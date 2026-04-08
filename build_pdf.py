#!/usr/bin/env python3
"""Generate a PDF recipe book from organized markdown files."""

import re
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

RECIPES_DIR = Path("recipes")
TEMPLATES_DIR = Path("templates")
OUTPUT_PDF = Path("recipe_book.pdf")

# Category display order (others will be appended alphabetically)
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
    """Extract title from the first H1 heading."""
    match = re.match(r'^#\s+(.+)', md_text, re.MULTILINE)
    return match.group(1).strip() if match else "Untitled Recipe"


def md_to_recipe_html(md_text: str) -> str:
    """Convert markdown to HTML, splitting into meta and body."""
    html = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

    # Wrap meta lines (Source, Date, Yields, etc.) in a meta div
    # They appear as <p><strong>Key:</strong> value</p> right after the h1
    html = re.sub(
        r'(<p><strong>(?:Source|Date saved|Yields|Total time):</strong>.*?</p>\s*)+',
        lambda m: f'<div class="meta">{m.group(0)}</div>',
        html,
    )

    # Remove the H1 (it's rendered separately by the template... actually we keep
    # it since each recipe div renders its own content)
    return html


def collect_recipes() -> dict[str, list[dict]]:
    """Walk the recipes directory and collect all markdown files by category."""
    categories = {}
    recipe_id = 0

    for md_file in sorted(RECIPES_DIR.rglob("*.md")):
        if md_file.name == "INDEX.md":
            continue

        # Category is the parent directory name
        rel = md_file.relative_to(RECIPES_DIR)
        if len(rel.parts) > 1:
            category = rel.parts[0].replace("_", " ").title()
        else:
            category = "Uncategorized"

        md_text = md_file.read_text(encoding="utf-8")
        title = extract_title(md_text)
        html = md_to_recipe_html(md_text)

        categories.setdefault(category, []).append({
            "id": recipe_id,
            "title": title,
            "html": html,
            "file": str(md_file),
        })
        recipe_id += 1

    # Sort categories by preferred order
    order_map = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    sorted_cats = dict(sorted(
        categories.items(),
        key=lambda x: (order_map.get(x[0], 99), x[0])
    ))

    # Sort recipes within each category alphabetically
    for cat in sorted_cats:
        sorted_cats[cat].sort(key=lambda r: r["title"].lower())

    return sorted_cats


def build_pdf():
    categories = collect_recipes()
    total = sum(len(r) for r in categories.values())

    if total == 0:
        print("No recipes found in recipes/. Run organize.py first.")
        return

    print(f"Building PDF with {total} recipes in {len(categories)} categories...")
    for cat, recs in categories.items():
        print(f"  {cat}: {len(recs)} recipes")

    # Render HTML
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("book.html")

    html_content = template.render(
        title="Recipe Book",
        subtitle=f"Collected recipes — {datetime.now().strftime('%B %Y')}",
        categories=categories,
    )

    # Debug: save intermediate HTML
    debug_html = Path("recipe_book.html")
    debug_html.write_text(html_content, encoding="utf-8")
    print(f"\nIntermediate HTML saved to {debug_html}")

    # Generate PDF
    print(f"Generating PDF...")
    HTML(string=html_content, base_url=str(Path.cwd())).write_pdf(str(OUTPUT_PDF))
    print(f"PDF saved to {OUTPUT_PDF}")


if __name__ == "__main__":
    build_pdf()
