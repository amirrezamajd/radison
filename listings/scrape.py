from __future__ import annotations

import re
from html import unescape
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.db import transaction

from .models import Property, PropertyImage

CRM_HOST = "https://crmamlak.app"
TOKEN_RE = re.compile(r"crmamlak\.app/p/([a-zA-Z0-9_-]+)", re.IGNORECASE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


def extract_token(url: str) -> str | None:
    match = TOKEN_RE.search((url or "").strip())
    return match.group(1) if match else None


def normalize_url(url: str) -> tuple[str, str]:
    token = extract_token(url)
    if not token:
        raise ValueError("لینک معتبر نیست. نمونه درست: https://crmamlak.app/p/xxxxx")
    return token, f"{CRM_HOST}/p/{token}"


def clean_text(value: str) -> str:
    return unescape(re.sub(r"\s+", " ", value or "")).strip()


def parse_price_chip(text: str) -> tuple[str, str]:
    clean = clean_text(text)
    parts = [part.strip() for part in clean.split("·")]
    price_text = parts[0] if parts else clean
    price_per_meter = parts[1] if len(parts) > 1 else ""
    return price_text, price_per_meter


def fetch_html(source_url: str) -> str:
    response = requests.get(source_url, headers=HEADERS, timeout=45)
    if response.status_code != 200:
        raise ValueError(f"صفحه ملک در دسترس نیست (کد {response.status_code})")
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def download_image(remote_url: str) -> ContentFile:
    response = requests.get(
        remote_url,
        headers={**HEADERS, "Referer": f"{CRM_HOST}/", "Accept": "image/*,*/*;q=0.8"},
        timeout=60,
    )
    if response.status_code != 200:
        raise ValueError(f"دانلود تصویر ناموفق بود: {remote_url}")

    filename = PurePosixPath(remote_url.split("?", 1)[0]).name or "image.jpg"
    return ContentFile(BytesIO(response.content).getvalue(), name=filename)


@transaction.atomic
def import_property_from_url(url: str) -> Property:
    token, source_url = normalize_url(url)
    html = fetch_html(source_url)
    soup = BeautifulSoup(html, "html.parser")

    title = clean_text(
        (soup.select_one(".pp-title").get_text() if soup.select_one(".pp-title") else "")
        or (soup.title.get_text() if soup.title else "")
        or "ملک بدون عنوان"
    )
    price_text, price_per_meter = parse_price_chip(
        soup.select_one(".pp-price-chip").get_text() if soup.select_one(".pp-price-chip") else ""
    )
    property_type = clean_text(
        soup.select_one(".pp-badge--type").get_text() if soup.select_one(".pp-badge--type") else ""
    )
    deal_type = clean_text(
        soup.select_one(".pp-badge--deal").get_text() if soup.select_one(".pp-badge--deal") else ""
    )
    specs = [
        clean_text(item.get_text())
        for item in soup.select(".pp-spec")
        if clean_text(item.get_text())
    ]

    remote_images = []
    for img in soup.select(".pp-gallery img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        remote_images.append(urljoin(CRM_HOST + "/", src))

    if not remote_images:
        raise ValueError("تصویری در صفحه ملک پیدا نشد")

    property_obj, _created = Property.objects.update_or_create(
        source_token=token,
        defaults={
            "source_url": source_url,
            "title": title,
            "price_text": price_text,
            "price_per_meter_text": price_per_meter,
            "property_type": property_type,
            "deal_type": deal_type,
            "specs": specs,
        },
    )

    property_obj.images.all().delete()
    for index, remote_url in enumerate(remote_images):
        image_file = download_image(remote_url)
        PropertyImage.objects.create(property=property_obj, image=image_file, order=index)

    return property_obj
