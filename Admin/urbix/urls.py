"""
URL configuration for urbix project.

Integrated with HR Payroll system functionality.
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from urbix.views import home_view, dynamic_view

urlpatterns = [
    path("", lambda request: redirect("accounts:login"), name="home"),
    path("<str:page>", dynamic_view, name="get"),
    path("accounts/", include("accounts.urls")),
    path("employees/", include("employees.urls")),
    path("attendance/", include("attendance.urls")),
    path("payroll/", include("payroll.urls")),
    path("expenses/", include("expenses.urls")),
    path("accounting/", include("accounting.urls")),
    path("license/", include("License.urls", namespace="license")),
    path("admin/", admin.site.urls),
]

# Debug toolbar for development
if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Serve media and static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
