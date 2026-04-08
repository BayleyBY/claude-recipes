#!/usr/bin/env python3
"""Scrape recipe content from URLs found in emails."""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

EXTRACTED_DIR = Path("extracted")
SCRAPED_DIR = Path("scraped")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
})

# Skip non-recipe URLs
SKIP_DOMAINS = {
    "google.com", "youtube.com", "facebook.com", "twitter.com",
    "instagram.com", "pinterest.com", "amazon.com", "mailto:",
    "maps.google.com", "accounts.google.com",
}


def is_recipe_url(url: str) -> bool:
    """Quick filter to skip obviously non-recipe URLs."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    return not any(skip in domain for skip in SKIP_DOMAINS)


def scrape_with_library(url: str, html: str) -> dict | None:
    """Try recipe-scrapers for structured extraction."""
    try:
        scraper = scrape_html(html=html, org_url=url)
        return {
            "title": scraper.title(),
            "ingredients": scraper.ingredients(),
            "instructions": scraper.instructions(),
            "yields": scraper.yields() if hasattr(scraper, 'yields') else "",
            "total_time": scraper.total_time() if hasattr(scraper, 'total_time') else "",
            "image": scraper.image() if hasattr(scraper, 'image') else "",
        }
    except Exception:
        return None


def scrape_json_ld(soup: BeautifulSoup) -> dict | None:
    """Look for JSON-LD Recipe schema markup."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph wrapper
        if isinstance(data, dict) and "@graph" in data:
            data = data["@graph"]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "Recipe":
                    data = item
                    break
            else:
                continue

        if isinstance(data, dict) and data.get("@type") == "Recipe":
            ingredients = data.get("recipeIngredient", [])
            instructions = data.get("recipeInstructions", [])
            # Instructions can be strings or HowToStep objects
            if instructions and isinstance(instructions[0], dict):
                instructions = [
                    step.get("text", "") for step in instructions
                ]
            return {
                "title": data.get("name", ""),
                "ingredients": ingredients,
                "instructions": "\n".join(
                    f"{i+1}. {s}" for i, s in enumerate(instructions)
                ) if isinstance(instructions, list) else str(instructions),
                "yields": data.get("recipeYield", ""),
                "total_time": data.get("totalTime", ""),
                "image": data.get("image", ""),
            }
    return None


def scrape_fallback(soup: BeautifulSoup, url: str) -> dict | None:
    """Generic extraction from article content."""
    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)

    # Try to find main content
    article = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"recipe|content|entry", re.I))
        or soup.find("main")
    )
    if not article:
        return None

    text = article.get_text(separator="\n", strip=True)
    if len(text) < 100:
        return None

    return {
        "title": title,
        "ingredients": [],
        "instructions": text,
        "yields": "",
        "total_time": "",
        "image": "",
    }


def recipe_to_markdown(data: dict, url: str) -> str:
    """Convert structured recipe data to markdown."""
    lines = [f"# {data['title']}\n"]
    lines.append(f"**Source:** {url}")

    if data.get("yields"):
        lines.append(f"**Yields:** {data['yields']}")
    if data.get("total_time"):
        lines.append(f"**Total time:** {data['total_time']}")

    lines.append("")

    if data.get("ingredients"):
        lines.append("## Ingredients\n")
        for ing in data["ingredients"]:
            lines.append(f"- {ing}")
        lines.append("")

    if data.get("instructions"):
        lines.append("## Instructions\n")
        instructions = data["instructions"]
        if isinstance(instructions, str):
            lines.append(instructions)
        else:
            for i, step in enumerate(instructions, 1):
                lines.append(f"{i}. {step}")
        lines.append("")

    return "\n".join(lines)


def scrape_url(url: str) -> tuple[str | None, str | None]:
    """Scrape a single URL; return (markdown, title) or (None, None)."""
    try:
        resp = SESSION.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    Failed to fetch: {e}")
        return None, None

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Try methods in order of quality
    data = scrape_with_library(url, html)
    source = "recipe-scrapers"

    if not data:
        data = scrape_json_ld(soup)
        source = "JSON-LD"

    if not data:
        data = scrape_fallback(soup, url)
        source = "fallback"

    if not data:
        return None, None

    print(f"    Extracted via {source}: {data['title'][:50]}")
    return recipe_to_markdown(data, url), data.get("title", "")


def scrape_all():
    SCRAPED_DIR.mkdir(exist_ok=True)

    if not EXTRACTED_DIR.exists():
        print("No extracted/ directory. Run extract_content.py first.")
        return

    # Collect all URLs across all emails
    all_urls = []
    for urls_file in sorted(EXTRACTED_DIR.glob("*/urls.txt")):
        email_id = urls_file.parent.name
        meta_file = urls_file.parent / "metadata.json"
        subject = ""
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            subject = meta.get("subject", "")

        for url in urls_file.read_text().strip().splitlines():
            url = url.strip()
            if url and is_recipe_url(url):
                all_urls.append((email_id, url, subject))

    print(f"Found {len(all_urls)} candidate URLs to scrape.\n")

    results = []
    for i, (email_id, url, subject) in enumerate(all_urls, 1):
        domain = urlparse(url).netloc.replace("www.", "")
        print(f"[{i}/{len(all_urls)}] {domain}: {url[:80]}")

        md, title = scrape_url(url)
        if md:
            safe = re.sub(r'[^\w\s-]', '', title or domain)
            safe = re.sub(r'\s+', '_', safe.strip())[:60]
            filename = f"{email_id}_{safe}.md"
            out_path = SCRAPED_DIR / filename
            out_path.write_text(md, encoding="utf-8")
            results.append({"email_id": email_id, "url": url, "file": str(out_path)})
            print(f"    → Saved: {filename}")
        else:
            print(f"    → No recipe content found")

        # Be polite to servers
        time.sleep(1)

    # Save scraping manifest
    manifest_path = SCRAPED_DIR / "index.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nScraped {len(results)}/{len(all_urls)} URLs. Results in {SCRAPED_DIR}/")


if __name__ == "__main__":
    scrape_all()
