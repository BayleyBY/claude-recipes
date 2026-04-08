#!/usr/bin/env python3
"""OCR image attachments from extracted emails using tesseract."""

import json
import shutil
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

EXTRACTED_DIR = Path("extracted")
RECIPES_IMAGES_DIR = Path("recipes/images")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def preprocess_image(img: Image.Image) -> Image.Image:
    """Enhance image for better OCR results."""
    # Convert to RGB if needed
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Resize small images
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Convert to grayscale
    img = img.convert("L")

    # Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)

    # Sharpen
    img = img.filter(ImageFilter.SHARPEN)

    return img


def ocr_image(image_path: Path) -> str:
    """Run OCR on a single image, return extracted text."""
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"    Cannot open image: {e}")
        return ""

    processed = preprocess_image(img)
    text = pytesseract.image_to_string(processed, lang="eng")
    return text.strip()


def process_all():
    RECIPES_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if not EXTRACTED_DIR.exists():
        print("No extracted/ directory. Run extract_content.py first.")
        return

    processed = 0
    for att_dir in sorted(EXTRACTED_DIR.glob("*/attachments")):
        email_id = att_dir.parent.name
        images = [
            f for f in att_dir.iterdir()
            if f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            continue

        print(f"[{email_id}] Found {len(images)} image(s)")
        ocr_texts = []

        for img_path in images:
            print(f"  OCR: {img_path.name}...", end=" ")
            text = ocr_image(img_path)

            if text:
                print(f"({len(text)} chars)")
                ocr_texts.append(f"--- {img_path.name} ---\n{text}")
            else:
                print("(no text found)")

            # Copy original to recipes/images/
            dest = RECIPES_IMAGES_DIR / f"{email_id}_{img_path.name}"
            shutil.copy2(img_path, dest)

        if ocr_texts:
            out_path = att_dir.parent / "ocr_output.txt"
            out_path.write_text("\n\n".join(ocr_texts), encoding="utf-8")
            print(f"  → Saved OCR text to {out_path}")
            processed += 1

    print(f"\nOCR complete. Processed images from {processed} emails.")
    print(f"Original images copied to {RECIPES_IMAGES_DIR}/")


if __name__ == "__main__":
    process_all()
