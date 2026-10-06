import json

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.static import serve

from .analytics import record_property_event
from .models import AdminJoinRequest, Property, PropertyEvent, VirtualTour
from .parsing import normalize_digits, normalize_persian
from .scrape import import_property_from_url
from .tours import TourUploadError, delete_tour_files, extract_tour_zip

User = get_user_model()


BILLION = 1_000_000_000

PRICE_MIN_OPTIONS = [(1, "۱ میلیارد"), (3, "۳ میلیارد"), (5, "۵ میلیارد"), (10, "۱۰ میلیارد"), (20, "۲۰ میلیارد")]
PRICE_MAX_OPTIONS = [(3, "۳ میلیارد"), (5, "۵ میلیارد"), (10, "۱۰ میلیارد"), (20, "۲۰ میلیارد"), (50, "۵۰ میلیارد")]
AREA_OPTIONS = [(100, "۱۰۰ متر"), (150, "۱۵۰ متر"), (200, "۲۰۰ متر"), (300, "۳۰۰ متر"), (500, "۵۰۰ متر")]
BEDROOM_OPTIONS = [(1, "۱ خواب"), (2, "۲ خواب"), (3, "۳ خواب"), (4, "۴ خواب و بیشتر")]
PINNED_FIRST = [F("pin_order").asc(nulls_last=True), "-created_at"]

SORT_OPTIONS = [
    ("featured", "پیشنهادی"),
    ("new", "جدیدترین"),
    ("price_asc", "ارزان‌ترین"),
    ("price_desc", "گران‌ترین"),
    ("area_desc", "بیشترین متراژ"),
    ("popular", "پربازدیدترین"),
]
SORT_ORDERING = {
    "featured": PINNED_FIRST,
    "new": ["-created_at"],
    "price_asc": [F("price_value").asc(nulls_last=True), "-created_at"],
    "price_desc": [F("price_value").desc(nulls_last=True), "-created_at"],
    "area_desc": [F("area_value").desc(nulls_last=True), "-created_at"],
    "popular": ["-view_count", "-created_at"],
}


def _public_queryset():
    return Property.objects.prefetch_related("images").select_related("virtual_tour")


def _properties_payload(request, properties):
    payload = []
    for item in properties:
        page_url = request.build_absolute_uri(item.get_absolute_url())
        payload.append(
            {
                "id": item.id,
                "code": item.code,
                "title": item.title,
                "price_text": item.price_text,
                "price_per_meter_text": item.price_per_meter_text,
                "property_type": item.property_type,
                "deal_type": item.deal_type,
                "specs": item.specs,
                "images": [image.image.url for image in item.images.all()],
                "virtual_tour_url": item.virtual_tour_url,
                "virtual_tour_name": item.virtual_tour.name if item.virtual_tour_id else "",
                "view_count": item.view_count,
                "url": item.get_absolute_url(),
                "whatsapp_url": item.whatsapp_url(page_url),
            }
        )
    return payload


def _distinct_values(field):
    values = Property.objects.exclude(**{field: ""}).order_by().values_list(field, flat=True)
    return sorted(set(values))


def _int_param(request, name):
    raw = normalize_digits(request.GET.get(name, "")).strip()
    return int(raw) if raw.isdigit() else None


def _filter_properties(request):
    filters = {
        "q": normalize_persian(request.GET.get("q", ""))[:80],
        "deal": request.GET.get("deal", "").strip(),
        "type": request.GET.get("type", "").strip(),
        "price_min": _int_param(request, "price_min"),
        "price_max": _int_param(request, "price_max"),
        "area_min": _int_param(request, "area_min"),
        "beds_min": _int_param(request, "beds_min"),
        "sort": request.GET.get("sort", "featured"),
    }
    if filters["sort"] not in SORT_ORDERING:
        filters["sort"] = "featured"

    qs = _public_queryset()
    q = filters["q"]
    if q:
        code = q.lstrip("#").removeprefix("کد").strip()
        text_match = Q(title__icontains=q) | Q(property_type__icontains=q) | Q(deal_type__icontains=q)
        qs = qs.filter(text_match | Q(pk=int(code))) if code.isdigit() else qs.filter(text_match)
    if filters["deal"]:
        qs = qs.filter(deal_type=filters["deal"])
    if filters["type"]:
        qs = qs.filter(property_type=filters["type"])
    if filters["price_min"]:
        qs = qs.filter(price_value__gte=filters["price_min"] * BILLION)
    if filters["price_max"]:
        qs = qs.filter(price_value__lte=filters["price_max"] * BILLION)
    if filters["area_min"]:
        qs = qs.filter(area_value__gte=filters["area_min"])
    if filters["beds_min"]:
        qs = qs.filter(bedrooms__gte=filters["beds_min"])

    active = any(filters[key] for key in ("q", "deal", "type", "price_min", "price_max", "area_min", "beds_min"))
    return qs.order_by(*SORT_ORDERING[filters["sort"]]), filters, active


def _filter_options():
    return {
        "deal_options": _distinct_values("deal_type"),
        "type_options": _distinct_values("property_type"),
        "price_min_options": PRICE_MIN_OPTIONS,
        "price_max_options": PRICE_MAX_OPTIONS,
        "area_options": AREA_OPTIONS,
        "bedroom_options": BEDROOM_OPTIONS,
        "sort_options": SORT_OPTIONS,
    }


@never_cache
@ensure_csrf_cookie
def home(request):
    properties = list(_public_queryset().order_by(*PINNED_FIRST))
    return render(
        request,
        "listings/home.html",
        {
            "properties": properties,
            "properties_json": _properties_payload(request, properties),
            **_filter_options(),
        },
    )


@never_cache
@ensure_csrf_cookie
def properties(request):
    properties_qs, filters, filters_active = _filter_properties(request)
    properties_list = list(properties_qs)
    return render(
        request,
        "listings/properties.html",
        {
            "properties": properties_list,
            "properties_json": _properties_payload(request, properties_list),
            "filters": filters,
            "filters_active": filters_active,
            "total_count": Property.objects.count(),
            **_filter_options(),
        },
    )


@never_cache
@ensure_csrf_cookie
def property_detail(request, pk):
    listing = get_object_or_404(_public_queryset(), pk=pk)
    page_url = request.build_absolute_uri(listing.get_absolute_url())
    images = [request.build_absolute_uri(image.image.url) for image in listing.images.all()]

    similar = _public_queryset().exclude(pk=listing.pk)
    if listing.property_type:
        similar = similar.filter(property_type=listing.property_type)
    similar = list(similar.order_by("-created_at")[:8])

    description_parts = [listing.property_type, listing.deal_type, listing.price_text, *listing.specs[:4]]
    meta_description = f"{listing.title} در سرخرود · " + " · ".join(part for part in description_parts if part)

    structured_data = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": listing.title,
        "url": page_url,
        "description": meta_description,
        "datePosted": listing.created_at.date().isoformat(),
        "image": images[:6],
        "identifier": listing.code,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "IRR",
            "availability": "https://schema.org/InStock",
        },
    }
    if listing.price_value:
        structured_data["offers"]["price"] = listing.price_value * 10

    return render(
        request,
        "listings/property_detail.html",
        {
            "listing": listing,
            "page_url": page_url,
            "og_image": images[0] if images else "",
            "meta_description": meta_description[:300],
            "whatsapp_url": listing.whatsapp_url(page_url),
            "similar": similar,
            "properties_json": _properties_payload(request, [listing, *similar]),
            "structured_data": _ld_json(structured_data),
        },
    )


def _ld_json(data):
    encoded = json.dumps(data, ensure_ascii=False)
    return mark_safe(encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    lines = [
        "User-agent: *",
        "Disallow: /panel/",
        "Disallow: /django-admin/",
        "Disallow: /api/",
        "Allow: /",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@never_cache
def panel_login(request):
    if request.user.is_authenticated and request.user.is_staff and request.user.is_active:
        return redirect("panel")

    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.is_staff:
            login(request, user)
            return redirect("panel")

        existing = User.objects.filter(username=username).first()
        if existing and existing.check_password(password):
            join_request = getattr(existing, "admin_join_request", None)
            if join_request and join_request.status == AdminJoinRequest.Status.PENDING:
                error = "حساب شما ثبت شده و در انتظار تأیید ادمین اصلی است."
            elif join_request and join_request.status == AdminJoinRequest.Status.REJECTED:
                error = "درخواست عضویت شما رد شده است. با ادمین اصلی هماهنگ کنید."
            elif not existing.is_active or not existing.is_staff:
                error = "حساب شما هنوز فعال یا دارای دسترسی پنل نیست."
            else:
                error = "نام کاربری یا رمز عبور اشتباه است"
        else:
            error = "نام کاربری یا رمز عبور اشتباه است"

    return render(request, "listings/login.html", {"error": error})


@never_cache
def panel_register(request):
    if request.user.is_authenticated and request.user.is_staff and request.user.is_active:
        return redirect("panel")

    error = ""
    success = ""
    form_data = {
        "full_name": "",
        "username": "",
        "phone": "",
        "note": "",
    }

    if request.method == "POST":
        form_data = {
            "full_name": request.POST.get("full_name", "").strip(),
            "username": request.POST.get("username", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
            "note": request.POST.get("note", "").strip(),
        }
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        if not form_data["full_name"] or not form_data["username"] or not password1:
            error = "نام، نام کاربری و رمز عبور الزامی است."
        elif len(form_data["username"]) < 3:
            error = "نام کاربری باید حداقل ۳ کاراکتر باشد."
        elif len(password1) < 8:
            error = "رمز عبور باید حداقل ۸ کاراکتر باشد."
        elif password1 != password2:
            error = "تکرار رمز عبور با رمز واردشده یکسان نیست."
        elif User.objects.filter(username__iexact=form_data["username"]).exists():
            error = "این نام کاربری قبلاً ثبت شده است."
        else:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form_data["username"],
                    password=password1,
                    first_name=form_data["full_name"][:150],
                    is_active=False,
                    is_staff=False,
                )
                AdminJoinRequest.objects.create(
                    user=user,
                    full_name=form_data["full_name"],
                    phone=form_data["phone"],
                    note=form_data["note"],
                    status=AdminJoinRequest.Status.PENDING,
                )
            success = "ثبت‌نام انجام شد. پس از تأیید ادمین اصلی می‌توانید وارد پنل شوید."
            form_data = {"full_name": "", "username": "", "phone": "", "note": ""}

    return render(
        request,
        "listings/register.html",
        {
            "error": error,
            "success": success,
            "form": form_data,
        },
    )


@login_required(login_url="panel_login")
@never_cache
def panel(request):
    if not request.user.is_staff:
        logout(request)
        return redirect("panel_login")

    properties = list(
        Property.objects.prefetch_related("images").select_related("virtual_tour").all()
    )
    tours = list(VirtualTour.objects.all())
    return render(
        request,
        "listings/panel.html",
        {
            "properties": properties,
            "tours": tours,
            "property_count": len(properties),
            "tour_count": len(tours),
        },
    )


@login_required(login_url="panel_login")
@never_cache
def panel_properties(request):
    if not request.user.is_staff:
        logout(request)
        return redirect("panel_login")

    properties = list(
        Property.objects.prefetch_related("images").select_related("virtual_tour").all()
    )
    tours = list(VirtualTour.objects.all())
    payload = []
    for item in properties:
        payload.append(
            {
                "id": item.id,
                "title": item.title,
                "price_text": item.price_text,
                "source_url": item.source_url,
                "images_count": item.images.count(),
                "view_count": item.view_count,
                "cover": item.cover_image,
                "virtual_tour_id": item.virtual_tour_id or "",
                "pinned": item.is_pinned,
                "pin_url": reverse("panel_pin", args=[item.id]),
                "page_url": item.get_absolute_url(),
                "assign_url": f"/panel/assign-tour/{item.id}/",
                "reextract_url": f"/panel/reextract/{item.id}/",
                "delete_url": f"/panel/delete/{item.id}/",
                "django_url": f"/django-admin/listings/property/{item.id}/change/",
            }
        )
    return render(
        request,
        "listings/panel_properties.html",
        {
            "properties": properties,
            "pinned": sorted((p for p in properties if p.is_pinned), key=lambda p: (p.pin_order, p.id)),
            "tours": tours,
            "property_count": len(properties),
            "tour_count": len(tours),
            "properties_json": payload,
        },
    )


@login_required(login_url="panel_login")
@require_POST
def panel_extract(request):
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "دسترسی غیرمجاز"}, status=403)

    url = (request.POST.get("url") or "").strip()
    if not url:
        return JsonResponse({"ok": False, "error": "لینک ملک را وارد کنید"}, status=400)

    tour_id = (request.POST.get("virtual_tour_id") or "").strip()
    selected_tour = None
    if tour_id:
        selected_tour = VirtualTour.objects.filter(pk=tour_id).first()
        if selected_tour is None:
            return JsonResponse({"ok": False, "error": "بازدید مجازی انتخاب‌شده پیدا نشد"}, status=400)

    replace_id = (request.POST.get("replace_property_id") or "").strip()
    replace_property = None
    if replace_id:
        replace_property = Property.objects.filter(pk=replace_id).first()
        if replace_property is None:
            return JsonResponse({"ok": False, "error": "ملک برای ویرایش پیدا نشد"}, status=404)

    try:
        property_obj = import_property_from_url(url, replace_property=replace_property)
        if selected_tour is not None:
            property_obj.virtual_tour = selected_tour
            property_obj.save(update_fields=["virtual_tour", "updated_at"])
    except Exception as exc:  # noqa: BLE001 - surface scrape errors to UI
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "replaced": bool(replace_property),
            "property": {
                "id": property_obj.id,
                "title": property_obj.title,
                "price_text": property_obj.price_text,
                "images_count": property_obj.images.count(),
                "cover": property_obj.cover_image,
                "virtual_tour_url": property_obj.virtual_tour_url,
            },
        }
    )


@login_required(login_url="panel_login")
@require_POST
def panel_reextract(request, pk):
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "دسترسی غیرمجاز"}, status=403)

    property_obj = get_object_or_404(Property, pk=pk)
    url = (request.POST.get("url") or "").strip()
    if not url:
        return JsonResponse({"ok": False, "error": "لینک ملک CRM را وارد کنید"}, status=400)

    try:
        updated = import_property_from_url(url, replace_property=property_obj)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "replaced": True,
            "property": {
                "id": updated.id,
                "title": updated.title,
                "price_text": updated.price_text,
                "images_count": updated.images.count(),
                "cover": updated.cover_image,
            },
        }
    )


@login_required(login_url="panel_login")
@require_POST
def panel_tour_upload(request):
    if not request.user.is_staff:
        messages.error(request, "دسترسی غیرمجاز")
        return redirect("panel_login")

    name = (request.POST.get("name") or "").strip()
    uploaded = request.FILES.get("tour_zip")
    if not name:
        messages.error(request, "نام بازدید مجازی را وارد کنید.")
        return redirect("panel")
    if not uploaded:
        messages.error(request, "فایل ZIP بازدید مجازی را انتخاب کنید.")
        return redirect("panel")
    if not uploaded.name.lower().endswith(".zip"):
        messages.error(request, "فقط فایل ZIP پذیرفته می‌شود. پوشه daya را زیپ کنید.")
        return redirect("panel")

    slug = VirtualTour.make_unique_slug(name)
    try:
        storage_dir = extract_tour_zip(uploaded, slug)
    except TourUploadError as exc:
        messages.error(request, str(exc))
        return redirect("panel")

    tour = VirtualTour.objects.create(name=name, slug=slug, storage_dir=storage_dir)
    messages.success(
        request,
        f"بازدید مجازی «{tour.name}» آپلود شد. لینک: {tour.get_absolute_url()}",
    )
    return redirect("panel")


@login_required(login_url="panel_login")
@require_POST
def panel_tour_delete(request, pk):
    if not request.user.is_staff:
        messages.error(request, "دسترسی غیرمجاز")
        return redirect("panel_login")

    tour = get_object_or_404(VirtualTour, pk=pk)
    name = tour.name
    storage_dir = tour.storage_dir
    tour.delete()
    delete_tour_files(storage_dir)
    messages.success(request, f"بازدید مجازی «{name}» حذف شد.")
    return redirect("panel")


def _staff_required_redirect(request):
    logout(request)
    return redirect("panel_login")


def _panel_return(request):
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/panel/"):
        return redirect(next_url)
    referer = request.META.get("HTTP_REFERER") or ""
    if "/panel/properties" in referer:
        return redirect("panel_properties")
    return redirect("panel")


@login_required(login_url="panel_login")
@require_POST
def panel_assign_tour(request, pk):
    if not request.user.is_staff:
        messages.error(request, "دسترسی غیرمجاز")
        return redirect("panel_login")

    property_obj = get_object_or_404(Property, pk=pk)
    tour_id = (request.POST.get("virtual_tour_id") or "").strip()
    if tour_id:
        tour = get_object_or_404(VirtualTour, pk=tour_id)
        property_obj.virtual_tour = tour
    else:
        property_obj.virtual_tour = None
    property_obj.save(update_fields=["virtual_tour", "updated_at"])
    messages.success(request, f"بازدید مجازی ملک «{property_obj.title}» به‌روز شد.")
    return _panel_return(request)


def virtual_tour_index(request, slug):
    return virtual_tour_file(request, slug, path="index.html")


@require_POST
@never_cache
def track_property_view(request, pk):
    """Count a public property open. Staff views are ignored."""
    property_obj = get_object_or_404(Property, pk=pk)
    if request.user.is_authenticated and request.user.is_staff:
        return JsonResponse(
            {
                "ok": True,
                "counted": False,
                "view_count": property_obj.view_count,
            }
        )

    if not record_property_event(request, property_obj, PropertyEvent.Kind.VIEW):
        return JsonResponse({"ok": True, "counted": False, "view_count": property_obj.view_count})

    Property.objects.filter(pk=pk).update(view_count=F("view_count") + 1)
    property_obj.refresh_from_db(fields=["view_count"])
    return JsonResponse(
        {
            "ok": True,
            "counted": True,
            "view_count": property_obj.view_count,
        }
    )


@csrf_exempt
@require_POST
def track_whatsapp_click(request, pk=None):
    property_obj = get_object_or_404(Property, pk=pk) if pk else None
    counted = record_property_event(request, property_obj, PropertyEvent.Kind.WHATSAPP)
    return JsonResponse({"ok": True, "counted": counted})


def page_not_found(request, exception=None):
    suggestions = list(_public_queryset().order_by(*PINNED_FIRST)[:4])
    return render(request, "404.html", {"suggestions": suggestions}, status=404)


def virtual_tour_file(request, slug, path):
    tour = get_object_or_404(VirtualTour, slug=slug)
    root = tour.absolute_folder
    if not root.exists():
        return JsonResponse({"ok": False, "error": "فایل‌های بازدید پیدا نشد"}, status=404)
    # Prevent empty path
    safe_path = path or "index.html"
    return serve(request, safe_path, document_root=str(root))


@login_required(login_url="panel_login")
@require_POST
def panel_delete(request, pk):
    if not request.user.is_staff:
        messages.error(request, "دسترسی غیرمجاز")
        return redirect("panel_login")

    property_obj = get_object_or_404(Property, pk=pk)
    title = property_obj.title
    for image in property_obj.images.all():
        image.delete_files()
    property_obj.delete()
    messages.success(request, f"ملک «{title}» حذف شد.")
    return _panel_return(request)


@require_POST
def panel_logout(request):
    logout(request)
    return redirect("panel_login")
