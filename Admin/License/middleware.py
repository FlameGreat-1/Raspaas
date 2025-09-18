from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from .utils import validate_license, get_hardware_fingerprint
from .models import License


class LicenseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        try:
            license_obj = License.objects.filter(is_active=True).first()

            if not license_obj:
                if request.user.is_authenticated:
                    logout(request)

                if not self._is_license_path(request.path):
                    return redirect(reverse("license:license_required"))
            else:
                if license_obj.remotely_revoked:
                    if request.user.is_authenticated:
                        logout(request)
                        messages.error(
                            request,
                            f"Your license has been revoked: {license_obj.revocation_reason or 'Contact support for details.'}",
                        )
                    return redirect(reverse("license:license_required"))

                if license_obj.was_revoked and not self._is_license_path(request.path):
                    if request.user.is_authenticated:
                        logout(request)
                        messages.error(
                            request,
                            "Your license requires reactivation. Please enter your license key again.",
                        )
                    return redirect(reverse("license:license_activation"))

                if not license_obj.is_active:
                    if request.user.is_authenticated:
                        logout(request)
                        messages.error(
                            request, "Your license is inactive. Please contact support."
                        )
                    return redirect(reverse("license:license_required"))

                if license_obj.is_expired():
                    if request.user.is_authenticated:
                        logout(request)
                        messages.error(
                            request,
                            "Your license has expired. Please renew your subscription.",
                        )
                    return redirect(reverse("license:license_expired"))

                if request.user.is_authenticated:
                    days_left = license_obj.days_until_expiration()
                    if days_left <= 7:
                        messages.warning(
                            request,
                            f"Your license will expire in {days_left} days. Please renew your subscription.",
                        )

                    redirect_response = self._update_online_check(license_obj, request)
                    if redirect_response:
                        return redirect_response

        except Exception as e:
            if settings.DEBUG and request.user.is_authenticated:
                messages.error(request, f"License check error: {str(e)}")
            if request.user.is_authenticated:
                logout(request)
            if not self._is_license_path(request.path):
                return redirect(reverse("license:license_required"))

        response = self.get_response(request)
        return response

    def _is_exempt(self, path):
        exempt_paths = settings.LICENSE_EXEMPT_URLS

        for exempt_path in exempt_paths:
            if path.startswith(exempt_path):
                return True

        return False

    def _is_license_path(self, path):
        license_paths = [
            url for url in settings.LICENSE_EXEMPT_URLS if url.startswith("/license/")
        ]

        for license_path in license_paths:
            if path.startswith(license_path):
                return True

        return False

    def _update_online_check(self, license_obj, request):
        now = timezone.now()

        if license_obj.needs_online_verification():
            hardware_fingerprint = get_hardware_fingerprint()
            online_valid, message = license_obj.verify_online()

            if not online_valid:
                if "offline grace period" not in message:
                    messages.warning(request, f"License verification: {message}")
                    if (
                        "revoked" in message.lower()
                        or "expired" in message.lower()
                        or "verification error" in message.lower()
                    ):
                        logout(request)
                        return redirect(reverse("license:license_required"))
        return None
