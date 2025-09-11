from django.contrib import admin
from .models import Company, SubscriptionTier, License


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
        ("Features", {"fields": ("features",)}),
    )

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "contact_phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_email")
    list_editable = ("is_active",)


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = (
        "license_key",
        "company",
        "subscription_tier",
        "expiration_date",
        "is_active",
    )
    list_filter = ("is_active", "subscription_tier")
    search_fields = ("license_key", "company__name")
    readonly_fields = ("license_key", "created_at")
