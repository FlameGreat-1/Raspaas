import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.urls import reverse, reverse_lazy
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from datetime import datetime, timedelta
from .models import Company, SubscriptionTier, License, LicenseAttempt
from .utils import (
    generate_license_key,
    get_hardware_fingerprint,
    validate_license,
    encrypt_license_data,
    decrypt_license_data,
    verify_license_online,
)
from .decorators import license_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

logger = logging.getLogger("license_security")


class LicenseActivationView(View):
    template_name = "license/activate.html"

    def get(self, request):
        try:
            license_obj = License.objects.filter(is_active=True).first()
            if license_obj and license_obj.was_revoked:
                return render(
                    request,
                    self.template_name,
                    {"license": None, "needs_reactivation": True},
                )
            return render(request, self.template_name, {"license": license_obj})
        except:
            return render(request, self.template_name, {"license": None})

    def post(self, request):
        license_key = request.POST.get("license_key")
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

        if not license_key:
            messages.error(request, "License key is required.")
            return redirect("license:license_activation")

        if ip_address and not LicenseAttempt.check_rate_limit(ip_address, "activation"):
            backoff_time = LicenseAttempt.get_backoff_time(ip_address, "activation")
            logger.warning(f"Rate limit exceeded for IP {ip_address} (activation)")
            messages.error(
                request,
                f"Too many activation attempts. Please try again in {backoff_time} seconds.",
            )
            return redirect("license:license_activation")

        hardware_fingerprint = get_hardware_fingerprint()

        is_valid, license_obj, message = License.activate_license(
            license_key, hardware_fingerprint, ip_address, user_agent
        )

        if is_valid:
            logger.info(
                f"License {license_key[-8:]} activated successfully from IP {ip_address}"
            )
            messages.success(request, "License activated successfully!")
            if request.user.is_authenticated:
                return redirect("license:license_status")
            else:
                return redirect("accounts:login")
        else:
            logger.warning(f"License activation failed: {message} from IP {ip_address}")
            messages.error(request, f"License activation failed: {message}")
            return redirect("license:license_activation")

class LicenseRequiredView(View):
    template_name = "license/required.html"

    def get(self, request):
        return render(request, self.template_name)


class LicenseExpiredView(View):
    template_name = "license/expired.html"

    def get(self, request):
        try:
            license_obj = License.objects.filter(is_active=True).first()
            return render(request, self.template_name, {"license": license_obj})
        except:
            return redirect("license:license_required")


class LicenseStatusView(LoginRequiredMixin, View):
    template_name = "license/status.html"

    def get(self, request):
        license_obj = License.objects.filter(is_active=True).first()

        if not license_obj:
            messages.error(
                request, "No valid license found. Please activate your license."
            )
            return redirect("license:license_required")

        if not license_obj.verify_integrity():
            logger.critical(
                f"License integrity check failed for IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "License validation error. Please contact support.")
            return redirect("license:license_required")

        if license_obj.was_revoked:
            messages.error(
                request,
                "Your license requires reactivation. Please enter your license key again.",
            )
            return redirect("license:license_activation")

        return render(request, self.template_name, {"license": license_obj})


class LicenseRenewalView(LoginRequiredMixin, View):
    template_name = "license/renewal.html"

    def get(self, request):
        try:
            license_obj = License.objects.filter(is_active=True).first()

            if license_obj and not license_obj.verify_integrity():
                logger.critical(
                    f"License integrity check failed for IP {request.META.get('REMOTE_ADDR')}"
                )
                messages.error(
                    request, "License validation error. Please contact support."
                )
                return redirect("license:license_required")

            subscription_tiers = SubscriptionTier.objects.filter(is_active=True)

            return render(
                request,
                self.template_name,
                {
                    "license": license_obj,
                    "subscription_tiers": subscription_tiers,
                    "durations": SubscriptionTier.DURATION_CHOICES,
                },
            )
        except Exception as e:
            logger.error(f"Error in license renewal view: {str(e)}")
            return redirect("license:license_required")

    def post(self, request):
        try:
            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                messages.error(request, "No active license found.")
                return redirect("license:license_required")

            if not license_obj.verify_integrity():
                logger.critical(
                    f"License integrity check failed for IP {request.META.get('REMOTE_ADDR')}"
                )
                messages.error(
                    request, "License validation error. Please contact support."
                )
                return redirect("license:license_required")

            tier_id = request.POST.get("tier_id")
            duration = int(request.POST.get("duration"))

            if tier_id:
                new_tier = get_object_or_404(
                    SubscriptionTier, id=tier_id, is_active=True
                )
                license_obj.renew(duration, new_tier)
            else:
                license_obj.renew(duration)

            try:
                ip_address = request.META.get("REMOTE_ADDR")
                user_agent = request.META.get("HTTP_USER_AGENT")

                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=True,
                    license_key=license_obj.license_key,
                    user_agent=user_agent,
                    attempt_type="renewal",
                )

                license_obj.verify_online()
            except Exception as e:
                logger.error(f"Error in online verification during renewal: {str(e)}")
                pass

            logger.info(
                f"License {license_obj.license_key[-8:]} renewed successfully until {license_obj.expiration_date}"
            )
            messages.success(
                request,
                f"License renewed successfully until {license_obj.expiration_date}!",
            )
            return redirect("license:license_status")

        except Exception as e:
            logger.error(f"License renewal failed: {str(e)}")
            messages.error(request, f"Renewal failed: {str(e)}")
            return redirect("license:license_renewal")


class AdminLicenseListView(LoginRequiredMixin, View):
    template_name = "license/admin/list.html"

    def get(self, request):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized admin access attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        licenses = License.objects.all().select_related("company", "subscription_tier")

        search_query = request.GET.get("q")
        if search_query:
            licenses = licenses.filter(
                Q(company__name__icontains=search_query)
                | Q(license_key__icontains=search_query)
            )

        status_filter = request.GET.get("status")
        if status_filter == "active":
            licenses = licenses.filter(
                is_active=True,
                remotely_revoked=False,
                expiration_date__gte=timezone.now().date(),
            )
        elif status_filter == "expired":
            licenses = licenses.filter(expiration_date__lt=timezone.now().date())
        elif status_filter == "inactive":
            licenses = licenses.filter(Q(is_active=False) | Q(remotely_revoked=True))

        return render(request, self.template_name, {"licenses": licenses})

class CreateCompanyAjaxView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized company creation attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            return JsonResponse({"success": False, "error": "Permission denied"})

        try:
            name = request.POST.get("name")
            address = request.POST.get("address")
            contact_email = request.POST.get("contact_email")
            contact_phone = request.POST.get("contact_phone")

            if not all([name, address, contact_email, contact_phone]):
                return JsonResponse(
                    {"success": False, "error": "All fields are required"}
                )

            company = Company.objects.create(
                name=name,
                address=address,
                contact_email=contact_email,
                contact_phone=contact_phone,
                is_active=True,
            )

            logger.info(
                f"Company '{company.name}' created by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "company_id": company.id,
                        "company_name": company.name,
                    }
                )
            else:
                messages.success(
                    request, f'Company "{company.name}" created successfully!'
                )
                return redirect("license:admin_license_create")

        except Exception as e:
            logger.error(f"Error creating company: {str(e)}")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            else:
                messages.error(request, f"Error creating company: {str(e)}")
                return redirect("license:admin_license_create")


class AdminLicenseCreateView(LoginRequiredMixin, View):
    template_name = "license/admin/create.html"

    def get(self, request):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized admin access attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        companies = Company.objects.filter(is_active=True)
        subscription_tiers = SubscriptionTier.objects.filter(is_active=True)

        return render(
            request,
            self.template_name,
            {
                "companies": companies,
                "subscription_tiers": subscription_tiers,
                "durations": SubscriptionTier.DURATION_CHOICES,
            },
        )

    def post(self, request):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized license creation attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        try:
            company_id = request.POST.get("company_id")
            tier_id = request.POST.get("tier_id")
            duration = int(request.POST.get("duration"))
            max_activations = int(request.POST.get("max_activations", 1))
            online_check_required = request.POST.get("online_check_required") == "True"
            max_offline_days = int(request.POST.get("max_offline_days", 30))

            company = get_object_or_404(Company, id=company_id, is_active=True)
            tier = get_object_or_404(SubscriptionTier, id=tier_id, is_active=True)

            start_date = timezone.now().date()
            expiration_date = start_date + timedelta(days=duration * 30)
            amount_paid = tier.get_price_for_duration(duration)

            license_obj = License.objects.create(
                company=company,
                subscription_tier=tier,
                start_date=start_date,
                expiration_date=expiration_date,
                duration_months=duration,
                amount_paid=amount_paid,
                max_activations=max_activations,
                online_check_required=online_check_required,
                max_offline_days=max_offline_days,
            )

            logger.info(
                f"License {license_obj.license_key[-8:]} created for company '{company.name}' by admin {request.user.username}"
            )

            messages.success(
                request, f"License created successfully for {company.name}!"
            )
            return redirect("license:admin_license_detail", license_id=license_obj.id)

        except Exception as e:
            logger.error(f"License creation failed: {str(e)}")
            messages.error(request, f"License creation failed: {str(e)}")
            return redirect("license:admin_license_create")


class AdminLicenseDetailView(LoginRequiredMixin, View):
    template_name = "license/admin/detail.html"

    def get(self, request, license_id):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized admin access attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        license_obj = get_object_or_404(License, id=license_id)

        if not license_obj.verify_integrity():
            logger.critical(
                f"License integrity check failed for license {license_obj.license_key[-8:]} viewed by admin {request.user.username}"
            )
            messages.error(
                request,
                "License integrity check failed. This license may have been tampered with.",
            )

        return render(request, self.template_name, {"license": license_obj})


class AdminLicenseUpdateView(LoginRequiredMixin, View):
    template_name = "license/admin/update.html"

    def get(self, request, license_id):
        if not request.user.is_staff:
            logger.warning(
                f"Unauthorized admin access attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        license_obj = get_object_or_404(License, id=license_id)

        if not license_obj.verify_integrity():
            logger.critical(
                f"License integrity check failed for license {license_obj.license_key[-8:]} being updated by admin {request.user.username}"
            )
            messages.error(
                request,
                "License integrity check failed. This license may have been tampered with.",
            )

        subscription_tiers = SubscriptionTier.objects.filter(is_active=True)

        return render(
            request,
            self.template_name,
            {
                "license": license_obj,
                "subscription_tiers": subscription_tiers,
                "durations": SubscriptionTier.DURATION_CHOICES,
            },
        )
    
    def post(self, request, license_id):
        if not request.user.is_staff:
            logger.warning(f"Unauthorized license update attempt from IP {request.META.get('REMOTE_ADDR')}")
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        try:
            license_obj = get_object_or_404(License, id=license_id)
            
            if not license_obj.verify_integrity():
                logger.critical(f"License integrity check failed for license {license_obj.license_key[-8:]} being updated by admin {request.user.username}")
                messages.error(request, "License integrity check failed. This license may have been tampered with.")
                return redirect("license:admin_license_detail", license_id=license_obj.id)

            tier_id = request.POST.get("tier_id")
            duration = int(request.POST.get("duration"))
            is_active = request.POST.get("is_active") == "on"
            max_activations = int(request.POST.get("max_activations", 1))
            online_check_required = request.POST.get("online_check_required") == "True"
            max_offline_days = int(request.POST.get("max_offline_days", 30))
            remotely_revoked = request.POST.get("remotely_revoked") == "on"
            revocation_reason = request.POST.get("revocation_reason", "")

            if request.POST.get("clear_revocation") == "on":
                remotely_revoked = False
                revocation_reason = ""

            if tier_id:
                tier = get_object_or_404(SubscriptionTier, id=tier_id, is_active=True)
                license_obj.subscription_tier = tier

            license_obj.duration_months = duration
            license_obj.is_active = is_active
            license_obj.max_activations = max_activations
            license_obj.online_check_required = online_check_required
            license_obj.max_offline_days = max_offline_days
            license_obj.remotely_revoked = remotely_revoked

            if remotely_revoked and revocation_reason:
                license_obj.revocation_reason = revocation_reason
                license_obj.was_revoked = True
            elif not remotely_revoked and not license_obj.was_revoked:
                license_obj.revocation_reason = ""

            if request.POST.get("reset_expiration") == "on":
                license_obj.start_date = timezone.now().date()
                license_obj.expiration_date = license_obj.start_date + timedelta(
                    days=duration * 30
                )

            license_obj.amount_paid = (
                license_obj.subscription_tier.get_price_for_duration(duration)
            )
            license_obj.save()
            
            logger.info(f"License {license_obj.license_key[-8:]} updated by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}")

            messages.success(request, "License updated successfully!")
            return redirect("license:admin_license_detail", license_id=license_obj.id)

        except Exception as e:
            logger.error(f"License update failed: {str(e)}")
            messages.error(request, f"License update failed: {str(e)}")
            return redirect("license:admin_license_update", license_id=license_id)


class AdminLicenseRevokeView(LoginRequiredMixin, View):
    def post(self, request, license_id):
        if not request.user.is_staff:
            logger.warning(f"Unauthorized license revocation attempt from IP {request.META.get('REMOTE_ADDR')}")
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        try:
            license_obj = get_object_or_404(License, id=license_id)
            
            if not license_obj.verify_integrity():
                logger.critical(f"License integrity check failed for license {license_obj.license_key[-8:]} being revoked by admin {request.user.username}")
                messages.error(request, "License integrity check failed. This license may have been tampered with.")
                return redirect("license:admin_license_detail", license_id=license_obj.id)
                
            reason = request.POST.get("revocation_reason", "Revoked by administrator")
            license_obj.revoke(reason=reason)
            license_obj.was_revoked = True
            license_obj.save()
            
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')
            
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=True,
                license_key=license_obj.license_key,
                user_agent=user_agent,
                attempt_type='revocation'
            )
            
            logger.warning(f"License {license_obj.license_key[-8:]} for company '{license_obj.company.name}' revoked by admin {request.user.username} from IP {ip_address}")

            messages.success(
                request, f"License for {license_obj.company.name} has been revoked."
            )
            return redirect("license:admin_license_list")

        except Exception as e:
            logger.error(f"License revocation failed: {str(e)}")
            messages.error(request, f"License revocation failed: {str(e)}")
            return redirect("license:admin_license_detail", license_id=license_id)


class LicenseDownloadView(LoginRequiredMixin, View):
    @method_decorator(license_required)
    def get(self, request):
        license_obj = License.objects.filter(is_active=True).first()
        if not license_obj:
            messages.error(request, "No active license found.")
            return redirect("license:license_required")
            
        if not license_obj.verify_integrity():
            logger.critical(f"License integrity check failed during download for license {license_obj.license_key[-8:]} from IP {request.META.get('REMOTE_ADDR')}")
            messages.error(request, "License validation error. Please contact support.")
            return redirect("license:license_required")

        encrypted_data = encrypt_license_data(license_obj)
        
        logger.info(f"License {license_obj.license_key[-8:]} downloaded by user {request.user.username} from IP {request.META.get('REMOTE_ADDR')}")

        response = HttpResponse(encrypted_data, content_type="text/plain")
        response["Content-Disposition"] = (
            f'attachment; filename="{license_obj.company.name}_license.lic"'
        )

        return response


class LicenseValidateAPIView(View):
    def post(self, request):
        license_key = request.POST.get("license_key")
        hardware_fingerprint = request.POST.get("hardware_fingerprint")
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT')

        if not license_key or not hardware_fingerprint:
            logger.warning(f"License validation attempt with missing parameters from IP {ip_address}")
            return JsonResponse(
                {"valid": False, "message": "Missing required parameters"}
            )

        if ip_address and not LicenseAttempt.check_rate_limit(ip_address, 'verification'):
            backoff_time = LicenseAttempt.get_backoff_time(ip_address, 'verification')
            logger.warning(f"Rate limit exceeded for IP {ip_address} (verification)")
            return JsonResponse(
                {"valid": False, "message": f"Too many verification attempts. Please try again in {backoff_time} seconds."}
            )

        try:
            license_obj = License.objects.get(license_key=license_key)

            if not license_obj.verify_integrity():
                logger.critical(f"License integrity check failed during validation for license {license_obj.license_key[-8:]} from IP {ip_address}")
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type='verification'
                )
                return JsonResponse({"valid": False, "message": "License integrity check failed"})

            if license_obj.remotely_revoked:
                logger.warning(f"Attempt to validate revoked license {license_obj.license_key[-8:]} from IP {ip_address}")
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type='verification'
                )
                return JsonResponse(
                    {
                        "valid": False,
                        "message": license_obj.revocation_reason
                        or "License has been revoked",
                        "revoked": True,
                    }
                )

            if license_obj.was_revoked:
                logger.warning(f"Attempt to validate previously revoked license {license_obj.license_key[-8:]} from IP {ip_address}")
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type='verification'
                )
                return JsonResponse(
                    {
                        "valid": False,
                        "message": "License requires reactivation",
                        "requires_reactivation": True,
                    }
                )

            is_valid, message = validate_license(license_obj, hardware_fingerprint, ip_address, user_agent)

            if is_valid and license_obj.online_check_required:
                online_valid, online_message = license_obj.verify_online()
                if not online_valid and "offline grace period" not in online_message:
                    is_valid = False
                    message = online_message

            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=is_valid,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type='verification'
            )

            response_data = {
                "valid": is_valid,
                "message": message,
                "company": license_obj.company.name,
                "tier": license_obj.subscription_tier.name,
                "expiration": license_obj.expiration_date.isoformat(),
                "max_employees": license_obj.subscription_tier.max_employees,
                "max_users": license_obj.subscription_tier.max_users,
                "online_check_required": license_obj.online_check_required,
                "max_offline_days": license_obj.max_offline_days,
                "revoked": license_obj.remotely_revoked,
                "was_revoked": license_obj.was_revoked,
            }

            if is_valid:
                logger.info(f"License {license_obj.license_key[-8:]} validated successfully from IP {ip_address}")
            else:
                logger.warning(f"License {license_obj.license_key[-8:]} validation failed: {message} from IP {ip_address}")

            return JsonResponse(response_data)

        except License.DoesNotExist:
            logger.warning(f"Validation attempt with invalid license key from IP {ip_address}")
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=False,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type='verification'
            )
            return JsonResponse({"valid": False, "message": "Invalid license key"})
        except Exception as e:
            logger.error(f"License validation error: {str(e)} from IP {ip_address}")
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=False,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type='verification'
            )
            return JsonResponse({"valid": False, "message": str(e)})


class SubscriptionTierListView(LoginRequiredMixin, ListView):
    model = SubscriptionTier
    template_name = "license/subscription_tier_list.html"
    context_object_name = "subscription_tiers"

    def get_queryset(self):
        return SubscriptionTier.objects.all().order_by("price_monthly")


class SubscriptionTierCreateView(LoginRequiredMixin, CreateView):
    model = SubscriptionTier
    template_name = "license/subscription_tier_form.html"
    fields = [
        "name",
        "description",
        "max_employees",
        "max_users",
        "price_monthly",
        "price_quarterly",
        "price_biannual",
        "price_annual",
        "is_active",
    ]
    success_url = reverse_lazy("license:subscription_tier_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Subscription Tier"
        context["action"] = "Create"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            f"Subscription tier '{form.instance.name}' created by admin {self.request.user.username} from IP {self.request.META.get('REMOTE_ADDR')}"
        )
        return response


class SubscriptionTierUpdateView(LoginRequiredMixin, UpdateView):
    model = SubscriptionTier
    template_name = "license/subscription_tier_form.html"
    fields = [
        "name",
        "description",
        "max_employees",
        "max_users",
        "price_monthly",
        "price_quarterly",
        "price_biannual",
        "price_annual",
        "is_active",
    ]
    success_url = reverse_lazy("license:subscription_tier_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Subscription Tier"
        context["action"] = "Update"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info(
            f"Subscription tier '{form.instance.name}' updated by admin {self.request.user.username} from IP {self.request.META.get('REMOTE_ADDR')}"
        )
        return response


class SubscriptionTierDeleteView(LoginRequiredMixin, DeleteView):
    model = SubscriptionTier
    template_name = "license/subscription_tier_confirm_delete.html"
    success_url = reverse_lazy("license:subscription_tier_list")

    def delete(self, request, *args, **kwargs):
        tier = self.get_object()
        logger.info(
            f"Subscription tier '{tier.name}' deleted by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
        )
        return super().delete(request, *args, **kwargs)


def login_exempt(view_func):
    view_func.login_exempt = True
    return view_func


@method_decorator(csrf_exempt, name="dispatch")
class LicenseVerifyAPIView(View):

    @method_decorator(login_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
            license_key = data.get("license_key")
            hardware_fingerprint = data.get("hardware_fingerprint")
        except:
            license_key = request.POST.get("license_key")
            hardware_fingerprint = request.POST.get("hardware_fingerprint")

        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

        if not license_key or not hardware_fingerprint:
            logger.warning(
                f"License verification attempt with missing parameters from IP {ip_address}"
            )
            return JsonResponse(
                {"valid": False, "message": "Missing required parameters"}
            )

        if ip_address and not LicenseAttempt.check_rate_limit(
            ip_address, "verification"
        ):
            backoff_time = LicenseAttempt.get_backoff_time(ip_address, "verification")
            logger.warning(f"Rate limit exceeded for IP {ip_address} (verification)")
            return JsonResponse(
                {
                    "valid": False,
                    "message": f"Too many verification attempts. Please try again in {backoff_time} seconds.",
                }
            )

        try:
            license_obj = License.objects.get(license_key=license_key)

            if not license_obj.verify_integrity():
                logger.critical(
                    f"License integrity check failed during verification for license {license_obj.license_key[-8:]} from IP {ip_address}"
                )
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )
                return JsonResponse(
                    {"valid": False, "message": "License integrity check failed"}
                )

            if license_obj.remotely_revoked:
                logger.warning(
                    f"Attempt to verify revoked license {license_obj.license_key[-8:]} from IP {ip_address}"
                )
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )
                return JsonResponse(
                    {
                        "valid": False,
                        "message": license_obj.revocation_reason
                        or "License has been revoked",
                        "revoked": True,
                    }
                )

            if license_obj.was_revoked:
                logger.warning(
                    f"Attempt to verify previously revoked license {license_obj.license_key[-8:]} from IP {ip_address}"
                )
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )
                return JsonResponse(
                    {
                        "valid": False,
                        "message": "License requires reactivation",
                        "requires_reactivation": True,
                    }
                )

            if not license_obj.is_active:
                logger.warning(
                    f"Attempt to verify inactive license {license_obj.license_key[-8:]} from IP {ip_address}"
                )
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )
                return JsonResponse({"valid": False, "message": "License is inactive"})

            if license_obj.is_expired():
                logger.warning(
                    f"Attempt to verify expired license {license_obj.license_key[-8:]} from IP {ip_address}"
                )
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )
                return JsonResponse(
                    {
                        "valid": False,
                        "message": "License has expired",
                        "expiration_date": license_obj.expiration_date.isoformat(),
                    }
                )
            if (
                license_obj.hardware_fingerprint
                and license_obj.hardware_fingerprint != hardware_fingerprint
            ):
                if license_obj.activation_count >= license_obj.max_activations:
                    logger.warning(
                        f"Maximum activations reached for license {license_obj.license_key[-8:]} from IP {ip_address}"
                    )
                    LicenseAttempt.log_attempt(
                        ip_address=ip_address,
                        success=False,
                        license_key=license_key,
                        user_agent=user_agent,
                        attempt_type="verification",
                    )
                    return JsonResponse(
                        {"valid": False, "message": "Maximum activations reached"}
                    )

                license_obj.activation_count += 1
                license_obj.save(update_fields=["activation_count"])
                logger.info(
                    f"New hardware fingerprint registered for license {license_obj.license_key[-8:]} from IP {ip_address} (activation {license_obj.activation_count}/{license_obj.max_activations})"
                )

            license_obj.last_verified = timezone.now()
            license_obj.last_online_check = timezone.now()
            license_obj.save(update_fields=["last_verified", "last_online_check"])

            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=True,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )

            logger.info(
                f"License {license_obj.license_key[-8:]} verified successfully from IP {ip_address}"
            )

            return JsonResponse(
                {
                    "valid": True,
                    "message": "License verified successfully",
                    "company_name": license_obj.company.name,
                    "company_email": license_obj.company.contact_email,
                    "company_address": license_obj.company.address,
                    "company_phone": license_obj.company.contact_phone,
                    "tier_name": license_obj.subscription_tier.name,
                    "tier_description": license_obj.subscription_tier.description,
                    "max_employees": license_obj.subscription_tier.max_employees,
                    "max_users": license_obj.subscription_tier.max_users,
                    "expiration_date": license_obj.expiration_date.isoformat(),
                    "max_activations": license_obj.max_activations,
                    "online_check_required": license_obj.online_check_required,
                    "max_offline_days": license_obj.max_offline_days,
                    "was_revoked": license_obj.was_revoked,
                }
            )

        except License.DoesNotExist:
            logger.warning(
                f"Verification attempt with invalid license key from IP {ip_address}"
            )
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=False,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )
            return JsonResponse({"valid": False, "message": "Invalid license key"})
        except Exception as e:
            logger.error(f"License verification error: {str(e)} from IP {ip_address}")
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=False,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )
            return JsonResponse(
                {"valid": False, "message": f"Verification error: {str(e)}"}
            )
