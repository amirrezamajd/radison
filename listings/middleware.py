from .analytics import record_page_visit, should_track_page
from .backup import maybe_backup_async


class SiteAnalyticsMiddleware:
    """Record public page visits and trigger the periodic database backup."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if should_track_page(request, response):
            record_page_visit(request, response)
        maybe_backup_async()
        return response
