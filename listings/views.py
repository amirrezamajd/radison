from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Property
from .scrape import import_property_from_url


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
    if request.user.is_authenticated:
        return redirect("panel")

    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect("panel")
        error = "نام کاربری یا رمز عبور اشتباه است"

    return render(request, "listings/login.html", {"error": error})


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
