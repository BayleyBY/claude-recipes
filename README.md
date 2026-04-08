# claude-recipes

A personal recipe book pipeline that fetches recipe emails from Gmail, extracts and organizes the content into markdown files, and builds either a printable PDF book or an interactive web page.

## How it works

```
Gmail (recipe emails)
  └─ fetch_emails.py     → raw_emails/
  └─ extract_content.py  → extracted/   (body text, URLs, attachments)
  └─ scrape_recipes.py   → scraped/     (structured data from linked recipe sites)
  └─ ocr_images.py       → extracted/   (OCR for image attachments)
  └─ organize.py         → recipes/     (categorized markdown files)

recipes/
  └─ build_pdf.py        → recipe_book.pdf
  └─ build_web.py        → recipe_book_web.html
```

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/BayleyBY/claude-recipes.git
cd claude-recipes
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`weasyprint` also requires system libraries — see [weasyprint.org/docs/install](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) for OS-specific instructions.

**2. Configure Gmail access**

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password (not your login password)
GMAIL_LABEL=Recipes                       # Gmail label applied to recipe emails
```

To generate a Gmail App Password: Google Account → Security → 2-Step Verification → App passwords.

## Running the pipeline

Run each step in order, or only the steps you need:

```bash
python fetch_emails.py       # Download emails with the Recipes label
python extract_content.py    # Extract body text, URLs, and attachments
python scrape_recipes.py     # Scrape structured data from recipe URLs
python ocr_images.py         # OCR any image attachments (requires tesseract)
python organize.py           # Assemble into categorized markdown files
```

## Building the output

**Interactive web page** (open in any browser):
```bash
python build_web.py
open recipe_book_web.html
```

**Printable PDF**:
```bash
python build_pdf.py
```

## Recipe organization

`organize.py` writes markdown files into `recipes/<category>/`. The category is determined by the subdirectory name. To rename or recategorize a recipe, move its `.md` file to the appropriate folder and rebuild.

Categories used: `breakfast`, `appetizers`, `soups`, `salads`, `sides`, `mains`, `breads`, `sauces`, `desserts`.

## Dependencies

| Package | Purpose |
|---|---|
| `beautifulsoup4` | HTML parsing for web scraping |
| `recipe-scrapers` | Structured extraction from recipe sites |
| `pytesseract` + `Pillow` | OCR for image attachments |
| `requests` | HTTP fetching |
| `markdown` | Markdown → HTML conversion |
| `weasyprint` | HTML → PDF rendering |
| `Jinja2` | HTML templating |
| `python-dotenv` | `.env` loading |
