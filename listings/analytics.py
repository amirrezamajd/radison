import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

VISITOR_COOKIE = "rv_vid"
DIRECT = "مستقیم"
INTERNAL = "داخلی"

GOOGLE_ORGANIC = "گوگل · جستجو"
GOOGLE_ADS = "گوگل · تبلیغات"
GOOGLE_DISCOVER = "گوگل · دیسکاور"
GOOGLE_MAPS = "گوگل · نقشه"
GOOGLE_GENERIC = "گوگل"
GOOGLE_PREFIX = "گوگل"

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
    ("fb.com", "فیسبوک"),
    ("twitter.", "ایکس"),
    ("x.com", "ایکس"),
    ("linkedin.", "لینکدین"),
    ("eitaa.", "ایتا"),
    ("rubika.", "روبیکا"),
)

UTM_SOURCE_LABELS = {
    "instagram": "اینستاگرام",
    "ig": "اینستاگرام",
    "telegram": "تلگرام",
    "tg": "تلگرام",
    "whatsapp": "واتساپ",
    "wa": "واتساپ",
    "divar": "دیوار",
    "sheypoor": "شیپور",
    "bing": "بینگ",
    "yandex": "یاندکس",
    "facebook": "فیسبوک",
    "fb": "فیسبوک",
    "twitter": "ایکس",
    "x": "ایکس",
    "linkedin": "لینکدین",
    "eitaa": "ایتا",
    "rubika": "روبیکا",
}

PAID_MEDIUMS = {"cpc", "ppc", "paid", "paidsearch", "display", "banner", "cpm", "ads", "ad"}
GOOGLE_ADS_KEYS = ("gclid", "gbraid", "wbraid")
GOOGLE_HOST_NEEDLES = (
    "google.",
    "googleusercontent.",
    "googleadservices.",
    "googlesyndication.",
    "doubleclick.",
    "ggpht.",
    "g.page",
    "goo.gl",
    "g.co",
)


def _first(params, *keys) -> str:
    for key in keys:
        values = params.get(key)
        if isinstance(values, list):
            value = values[0] if values else ""
        else:
            value = values or ""
        value = str(value).strip()
        if value:
            return value
    return ""


def _parse_query(query: str) -> dict:
    if not query:
        return {}
    return parse_qs(query.lstrip("?"), keep_blank_values=False)


def is_google_host(host: str) -> bool:
    host = (host or "").lower()
    if not host:
        return False
    if any(needle in host for needle in GOOGLE_HOST_NEEDLES):
        return True
    # Android Google app referrers: com.google.android.googlequicksearchbox
    return host.startswith("com.google.")


def classify_google(host: str, params: dict) -> str | None:
    if any(_first(params, key) for key in GOOGLE_ADS_KEYS):
        return GOOGLE_ADS

    utm_source = _first(params, "utm_source").lower()
    utm_medium = _first(params, "utm_medium").lower()
    utm_campaign = _first(params, "utm_campaign").lower()

    googleish_source = (
        "google" in utm_source
        or utm_source in {"adwords", "googleads", "google_ads", "googleadsense"}
    )
    if googleish_source:
        if utm_medium in PAID_MEDIUMS or any(_first(params, key) for key in GOOGLE_ADS_KEYS):
            return GOOGLE_ADS
        if "discover" in utm_medium or "discover" in utm_campaign:
            return GOOGLE_DISCOVER
        if "map" in utm_medium or "map" in utm_campaign:
            return GOOGLE_MAPS
        return GOOGLE_ORGANIC

    host = (host or "").lower()
    if not is_google_host(host):
        return None

    if any(
        part in host
        for part in (
            "googleadservices.",
            "googlesyndication.",
            "doubleclick.",
            "adservice.google.",
        )
    ):
        return GOOGLE_ADS
    if "maps.google." in host or host.startswith("maps.google"):
        return GOOGLE_MAPS
    if "discover" in host:
        return GOOGLE_DISCOVER
    if "news.google." in host:
        return GOOGLE_ORGANIC
    return GOOGLE_ORGANIC


def classify_from_parts(referrer: str, query: str, own_host: str) -> tuple[str, str]:
    params = _parse_query(query)
    parsed = urlparse(referrer) if referrer else None
    host = ((parsed.hostname or parsed.netloc) if parsed else "") or ""
    host = host.lower()

    google = classify_google(host, params)
    if google:
        return google, host

    utm = _first(params, "utm_source")
    if utm:
        lowered = utm.lower()
        if lowered in UTM_SOURCE_LABELS:
            return UTM_SOURCE_LABELS[lowered], host
        for needle, label in KNOWN_SOURCES:
            if needle.strip(".") in lowered:
                return label, host
        return utm[:60], host

    if not host:
        return DIRECT, ""

    own = (own_host or "").split(":")[0].lower()
    if host == own or host.removeprefix("www.") == own.removeprefix("www."):
        return INTERNAL, host

    for needle, label in KNOWN_SOURCES:
        if needle in host:
            return label, host
    return host.removeprefix("www.")[:120], host


def classify_source(request) -> tuple[str, str]:
    referrer = request.META.get("HTTP_REFERER", "")
    query = request.META.get("QUERY_STRING", "") or request.GET.urlencode()
    return classify_from_parts(referrer, query, request.get_host() or "")


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


def refine_page_visit_source(request, referrer: str, query: str) -> bool:
    """Upgrade a just-recorded Direct hit when the browser still knows the real referrer."""
    from .models import PageVisit

    if is_bot(request) or is_staff(request):
        return False

    vid = request.COOKIES.get(VISITOR_COOKIE, "")
    if not re.fullmatch(r"[0-9a-f]{32}", vid):
        return False

    source, host = classify_from_parts(referrer, query, request.get_host() or "")
    if source in {DIRECT, INTERNAL}:
        return False

    cutoff = timezone.now() - timedelta(minutes=3)
    visit = (
        PageVisit.objects.filter(visitor_id=vid, created_at__gte=cutoff, source=DIRECT)
        .order_by("-created_at", "-id")
        .first()
    )
    if not visit:
        return False

    visit.source = source[:120]
    visit.referrer_host = (host or visit.referrer_host)[:255]
    visit.save(update_fields=["source", "referrer_host"])
    return True


def record_property_event(request, property_obj, kind) -> bool:
    from .models import PropertyEvent

    if is_bot(request) or is_staff(request):
        return False
    PropertyEvent.objects.create(property=property_obj, kind=kind)
    return True


def prune_analytics() -> None:
    from django.db.utils import OperationalError

    from .models import PageVisit, PropertyEvent

    cutoff = timezone.now() - timedelta(days=settings.ANALYTICS_RETENTION_DAYS)
    try:
        PageVisit.objects.filter(created_at__lt=cutoff).delete()
        PropertyEvent.objects.filter(created_at__lt=cutoff).delete()
    except OperationalError:
        logger.info("Analytics tables not ready; prune skipped")
