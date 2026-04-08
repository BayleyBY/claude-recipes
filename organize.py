#!/usr/bin/env python3
"""Combine all extracted content into standardized markdown recipe files."""

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

EXTRACTED_DIR = Path("extracted")
SCRAPED_DIR = Path("scraped")
RECIPES_DIR = Path("recipes")
UNCATEGORIZED_DIR = RECIPES_DIR / "uncategorized"


def parse_date(date_str: str) -> str:
    """Try to parse an email date into YYYY-MM-DD."""
    if not date_str:
        return "unknown"
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10]


def sanitize_filename(name: str) -> str:
    """Turn a title into a kebab-case filename."""
    name = name.lower()
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    return name[:80] or "untitled"


def build_recipe_from_scraped(scraped_path: Path) -> str | None:
    """Read an already-formatted scraped markdown file."""
    text = scraped_path.read_text(encoding="utf-8").strip()
    return text if text else None


def build_recipe_from_text(body: str, subject: str, date: str) -> str:
    """Build a recipe markdown from plain-text email body."""
    lines = [f"# {subject}\n"]
    lines.append(f"**Source:** email")
    lines.append(f"**Date saved:** {date}")
    lines.append("")
    lines.append("## Content\n")
    lines.append(body)
    lines.append("")
    lines.append("## Notes\n")
    lines.append("*Extracted from email body — may need manual cleanup.*")
    return "\n".join(lines)


def build_recipe_from_ocr(ocr_text: str, subject: str, date: str) -> str:
    """Build a recipe markdown from OCR output."""
    lines = [f"# {subject}\n"]
    lines.append(f"**Source:** image (OCR)")
    lines.append(f"**Date saved:** {date}")
    lines.append("")
    lines.append("## Content\n")
    lines.append(ocr_text)
    lines.append("")
    lines.append("## Notes\n")
    lines.append("*Extracted via OCR — likely needs manual cleanup and formatting.*")
    return "\n".join(lines)


def organize():
    UNCATEGORIZED_DIR.mkdir(parents=True, exist_ok=True)

    if not EXTRACTED_DIR.exists():
        print("No extracted/ directory. Run extract_content.py first.")
        return

    # Build a mapping from email_id → list of scraped files
    scraped_by_email = {}
    if SCRAPED_DIR.exists():
        scraped_index = SCRAPED_DIR / "index.json"
        if scraped_index.exists():
            for entry in json.loads(scraped_index.read_text()):
                eid = entry["email_id"]
                scraped_by_email.setdefault(eid, []).append(Path(entry["file"]))

    recipes = []
    recipe_count = 0

    for meta_file in sorted(EXTRACTED_DIR.glob("*/metadata.json")):
        email_dir = meta_file.parent
        email_id = email_dir.name
        meta = json.loads(meta_file.read_text())
        subject = meta["subject"]
        date = parse_date(meta.get("date", ""))

        # Check what content we have
        has_scraped = email_id in scraped_by_email
        body_file = email_dir / "body.txt"
        ocr_file = email_dir / "ocr_output.txt"
        has_body = body_file.exists()
        has_ocr = ocr_file.exists()

        # Strategy: prefer scraped recipe pages, then body text, then OCR
        # If we have scraped content, each scraped URL becomes its own recipe file
        if has_scraped:
            for scraped_path in scraped_by_email[email_id]:
                content = build_recipe_from_scraped(scraped_path)
                if content:
                    # Extract title from the scraped markdown
                    first_line = content.split("\n")[0]
                    title = first_line.lstrip("# ").strip() or subject
                    fname = sanitize_filename(title)

                    # Add date to markdown if not already present
                    if "**Date saved:**" not in content:
                        content = content.replace(
                            "\n\n## Ingredients",
                            f"\n**Date saved:** {date}\n\n## Ingredients"
                        )

                    out_path = UNCATEGORIZED_DIR / f"{fname}.md"
                    # Avoid overwriting
                    if out_path.exists():
                        out_path = UNCATEGORIZED_DIR / f"{fname}-{email_id}.md"
                    out_path.write_text(content, encoding="utf-8")
                    recipe_count += 1
                    recipes.append({"title": title, "file": str(out_path)})
                    print(f"  [scraped] {title[:60]}")

        # Also save body text if it looks substantial (not just links)
        if has_body:
            body = body_file.read_text(encoding="utf-8").strip()
            # Skip if body is tiny or is just a URL dump
            non_url_text = re.sub(r'https?://\S+', '', body).strip()
            if len(non_url_text) > 150:
                fname = sanitize_filename(subject)
                out_path = UNCATEGORIZED_DIR / f"{fname}-text.md"
                if out_path.exists():
                    out_path = UNCATEGORIZED_DIR / f"{fname}-text-{email_id}.md"
                content = build_recipe_from_text(body, subject, date)
                out_path.write_text(content, encoding="utf-8")
                recipe_count += 1
                recipes.append({"title": subject, "file": str(out_path)})
                print(f"  [text]    {subject[:60]}")

        # OCR output
        if has_ocr:
            ocr = ocr_file.read_text(encoding="utf-8").strip()
            if len(ocr) > 50:
                fname = sanitize_filename(subject)
                out_path = UNCATEGORIZED_DIR / f"{fname}-ocr.md"
                if out_path.exists():
                    out_path = UNCATEGORIZED_DIR / f"{fname}-ocr-{email_id}.md"
                content = build_recipe_from_ocr(ocr, subject, date)
                out_path.write_text(content, encoding="utf-8")
                recipe_count += 1
                recipes.append({"title": f"{subject} (OCR)", "file": str(out_path)})
                print(f"  [ocr]     {subject[:60]}")

    # Generate INDEX.md
    index_lines = ["# Recipe Book — Index\n"]
    index_lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n")
    index_lines.append(f"**Total recipes:** {len(recipes)}\n")
    index_lines.append("## Uncategorized\n")
    for r in sorted(recipes, key=lambda x: x["title"].lower()):
        rel_path = Path(r["file"]).relative_to(RECIPES_DIR)
        index_lines.append(f"- [{r['title']}]({rel_path})")
    index_lines.append("")

    index_path = RECIPES_DIR / "INDEX.md"
    index_path.write_text("\n".join(index_lines), encoding="utf-8")

    print(f"\nOrganized {recipe_count} recipes into {UNCATEGORIZED_DIR}/")
    print(f"Index: {index_path}")


if __name__ == "__main__":
    organize()
