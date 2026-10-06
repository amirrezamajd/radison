import tempfile
import zipfile
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .analytics import INTERNAL
from .backup import create_backup, list_backups, sqlite_path
from .jalali import fa_digits, full_label, short_label
from .models import PageVisit, Property, PropertyEvent

DEVICE_LABELS = {"mobile": "موبایل", "desktop": "دسکتاپ", "tablet": "تبلت"}


def staff_required(view):
    @login_required(login_url="panel_login")
    @never_cache
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            logout(request)
            return redirect("panel_login")
        return view(request, *args, **kwargs)

    return wrapper


def _panel_return(request, fallback="panel_properties"):
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/panel/"):
        return redirect(next_url)
    return redirect(fallback)


def _share_rows(rows, total):
    for row in rows:
        row["percent"] = round(row["count"] * 100 / total) if total else 0
    return rows


@staff_required
def panel_stats(request):
    now = timezone.localtime()
    today = now.date()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since_7 = start_today - timedelta(days=6)
    since_14 = start_today - timedelta(days=13)
    since_30 = start_today - timedelta(days=29)

    visits = PageVisit.objects.all()
    events = PropertyEvent.objects.all()

    def visit_numbers(since):
        qs = visits.filter(created_at__gte=since)
        return qs.count(), qs.values("visitor_id").distinct().count()

    today_visits, today_visitors = visit_numbers(start_today)
    week_visits, week_visitors = visit_numbers(since_7)
    week_views = events.filter(kind=PropertyEvent.Kind.VIEW, created_at__gte=since_7).count()
    week_whatsapp = events.filter(kind=PropertyEvent.Kind.WHATSAPP, created_at__gte=since_7).count()

    daily_visits = {
        row["day"]: row
        for row in visits.filter(created_at__gte=since_14)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"), visitors=Count("visitor_id", distinct=True))
    }
    daily_events = {}
    for row in (
        events.filter(created_at__gte=since_14)
        .annotate(day=TruncDate("created_at"))
        .values("day", "kind")
        .annotate(count=Count("id"))
    ):
        daily_events.setdefault(row["day"], {})[row["kind"]] = row["count"]

    days = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        visit_row = daily_visits.get(day, {})
        event_row = daily_events.get(day, {})
        days.append(
            {
                "label": short_label(day),
                "full_label": full_label(day),
                "visits": visit_row.get("count", 0),
                "visitors": visit_row.get("visitors", 0),
                "views": event_row.get(PropertyEvent.Kind.VIEW, 0),
                "whatsapp": event_row.get(PropertyEvent.Kind.WHATSAPP, 0),
            }
        )
    peak = max([1] + [max(d["visits"], d["views"], d["whatsapp"]) for d in days])
    for day in days:
        day["visits_h"] = round(day["visits"] * 100 / peak)
        day["views_h"] = round(day["views"] * 100 / peak)
        day["whatsapp_h"] = round(day["whatsapp"] * 100 / peak)

    month_visits = visits.filter(created_at__gte=since_30)
    entry_visits = month_visits.exclude(source=INTERNAL)
    entry_total = entry_visits.count()
    sources = _share_rows(
        list(entry_visits.values("source").annotate(count=Count("id")).order_by("-count")[:12]),
        entry_total,
    )

    device_total = month_visits.values("visitor_id").distinct().count()
    devices = _share_rows(
        [
            {"label": DEVICE_LABELS.get(row["device"], row["device"] or "نامشخص"), "count": row["count"]}
            for row in month_visits.values("device").annotate(count=Count("visitor_id", distinct=True)).order_by("-count")
        ],
        device_total,
    )

    top_pages = list(month_visits.values("path").annotate(count=Count("id")).order_by("-count")[:8])

    top_properties = list(
        Property.objects.annotate(
            views_7=Count("events", filter=Q(events__kind=PropertyEvent.Kind.VIEW, events__created_at__gte=since_7)),
            whatsapp_7=Count(
                "events", filter=Q(events__kind=PropertyEvent.Kind.WHATSAPP, events__created_at__gte=since_7)
            ),
            whatsapp_all=Count("events", filter=Q(events__kind=PropertyEvent.Kind.WHATSAPP)),
        ).order_by("-views_7", "-view_count")[:10]
    )
    general_whatsapp = events.filter(
        kind=PropertyEvent.Kind.WHATSAPP, property__isnull=True, created_at__gte=since_7
    ).count()

    return render(
        request,
        "listings/panel_stats.html",
        {
            "today_label": full_label(today),
            "kpis": [
                {"label": "بازدید امروز", "value": fa_digits(today_visits), "hint": f"{fa_digits(today_visitors)} بازدیدکننده"},
                {"label": "بازدید ۷ روز", "value": fa_digits(week_visits), "hint": f"{fa_digits(week_visitors)} بازدیدکننده یکتا"},
                {"label": "باز شدن ملک‌ها (۷ روز)", "value": fa_digits(week_views), "hint": "پاپ‌آپ یا صفحه ملک"},
                {
                    "label": "کلیک واتساپ (۷ روز)",
                    "value": fa_digits(week_whatsapp),
                    "hint": f"{fa_digits(round(week_whatsapp * 100 / week_views) if week_views else 0)}٪ از بازدید ملک‌ها",
                },
            ],
            "days": days,
            "sources": sources,
            "entry_total": entry_total,
            "devices": devices,
            "top_pages": top_pages,
            "top_properties": top_properties,
            "general_whatsapp": general_whatsapp,
            "ga_enabled": bool(settings.GA_MEASUREMENT_ID),
        },
    )


@staff_required
@require_POST
def panel_pin(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)
    action = request.POST.get("action", "")

    with transaction.atomic():
        pinned = list(Property.objects.filter(pin_order__isnull=False).order_by("pin_order", "id"))
        if action == "pin" and property_obj not in pinned:
            pinned.append(property_obj)
            messages.success(request, f"«{property_obj.title}» به ابتدای صفحه اصلی اضافه شد.")
        elif action == "unpin" and property_obj in pinned:
            pinned.remove(property_obj)
            Property.objects.filter(pk=property_obj.pk).update(pin_order=None)
            messages.success(request, f"«{property_obj.title}» از ابتدای صفحه اصلی برداشته شد.")
        elif action in ("up", "down") and property_obj in pinned:
            index = pinned.index(property_obj)
            target = index - 1 if action == "up" else index + 1
            if 0 <= target < len(pinned):
                pinned[index], pinned[target] = pinned[target], pinned[index]

        for position, item in enumerate(pinned, start=1):
            Property.objects.filter(pk=item.pk).update(pin_order=position)

    return _panel_return(request)


def _backup_rows():
    rows = []
    for path in list_backups():
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone())
        rows.append(
            {
                "name": path.name,
                "size": f"{stat.st_size / 1024:.0f} KB" if stat.st_size < 1024 * 1024 else f"{stat.st_size / 1024 / 1024:.1f} MB",
                "date": f"{full_label(modified.date())} · {fa_digits(modified.strftime('%H:%M'))}",
                "kind": "خودکار" if "-auto" in path.name else "قبل از دیپلوی" if "-predeploy" in path.name else "دستی",
            }
        )
    return rows


@staff_required
def panel_backups(request):
    db_path = sqlite_path()
    media_root = Path(settings.MEDIA_ROOT)
    media_files = [p for p in media_root.rglob("*") if p.is_file()] if media_root.is_dir() else []
    media_size = sum(p.stat().st_size for p in media_files)
    return render(
        request,
        "listings/panel_backups.html",
        {
            "backups": _backup_rows(),
            "backup_dir": settings.BACKUP_DIR,
            "interval": fa_digits(int(settings.BACKUP_INTERVAL_HOURS)),
            "keep": fa_digits(settings.BACKUP_KEEP),
            "db_path": db_path,
            "db_size": f"{db_path.stat().st_size / 1024 / 1024:.1f} MB" if db_path and db_path.exists() else "—",
            "media_count": fa_digits(len(media_files)),
            "media_size": f"{media_size / 1024 / 1024:.1f} MB",
            "property_count": fa_digits(Property.objects.count()),
        },
    )


@staff_required
@require_POST
def panel_backup_create(request):
    target = create_backup("manual")
    if target:
        messages.success(request, f"بکاپ «{target.name}» ساخته شد.")
    else:
        messages.error(request, "دیتابیس SQLite پیدا نشد؛ بکاپ ساخته نشد.")
    return redirect("panel_backups")


@staff_required
def panel_backup_download(request, name):
    for path in list_backups():
        if path.name == name:
            return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)
    raise Http404("Backup not found")


@staff_required
def panel_media_download(request):
    media_root = Path(settings.MEDIA_ROOT)
    if not media_root.is_dir():
        raise Http404("Media folder not found")

    fresh = create_backup("manual")
    archive = tempfile.TemporaryFile()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
        if fresh:
            bundle.write(fresh, arcname="database/db.sqlite3")
        for path in media_root.rglob("*"):
            if path.is_file():
                bundle.write(path, arcname=f"media/{path.relative_to(media_root).as_posix()}")
    archive.seek(0)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    return FileResponse(archive, as_attachment=True, filename=f"radison-full-backup-{stamp}.zip")

