from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.static import serve

from .models import AdminJoinRequest, Property, VirtualTour
from .scrape import import_property_from_url
from .tours import TourUploadError, delete_tour_files, extract_tour_zip

User = get_user_model()


@never_cache
def home(request):
    properties = Property.objects.prefetch_related("images").select_related("virtual_tour").all()
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
                "virtual_tour_url": item.virtual_tour_url,
                "virtual_tour_name": item.virtual_tour.name if item.virtual_tour_id else "",
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

    properties = Property.objects.prefetch_related("images").select_related("virtual_tour").all()
    tours = VirtualTour.objects.all()
    return render(
        request,
        "listings/panel.html",
        {
            "properties": properties,
            "tours": tours,
            "property_count": properties.count(),
            "tour_count": tours.count(),
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

    try:
        property_obj = import_property_from_url(url)
        if selected_tour is not None:
            property_obj.virtual_tour = selected_tour
            property_obj.save(update_fields=["virtual_tour", "updated_at"])
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
                "virtual_tour_url": property_obj.virtual_tour_url,
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
    return redirect("panel")


def virtual_tour_index(request, slug):
    return virtual_tour_file(request, slug, path="index.html")


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
        if image.image:
            image.image.delete(save=False)
    property_obj.delete()
    messages.success(request, f"ملک «{title}» حذف شد.")
    return redirect("panel")


@require_POST
def panel_logout(request):
    logout(request)
    return redirect("panel_login")
