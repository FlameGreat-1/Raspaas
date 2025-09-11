from django.urls import path
from . import views
from . import views, tests

app_name = 'license'

urlpatterns = [
    # User-facing license URLs
    path('activate/', views.LicenseActivationView.as_view(), name='license_activation'),
    path('required/', views.LicenseRequiredView.as_view(), name='license_required'),
    path('expired/', views.LicenseExpiredView.as_view(), name='license_expired'),
    path('status/', views.LicenseStatusView.as_view(), name='license_status'),
    path('renewal/', views.LicenseRenewalView.as_view(), name='license_renewal'),
    path('download/', views.LicenseDownloadView.as_view(), name='license_download'),
    
    # Admin license management URLs
    path('admin/licenses/', views.AdminLicenseListView.as_view(), name='admin_license_list'),
    path('create-company-ajax/', views.CreateCompanyAjaxView.as_view(), name='create_company_ajax'),
    path('admin/licenses/create/', views.AdminLicenseCreateView.as_view(), name='admin_license_create'),
    path('admin/licenses/<int:license_id>/', views.AdminLicenseDetailView.as_view(), name='admin_license_detail'),
    path('admin/licenses/<int:license_id>/update/', views.AdminLicenseUpdateView.as_view(), name='admin_license_update'),
    path('admin/licenses/<int:license_id>/revoke/', views.AdminLicenseRevokeView.as_view(), name='admin_license_revoke'),
    
    path('subscription-tiers/', views.SubscriptionTierListView.as_view(), name='subscription_tier_list'),
    path('subscription-tiers/create/', views.SubscriptionTierCreateView.as_view(), name='subscription_tier_create'),
    path('subscription-tiers/<int:pk>/edit/', views.SubscriptionTierUpdateView.as_view(), name='subscription_tier_edit'),
    path('subscription-tiers/<int:pk>/delete/', views.SubscriptionTierDeleteView.as_view(), name='subscription_tier_delete'),

    # API endpoints
    path('api/validate/', views.LicenseValidateAPIView.as_view(), name='license_validate_api'),
    path('api/verify/', views.LicenseVerifyAPIView.as_view(), name='license_verify_api'),

    path('test-binding/', tests.test_hardware_binding, name='test_binding'),
]
