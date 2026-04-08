#!/usr/bin/env python3
"""Parse .eml files and extract text, HTML, URLs, and attachments."""

import email
import email.header
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

RAW_DIR = Path("raw_emails")
EXTRACTED_DIR = Path("extracted")

# Match http(s) URLs, avoiding trailing punctuation
URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
ATTACHMENT_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}


def decode_payload(part):
    """Decode an email part's payload to a string."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def extract_urls(text: str) -> list[str]:
    """Pull all URLs from text, deduped and ordered."""
    seen = set()
    urls = []
    for url in URL_RE.findall(text):
        # Strip trailing punctuation that's likely not part of the URL
        url = url.rstrip(".,;:!?)")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def extract_email(eml_path: Path, seq: int):
    """Extract all content from a single .eml file."""
    out_dir = EXTRACTED_DIR / f"{seq:04d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    att_dir = out_dir / "attachments"

    raw = eml_path.read_bytes()
    msg = email.message_from_bytes(raw)

    # Decode subject
    subject = msg.get("Subject", "no subject")
    decoded = email.header.decode_header(subject)
    subject = "".join(
        part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        for part, enc in decoded
    )

    date_str = msg.get("Date", "")
    sender = msg.get("From", "")

    plain_parts = []
    html_parts = []
    all_urls = []
    attachment_files = []

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()

        # Save attachments
        if filename or "attachment" in disposition:
            att_dir.mkdir(exist_ok=True)
            if filename:
                # Decode encoded filenames
                decoded_fn = email.header.decode_header(filename)
                filename = "".join(
                    p.decode(enc or "utf-8") if isinstance(p, bytes) else p
                    for p, enc in decoded_fn
                )
            else:
                ext = ".bin"
                if content_type.startswith("image/"):
                    ext = "." + content_type.split("/")[1].split(";")[0]
                filename = f"attachment_{len(attachment_files)}{ext}"

            save_path = att_dir / filename
            payload = part.get_payload(decode=True)
            if payload:
                save_path.write_bytes(payload)
                attachment_files.append(filename)
            continue

        if content_type == "text/plain":
            text = decode_payload(part)
            plain_parts.append(text)
            all_urls.extend(extract_urls(text))

        elif content_type == "text/html":
            html = decode_payload(part)
            html_parts.append(html)
            # Extract text and URLs from HTML
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            plain_parts.append(text)
            # Get href URLs too
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http"):
                    all_urls.append(href)
            all_urls.extend(extract_urls(text))

        # Inline images (without Content-Disposition: attachment)
        elif content_type.startswith("image/"):
            att_dir.mkdir(exist_ok=True)
            ext = content_type.split("/")[1].split(";")[0]
            fname = f"inline_{len(attachment_files)}.{ext}"
            payload = part.get_payload(decode=True)
            if payload:
                (att_dir / fname).write_bytes(payload)
                attachment_files.append(fname)

    # Write body text
    body = "\n\n".join(plain_parts).strip()
    if body:
        (out_dir / "body.txt").write_text(body, encoding="utf-8")

    # Write URLs (deduped)
    seen = set()
    unique_urls = []
    for u in all_urls:
        u = u.rstrip(".,;:!?)")
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    if unique_urls:
        (out_dir / "urls.txt").write_text("\n".join(unique_urls), encoding="utf-8")

    # Write metadata
    metadata = {
        "seq": seq,
        "subject": subject,
        "date": date_str,
        "from": sender,
        "source_file": str(eml_path),
        "has_text": bool(body),
        "url_count": len(unique_urls),
        "attachment_count": len(attachment_files),
        "attachments": attachment_files,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return metadata


def extract_all():
    EXTRACTED_DIR.mkdir(exist_ok=True)

    index_path = RAW_DIR / "index.json"
    if not index_path.exists():
        print("No index.json found. Run fetch_emails.py first.")
        return

    manifest = json.loads(index_path.read_text())
    print(f"Extracting content from {len(manifest)} emails...")

    for entry in manifest:
        seq = entry["seq"]
        eml_path = Path(entry["file"])
        if not eml_path.exists():
            print(f"  [{seq}] MISSING: {eml_path}")
            continue

        meta = extract_email(eml_path, seq)
        parts = []
        if meta["has_text"]:
            parts.append("text")
        if meta["url_count"]:
            parts.append(f"{meta['url_count']} URLs")
        if meta["attachment_count"]:
            parts.append(f"{meta['attachment_count']} attachments")
        print(f"  [{seq}] {entry['subject'][:50]}  →  {', '.join(parts) or 'empty'}")

    print(f"\nExtraction complete. Output in {EXTRACTED_DIR}/")


if __name__ == "__main__":
    extract_all()
