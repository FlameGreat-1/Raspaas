import json
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
from .models import Company, SubscriptionTier, License
from .utils import (
    generate_license_key,
    get_hardware_fingerprint,
    validate_license,
    encrypt_license_data,
    decrypt_license_data,
)
from .decorators import license_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
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

        if not license_key:
            messages.error(request, "License key is required.")
            return redirect("license:license_activation")

        hardware_fingerprint = get_hardware_fingerprint()

        is_valid, license_obj, message = License.activate_license(
            license_key, hardware_fingerprint
        )

        if is_valid:
            messages.success(request, "License activated successfully!")
            if request.user.is_authenticated:
                return redirect("license:license_status")
            else:
                return redirect("accounts:login")
        else:
            messages.error(request, f"License activation failed: {message}")
            return redirect("license:license_activation")


class LicenseRequiredView(View):
    template_name = "license/required.html"

    def get(self, request):
        response = render(request, self.template_name)
        response.status_code = 200
        return response

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
        except:
            return redirect("license:license_required")

    def post(self, request):
        try:
            license_obj = License.objects.filter(is_active=True).first()
            if not license_obj:
                messages.error(request, "No active license found.")
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
                license_obj.verify_online()
            except:
                pass

            messages.success(
                request,
                f"License renewed successfully until {license_obj.expiration_date}!",
            )
            return redirect("license:license_status")

        except Exception as e:
            messages.error(request, f"Renewal failed: {str(e)}")
            return redirect("license:license_renewal")


class AdminLicenseListView(LoginRequiredMixin, View):
    template_name = "license/admin/list.html"

    def get(self, request):
        if not request.user.is_staff:
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
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})
            else:
                messages.error(request, f"Error creating company: {str(e)}")
                return redirect("license:admin_license_create")


class AdminLicenseCreateView(LoginRequiredMixin, View):
    template_name = "license/admin/create.html"

    def get(self, request):
        if not request.user.is_staff:
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

            messages.success(
                request, f"License created successfully for {company.name}!"
            )
            return redirect("license:admin_license_detail", license_id=license_obj.id)

        except Exception as e:
            messages.error(request, f"License creation failed: {str(e)}")
            return redirect("license:admin_license_create")


class AdminLicenseDetailView(LoginRequiredMixin, View):
    template_name = "license/admin/detail.html"

    def get(self, request, license_id):
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        license_obj = get_object_or_404(License, id=license_id)
        return render(request, self.template_name, {"license": license_obj})


class AdminLicenseUpdateView(LoginRequiredMixin, View):
    template_name = "license/admin/update.html"

    def get(self, request, license_id):
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        license_obj = get_object_or_404(License, id=license_id)
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
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        try:
            license_obj = get_object_or_404(License, id=license_id)

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

            messages.success(request, "License updated successfully!")
            return redirect("license:admin_license_detail", license_id=license_obj.id)

        except Exception as e:
            messages.error(request, f"License update failed: {str(e)}")
            return redirect("license:admin_license_update", license_id=license_id)


class AdminLicenseRevokeView(LoginRequiredMixin, View):
    def post(self, request, license_id):
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access this page.")
            return redirect("dashboard")

        try:
            license_obj = get_object_or_404(License, id=license_id)
            reason = request.POST.get("revocation_reason", "Revoked by administrator")
            license_obj.revoke(reason=reason)
            license_obj.was_revoked = True
            license_obj.save()

            messages.success(
                request, f"License for {license_obj.company.name} has been revoked."
            )
            return redirect("license:admin_license_list")

        except Exception as e:
            messages.error(request, f"License revocation failed: {str(e)}")
            return redirect("license:admin_license_detail", license_id=license_id)


class LicenseDownloadView(LoginRequiredMixin, View):
    @method_decorator(license_required)
    def get(self, request):
        license_obj = License.objects.filter(is_active=True).first()
        if not license_obj:
            messages.error(request, "No active license found.")
            return redirect("license:license_required")

        encrypted_data = encrypt_license_data(license_obj)

        response = HttpResponse(encrypted_data, content_type="text/plain")
        response["Content-Disposition"] = (
            f'attachment; filename="{license_obj.company.name}_license.lic"'
        )

        return response


class LicenseValidateAPIView(View):
    def post(self, request):
        license_key = request.POST.get("license_key")
        hardware_fingerprint = request.POST.get("hardware_fingerprint")

        if not license_key or not hardware_fingerprint:
            return JsonResponse(
                {"valid": False, "message": "Missing required parameters"}
            )

        try:
            license_obj = License.objects.get(license_key=license_key)

            if license_obj.remotely_revoked:
                return JsonResponse(
                    {
                        "valid": False,
                        "message": license_obj.revocation_reason
                        or "License has been revoked",
                        "revoked": True,
                    }
                )

            if license_obj.was_revoked:
                return JsonResponse(
                    {
                        "valid": False,
                        "message": "License requires reactivation",
                        "requires_reactivation": True,
                    }
                )

            is_valid, message = validate_license(license_obj, hardware_fingerprint)

            if is_valid and license_obj.online_check_required:
                online_valid, online_message = license_obj.verify_online()
                if not online_valid and "offline grace period" not in online_message:
                    is_valid = False
                    message = online_message

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

            return JsonResponse(response_data)

        except License.DoesNotExist:
            return JsonResponse({"valid": False, "message": "Invalid license key"})
        except Exception as e:
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


class SubscriptionTierDeleteView(LoginRequiredMixin, DeleteView):
    model = SubscriptionTier
    template_name = "license/subscription_tier_confirm_delete.html"
    success_url = reverse_lazy("license:subscription_tier_list")


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

        if not license_key or not hardware_fingerprint:
            return JsonResponse(
                {"valid": False, "message": "Missing required parameters"}
            )

        try:
            license_obj = License.objects.get(license_key=license_key)

            if license_obj.remotely_revoked:
                return JsonResponse(
                    {
                        "valid": False,
                        "message": license_obj.revocation_reason
                        or "License has been revoked",
                        "revoked": True,
                    }
                )

            if license_obj.was_revoked:
                return JsonResponse(
                    {
                        "valid": False,
                        "message": "License requires reactivation",
                        "requires_reactivation": True,
                    }
                )

            if not license_obj.is_active:
                return JsonResponse({"valid": False, "message": "License is inactive"})

            if license_obj.is_expired():
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
                    return JsonResponse(
                        {"valid": False, "message": "Maximum activations reached"}
                    )

                license_obj.activation_count += 1
                license_obj.save(update_fields=["activation_count"])

            license_obj.last_verified = timezone.now()
            license_obj.last_online_check = timezone.now()
            license_obj.save(update_fields=["last_verified", "last_online_check"])

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
            return JsonResponse({"valid": False, "message": "Invalid license key"})
        except Exception as e:
            return JsonResponse(
                {"valid": False, "message": f"Verification error: {str(e)}"}
            )
