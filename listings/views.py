from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import AdminJoinRequest, Property
from .scrape import import_property_from_url

User = get_user_model()


def home(request):
    properties = Property.objects.prefetch_related("images").all()
    payload = []
    for item in properties:
        payload.append(
            {
                "id": item.id,
                "title": item.title,
                "price_text": item.price_text,
                "price_per_meter_text": item.price_per_meter_text,
                "property_type": item.property_type,
                "deal_type": item.deal_type,
                "specs": item.specs,
                "images": [image.image.url for image in item.images.all()],
            }
        )
    return render(
        request,
        "listings/home.html",
        {
            "properties": properties,
            "properties_json": payload,
        },
    )


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
def panel(request):
    if not request.user.is_staff:
        logout(request)
        return redirect("panel_login")

    properties = Property.objects.prefetch_related("images").all()
    return render(request, "listings/panel.html", {"properties": properties})


@login_required(login_url="panel_login")
@require_POST
def panel_extract(request):
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "دسترسی غیرمجاز"}, status=403)

    url = (request.POST.get("url") or "").strip()
    if not url:
        return JsonResponse({"ok": False, "error": "لینک ملک را وارد کنید"}, status=400)

    try:
        property_obj = import_property_from_url(url)
    except Exception as exc:  # noqa: BLE001 - surface scrape errors to UI
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "property": {
                "id": property_obj.id,
                "title": property_obj.title,
                "price_text": property_obj.price_text,
                "images_count": property_obj.images.count(),
                "cover": property_obj.cover_image,
            },
        }
    )


@login_required(login_url="panel_login")
@require_POST
def panel_delete(request, pk):
    if not request.user.is_staff:
        messages.error(request, "دسترسی غیرمجاز")
        return redirect("panel_login")

    property_obj = get_object_or_404(Property, pk=pk)
    title = property_obj.title
    property_obj.delete()
    messages.success(request, f"ملک «{title}» حذف شد.")
    return redirect("panel")


@require_POST
def panel_logout(request):
    logout(request)
    return redirect("panel_login")
