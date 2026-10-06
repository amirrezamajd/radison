class NoStoreDynamicMiddleware:
    """
    Prevent browsers/CDNs from caching HTML and admin responses so
    site panel, Django admin, and public listings always stay in sync.
    """

    CACHEABLE_PREFIXES = ("/static/", "/media/", "/tours/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or "/"
        if path.startswith(self.CACHEABLE_PREFIXES):
            return response

        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["Vary"] = "Cookie"
        return response
