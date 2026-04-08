#!/usr/bin/env python3
"""Fetch recipe emails from Gmail via IMAP and save as .eml files."""

import imaplib
import json
import os
import re
import email
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_LABEL = os.environ.get("GMAIL_LABEL", "Recipes")
RAW_DIR = Path("raw_emails")


def sanitize_filename(name: str) -> str:
    """Turn an email subject into a safe filename."""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:80] or "no_subject"


def fetch_emails():
    RAW_DIR.mkdir(exist_ok=True)

    print(f"Connecting to Gmail as {GMAIL_ADDRESS}...")
    conn = imaplib.IMAP4_SSL("imap.gmail.com")
    conn.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

    # Gmail labels with spaces/special chars are quoted automatically by select
    label = GMAIL_LABEL
    status, _ = conn.select(f'"{label}"')
    if status != "OK":
        # Try Gmail's X-GM-LABELS search on All Mail as fallback
        print(f"Could not select label '{label}' directly, searching All Mail...")
        conn.select('"[Gmail]/All Mail"')
        status, msg_ids = conn.search(None, f'X-GM-LABELS "{label}"')
    else:
        status, msg_ids = conn.search(None, "ALL")

    if status != "OK" or not msg_ids[0]:
        print("No emails found.")
        conn.logout()
        return

    ids = msg_ids[0].split()
    print(f"Found {len(ids)} emails in '{label}'.")

    manifest = []

    for seq, uid in enumerate(ids, 1):
        status, data = conn.fetch(uid, "(RFC822)")
        if status != "OK":
            print(f"  Skipping message {uid}: fetch failed")
            continue

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        subject = msg.get("Subject", "no subject")
        # Decode encoded subjects
        decoded_parts = email.header.decode_header(subject)
        subject = "".join(
            part.decode(enc or "utf-8") if isinstance(part, bytes) else part
            for part, enc in decoded_parts
        )

        date_str = msg.get("Date", "")
        sender = msg.get("From", "")
        msg_id = msg.get("Message-ID", f"msg_{seq}")

        safe_name = f"{seq:04d}_{sanitize_filename(subject)}"
        eml_path = RAW_DIR / f"{safe_name}.eml"

        eml_path.write_bytes(raw)
        print(f"  [{seq}/{len(ids)}] {subject[:60]}")

        manifest.append({
            "seq": seq,
            "file": str(eml_path),
            "subject": subject,
            "date": date_str,
            "from": sender,
            "message_id": msg_id,
        })

    index_path = RAW_DIR / "index.json"
    index_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(manifest)} emails. Manifest: {index_path}")

    conn.close()
    conn.logout()


if __name__ == "__main__":
    fetch_emails()
