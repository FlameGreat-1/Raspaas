from django.shortcuts import render, redirect
from django.views import View
from django.template import TemplateDoesNotExist
from django.http import HttpResponse
from accounts.models import SystemConfiguration
from django.contrib import messages
from django.db.models import Q


def home_view(request):
    return render(request, f"index.html")


def dynamic_view(request, page):
    print(f"Trying to render template: {page}")

    context = {}

    if page == "apps-kanban.html":
        return redirect("accounts:system_config")

    if page == "system-config":
        if not SystemConfiguration.objects.exists():
            created_count = SystemConfiguration.initialize_default_settings()
            messages.success(
                request, f"Initialized {created_count} default system configurations."
            )

        queryset = SystemConfiguration.objects.filter(is_active=True)

        setting_type = request.GET.get("type")
        if setting_type:
            queryset = queryset.filter(setting_type=setting_type)

        search_query = request.GET.get("search")
        if search_query:

            queryset = queryset.filter(
                Q(key__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(value__icontains=search_query)
            )

        configurations = queryset.order_by("setting_type", "key")

        grouped_configs = {}
        for config in configurations:
            if config.setting_type not in grouped_configs:
                grouped_configs[config.setting_type] = []
            grouped_configs[config.setting_type].append(config)

        context = {
            "page_title": "System Configuration",
            "configurations": configurations,
            "grouped_configs": grouped_configs,
            "setting_types": SystemConfiguration.SETTING_TYPES,
            "selected_type": setting_type or "",
            "search_query": search_query or "",
            "total_configs": configurations.count(),
            "can_add_setting": True,
            "can_export": True,
            "can_bulk_edit": True,
            "action": "list",
        }

        return render(request, "accounts/system_config.html", context)

    try:
        return render(request, f"{page}", context)
    except TemplateDoesNotExist as e:
        print(f"Template not found: {e}")
        try:
            return render(request, f"pages-404.html")
        except TemplateDoesNotExist as e2:
            print(f"404 template not found: {e2}")
            return HttpResponse("Page not found", status=404)
