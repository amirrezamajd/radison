from django.conf import settings


def site_contact(request):
    return {
        "WHATSAPP_NUMBER": settings.RADISON_WHATSAPP,
        "SITE_PHONE": settings.RADISON_PHONE,
        "SITE_INSTAGRAM": settings.RADISON_INSTAGRAM,
    }
