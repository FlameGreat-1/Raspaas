from django.shortcuts import redirect
from django.urls import reverse


class SessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded_paths = [
            "/admin/",
            "/accounts/login/",
            "/static/",
            "/media/",
            "/api/",
            "/favicon.ico",
            "/license/api/",
            "/license/required/",
            "/license/activate/",
            "/license/expired/",
        ]

        is_excluded = any(request.path.startswith(path) for path in excluded_paths)

        if (
            not is_excluded
            and hasattr(request, "user")
            and not request.user.is_authenticated
        ):
            next_url = request.path
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next={next_url}")

        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(view_func, "login_exempt", False):
            return None
        return None
