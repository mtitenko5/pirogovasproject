import os
from uuid import uuid4
import json
import csv
import zipfile
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from typing import Any


ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def round_numbers(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, list):
        return [round_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: round_numbers(item) for key, item in value.items()}
    return value


def parse_number_if_possible(value: str) -> Any:
    normalized = value.strip().replace(",", ".")
    try:
        return round(float(normalized), 3)
    except ValueError:
        return value.strip()


def image_content_type(extension: str) -> str:
    return "image/png" if extension == ".png" else "image/jpeg"


def extract_images_from_zip(zip_bytes: bytes, filename: str) -> list[dict]:
    """Unpacks all CT images from a ZIP archive."""
    images = []

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                image_name = PurePosixPath(info.filename).name
                extension = PurePosixPath(image_name).suffix.lower()

                if extension not in ALLOWED_IMAGE_EXTENSIONS:
                    continue

                images.append({
                    "filename": image_name,
                    "bytes": archive.read(info),
                    "content_type": image_content_type(extension),
                })
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{filename} is not a valid ZIP archive") from exc

    if not images:
        raise ValueError("ZIP archive does not contain PNG/JPG/JPEG images")

    return images

def parse_measurements_file(file_bytes: bytes, filename: str) -> dict:
    """Parses the measurements file (CSV or JSON) and returns a structured dict"""
    if filename.endswith(".json"):
        return round_numbers(json.loads(file_bytes.decode("utf-8-sig")))
    elif filename.endswith(".csv"):
        content = file_bytes.decode('utf-8-sig')
        reader = csv.reader(StringIO(content))
        data = {}
        for row in reader:
            if not row:
                continue
            if len(row) < 2:
                raise ValueError("Invalid CSV format: each row must have at least 2 columns")
            key = row[0].strip()
            value = row[1].strip()
            data[key] = parse_number_if_possible(value)
        return data
    else:
        raise ValueError("Unsupported file format: only CSV and JSON are allowed")
        
