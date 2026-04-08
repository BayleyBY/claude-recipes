#!/usr/bin/env python3
"""List all Gmail labels/folders visible via IMAP."""
import imaplib
import os
from dotenv import load_dotenv

load_dotenv()

conn = imaplib.IMAP4_SSL("imap.gmail.com")
conn.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])

status, labels = conn.list()
for label in sorted(labels):
    print(label.decode())

conn.logout()
