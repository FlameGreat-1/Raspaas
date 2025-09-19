from django.contrib import admin
from django.utils.html import format_html
import logging
from .models import Company, SubscriptionTier, License, LicenseAttempt

logger = logging.getLogger("license_security")


@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "max_employees",
        "max_users",
        "price_monthly",
        "price_annual",
        "is_active",
    )
    list_filter = ("is_active", "name")
    search_fields = ("name", "description")
    list_editable = ("is_active",)
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        ("Limits", {"fields": ("max_employees", "max_users")}),
        (
            "Pricing",
            {
                "fields": (
                    "price_monthly",
                    "price_quarterly",
                    "price_biannual",
                    "price_annual",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            logger.info(
                f"Subscription tier '{obj.name}' updated by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )
        else:
            logger.info(
                f"Subscription tier '{obj.name}' created by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "contact_phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_email")
    list_editable = ("is_active",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            logger.info(
                f"Company '{obj.name}' updated by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )
        else:
            logger.info(
                f"Company '{obj.name}' created by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = (
        "license_key_display",
        "company",
        "subscription_tier",
        "expiration_date",
        "is_active",
        "integrity_status",
    )
    list_filter = ("is_active", "subscription_tier", "remotely_revoked", "was_revoked")
    search_fields = ("license_key", "company__name")
    readonly_fields = (
        "license_key",
        "created_at",
        "integrity_signature",
        "integrity_status",
        "issue_date",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {"fields": ("license_key", "company", "subscription_tier", "is_active")},
        ),
        (
            "Subscription",
            {"fields": ("duration_months", "amount_paid")},
        ),
        (
            "Dates",
            {
                "fields": (
                    "issue_date",
                    "start_date",
                    "expiration_date",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Activation",
            {"fields": ("hardware_fingerprint", "activation_count", "max_activations")},
        ),
        (
            "Verification",
            {
                "fields": (
                    "last_verified",
                    "last_online_check",
                    "online_check_required",
                    "max_offline_days",
                    "license_server_url",
                    "failed_verification_count",
                    "last_failed_verification",
                )
            },
        ),
        (
            "Revocation",
            {"fields": ("remotely_revoked", "was_revoked", "revocation_reason")},
        ),
        ("Security", {"fields": ("integrity_signature", "integrity_status")}),
    )

    def license_key_display(self, obj):
        return obj.license_key[-8:] if obj.license_key else ""

    license_key_display.short_description = "License Key"

    def integrity_status(self, obj):
        if obj.verify_integrity():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Invalid</span>')

    integrity_status.short_description = "Integrity"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.activation_count = 0
            obj.hardware_fingerprint = ""

        super().save_model(request, obj, form, change)
        obj.generate_integrity_signature()
        obj.save(update_fields=["integrity_signature"])

        if change:
            logger.info(
                f"License {obj.license_key[-8:]} updated by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )
        else:
            logger.info(
                f"License {obj.license_key[-8:]} created by admin {request.user.username} from IP {request.META.get('REMOTE_ADDR')}"
            )


@admin.register(LicenseAttempt)
class LicenseAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "ip_address",
        "timestamp",
        "attempt_type",
        "success",
        "license_key_display",
        "hardware_fingerprint_display",
    )
    list_filter = ("success", "attempt_type", "timestamp")
    search_fields = ("ip_address", "license_key", "user_agent", "hardware_fingerprint")
    readonly_fields = (
        "ip_address",
        "timestamp",
        "success",
        "license_key",
        "user_agent",
        "attempt_type",
        "cpu_info",
        "ram_info",
        "disk_info",
        "mac_address",
        "os_info",
        "hardware_fingerprint",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "timestamp",
                    "ip_address",
                    "success",
                    "attempt_type",
                    "license_key",
                )
            },
        ),
        (
            "Hardware Information",
            {
                "fields": (
                    "hardware_fingerprint",
                    "cpu_info",
                    "ram_info",
                    "disk_info",
                    "mac_address",
                    "os_info",
                )
            },
        ),
        ("Browser Information", {"fields": ("user_agent",)}),
    )

    def license_key_display(self, obj):
        return obj.license_key[-8:] if obj.license_key else "N/A"

    license_key_display.short_description = "License Key"

    def hardware_fingerprint_display(self, obj):
        return obj.hardware_fingerprint[-8:] if obj.hardware_fingerprint else "N/A"

    hardware_fingerprint_display.short_description = "Hardware ID"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
