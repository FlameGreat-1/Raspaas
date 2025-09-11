from functools import wraps
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from .utils import (
    check_license_validity,
    get_hardware_fingerprint,
    validate_license,
)
from .models import License, Company
from django.apps import apps


def license_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not check_license_validity(request):
            return HttpResponseRedirect(reverse("license:license_required"))

        try:

            license_obj = License.objects.filter(is_active=True).first()
            if license_obj and license_obj.was_revoked:
                messages.error(
                    request,
                    "Your license requires reactivation. Please enter your license key again.",
                )
                return HttpResponseRedirect(reverse("license:license_activation"))
        except:
            pass

        return view_func(request, *args, **kwargs)

    return wrapper


def max_employees_check(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                return HttpResponseRedirect(reverse("license:license_required"))

            if license_obj.was_revoked:
                messages.error(
                    request,
                    "Your license requires reactivation. Please enter your license key again.",
                )
                return HttpResponseRedirect(reverse("license:license_activation"))

            company = license_obj.company
            Employee = apps.get_model("Employee", "Employee")

            employee_count = Employee.objects.filter(company=company).count()

            if employee_count >= license_obj.subscription_tier.max_employees:
                messages.error(
                    request,
                    "You have reached the maximum number of employees allowed by your subscription.",
                )
                return HttpResponseRedirect(reverse("dashboard"))

            return view_func(request, *args, **kwargs)
        except Exception as e:
            if settings.DEBUG:
                messages.error(request, f"License check error: {str(e)}")
            return HttpResponseRedirect(reverse("license:license_required"))

    return wrapper


def max_users_check(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            from .models import License, Company
            from django.contrib.auth import get_user_model

            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                return HttpResponseRedirect(reverse("license:license_required"))

            if license_obj.was_revoked:
                messages.error(
                    request,
                    "Your license requires reactivation. Please enter your license key again.",
                )
                return HttpResponseRedirect(reverse("license:license_activation"))

            company = license_obj.company
            User = get_user_model()

            user_count = User.objects.all().count()

            if user_count >= license_obj.subscription_tier.max_users:
                messages.error(
                    request,
                    "You have reached the maximum number of users allowed by your subscription.",
                )
                return HttpResponseRedirect(reverse("dashboard"))

            return view_func(request, *args, **kwargs)
        except Exception as e:
            if settings.DEBUG:
                messages.error(request, f"License check error: {str(e)}")
            return HttpResponseRedirect(reverse("license:license_required"))

    return wrapper


def offline_license_check(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            from .models import License

            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                return HttpResponseRedirect(reverse("license:license_required"))

            if license_obj.was_revoked:
                messages.error(
                    request,
                    "Your license requires reactivation. Please enter your license key again.",
                )
                return HttpResponseRedirect(reverse("license:license_activation"))

            hardware_fingerprint = get_hardware_fingerprint()
            is_valid, message = validate_license(license_obj, hardware_fingerprint)

            if not is_valid:
                messages.error(request, f"License issue: {message}")
                return HttpResponseRedirect(reverse("license:license_required"))

            if license_obj.needs_online_verification():
                online_valid, online_message = license_obj.verify_online()
                if not online_valid:
                    if "offline grace period" not in online_message:
                        messages.warning(
                            request, f"License verification: {online_message}"
                        )

            return view_func(request, *args, **kwargs)
        except Exception as e:
            if settings.DEBUG:
                messages.error(request, f"License check error: {str(e)}")
            return HttpResponseRedirect(reverse("license:license_required"))

    return wrapper


def online_verification_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            from .models import License

            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                return HttpResponseRedirect(reverse("license:license_required"))

            if license_obj.was_revoked:
                messages.error(
                    request,
                    "Your license requires reactivation. Please enter your license key again.",
                )
                return HttpResponseRedirect(reverse("license:license_activation"))

            online_valid, message = license_obj.verify_online()
            if not online_valid:
                messages.error(request, f"Online verification required: {message}")
                return HttpResponseRedirect(reverse("license:license_required"))

            return view_func(request, *args, **kwargs)
        except Exception as e:
            if settings.DEBUG:
                messages.error(request, f"License check error: {str(e)}")
            return HttpResponseRedirect(reverse("license:license_required"))

    return wrapper
