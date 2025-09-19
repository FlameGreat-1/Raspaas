from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
import logging
from .utils import validate_license, get_hardware_fingerprint
from .models import License, LicenseAttempt

logger = logging.getLogger("license_security")


class LicenseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

        try:
            license_obj = License.objects.filter(is_active=True).first()

            if not license_obj:
                if request.user.is_authenticated:
                    logout(request)
                    logger.warning(
                        f"No active license found, logging out user from IP {ip_address}"
                    )

                if not self._is_license_path(request.path):
                    return redirect(reverse("license:license_required"))
            else:
                if not license_obj.verify_integrity():
                    logger.critical(
                        f"License integrity check failed for IP {ip_address}"
                    )
                    if request.user.is_authenticated:
                        logout(request)
                        messages.error(
                            request, "License validation error. Please contact support."
                        )
                    return redirect(reverse("license:license_required"))

                if license_obj.remotely_revoked:
                    if request.user.is_authenticated:
                        logout(request)
                        logger.warning(
                            f"Revoked license access attempt from IP {ip_address}"
                        )
                        messages.error(
                            request,
                            f"Your license has been revoked: {license_obj.revocation_reason or 'Contact support for details.'}",
                        )
                    return redirect(reverse("license:license_required"))

                if license_obj.was_revoked and not self._is_license_path(request.path):
                    if request.user.is_authenticated:
                        logout(request)
                        logger.warning(
                            f"Previously revoked license access attempt from IP {ip_address}"
                        )
                        messages.error(
                            request,
                            "Your license requires reactivation. Please enter your license key again.",
                        )
                    return redirect(reverse("license:license_activation"))

                if not license_obj.is_active:
                    if request.user.is_authenticated:
                        logout(request)
                        logger.warning(
                            f"Inactive license access attempt from IP {ip_address}"
                        )
                        messages.error(
                            request, "Your license is inactive. Please contact support."
                        )
                    return redirect(reverse("license:license_required"))

                if license_obj.is_expired():
                    if request.user.is_authenticated:
                        logout(request)
                        logger.warning(
                            f"Expired license access attempt from IP {ip_address}"
                        )
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
            logger.error(f"License middleware error: {str(e)} for IP {ip_address}")
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
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

        if license_obj.needs_online_verification():
            hardware_fingerprint = get_hardware_fingerprint()

            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=True,
                license_key=license_obj.license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )

            online_valid, message = license_obj.verify_online()

            if not online_valid:
                if "offline grace period" not in message:
                    logger.warning(
                        f"License verification failed: {message} for IP {ip_address}"
                    )
                    messages.warning(request, f"License verification: {message}")
                    if (
                        "revoked" in message.lower()
                        or "expired" in message.lower()
                        or "verification error" in message.lower()
                        or "integrity check failed" in message.lower()
                    ):
                        logout(request)
                        return redirect(reverse("license:license_required"))
        return None
