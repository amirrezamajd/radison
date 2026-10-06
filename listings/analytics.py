import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

VISITOR_COOKIE = "rv_vid"
DIRECT = "مستقیم"
INTERNAL = "داخلی"

EXCLUDED_PREFIXES = (
    "/panel",
    "/django-admin",
    "/static/",
    "/media/",
    "/api/",
    "/tours/",
    "/favicon",
    "/sitemap",
    "/robots",
)

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|preview|curl|wget|python-requests|headless|lighthouse",
    re.IGNORECASE,
)

KNOWN_SOURCES = (
    ("google.", "گوگل"),
    ("bing.", "بینگ"),
    ("yandex.", "یاندکس"),
    ("duckduckgo.", "داک‌داک‌گو"),
    ("instagram.", "اینستاگرام"),
    ("t.me", "تلگرام"),
    ("telegram.", "تلگرام"),
    ("whatsapp.", "واتساپ"),
    ("wa.me", "واتساپ"),
    ("divar.", "دیوار"),
    ("sheypoor.", "شیپور"),
    ("facebook.", "فیسبوک"),
    ("twitter.", "ایکس"),
    ("x.com", "ایکس"),
    ("linkedin.", "لینکدین"),
    ("eitaa.", "ایتا"),
    ("rubika.", "روبیکا"),
)


def classify_source(request) -> tuple[str, str]:
    utm = (request.GET.get("utm_source") or "").strip()[:60]
    referrer = request.META.get("HTTP_REFERER", "")
    host = (urlparse(referrer).hostname or "").lower() if referrer else ""

    if utm:
        lowered = utm.lower()
        for needle, label in KNOWN_SOURCES:
            if needle.strip(".") in lowered:
                return label, host
        return utm, host
    if not host:
        return DIRECT, ""
    own_host = (request.get_host() or "").split(":")[0].lower()
    if host == own_host or host.removeprefix("www.") == own_host.removeprefix("www."):
        return INTERNAL, host
    for needle, label in KNOWN_SOURCES:
        if needle in host:
            return label, host
    return host.removeprefix("www.")[:120], host


def classify_device(user_agent: str) -> str:
    if re.search(r"iPad|Tablet", user_agent, re.IGNORECASE):
        return "tablet"
    if re.search(r"Mobi|Android|iPhone", user_agent, re.IGNORECASE):
        return "mobile"
    return "desktop"


def is_bot(request) -> bool:
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    return not user_agent or bool(BOT_RE.search(user_agent))


def is_staff(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


def should_track_page(request, response) -> bool:
    if request.method != "GET" or response.status_code != 200:
        return False
    if request.path.startswith(EXCLUDED_PREFIXES):
        return False
    if "text/html" not in response.get("Content-Type", ""):
        return False
    return not is_bot(request) and not is_staff(request)


def visitor_id(request) -> tuple[str, bool]:
    existing = request.COOKIES.get(VISITOR_COOKIE, "")
    if re.fullmatch(r"[0-9a-f]{32}", existing):
        return existing, False
    return uuid.uuid4().hex, True


def record_page_visit(request, response) -> None:
    from .models import PageVisit

    vid, is_new = visitor_id(request)
    source, host = classify_source(request)
    try:
        PageVisit.objects.create(
            path=request.path[:255],
            source=source,
            referrer_host=host[:255],
            device=classify_device(request.META.get("HTTP_USER_AGENT", "")),
            visitor_id=vid,
        )
    except Exception:  # noqa: BLE001 - analytics must never break pages
        logger.exception("Could not record page visit")
        return
    if is_new:
        response.set_cookie(
            VISITOR_COOKIE,
            vid,
            max_age=365 * 24 * 3600,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )


def record_property_event(request, property_obj, kind) -> bool:
    from .models import PropertyEvent

    if is_bot(request) or is_staff(request):
        return False
    PropertyEvent.objects.create(property=property_obj, kind=kind)
    return True


def prune_analytics() -> None:
    from .models import PageVisit, PropertyEvent

    cutoff = timezone.now() - timedelta(days=settings.ANALYTICS_RETENTION_DAYS)
    PageVisit.objects.filter(created_at__lt=cutoff).delete()
    PropertyEvent.objects.filter(created_at__lt=cutoff).delete()
