from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('force-password-change/', views.ForcePasswordChangeView.as_view(), name='force_password_change'),
    
    # Password Reset URLs
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.password_reset_done_view, name='password_reset_done'),
    path('reset-password/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.password_reset_complete_view, name='password_reset_complete'),
    
    # Password Change URLs
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', views.password_change_done_view, name='password_change_done'),
    
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard_alt'),
    
    # Employee Management URLs
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('employees/<int:employee_id>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/<int:employee_id>/edit/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('employees/<int:employee_id>/delete/', views.employee_delete_view, name='employee_delete'),
    path('employees/search/', views.employee_search_ajax, name='employee_search_ajax'),
    path('employees/export/', views.employee_export_view, name='employee_export'),
    path('employees/advanced-search/', views.advanced_search_view, name='advanced_search'),
    path('employees/hierarchy/', views.employee_hierarchy_view, name='employee_hierarchy'),
    
    # Bulk Operations URLs
    path('employees/bulk-upload/', views.BulkEmployeeUploadView.as_view(), name='bulk_employee_upload'),
    path('employees/template-download/', views.employee_template_download, name='employee_template_download'),
    path('employees/bulk-action/', views.bulk_employee_action, name='bulk_employee_action'),
    path('employees/import-status/<str:task_id>/', views.employee_import_status, name='employee_import_status'),
    path('bulk-notification/', views.bulk_notification_view, name='bulk_notification'),
    
    # Department Management URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:department_id>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:department_id>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:department_id>/delete/', views.department_delete_view, name='department_delete'),
    path('departments/export/', views.department_export_view, name='department_export'),
    
    # Role Management URLs
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:role_id>/', views.RoleDetailView.as_view(), name='role_detail'),
    path('roles/<int:role_id>/edit/', views.RoleUpdateView.as_view(), name='role_update'),
    path('roles/<int:role_id>/delete/', views.role_delete_view, name='role_delete'),
    path('roles/export/', views.role_export_view, name='role_export'),
    
    # Profile Management URLs
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/security/', views.account_security_view, name='account_security'),
    
    # Session Management URLs
    path('sessions/', views.user_sessions_view, name='user_sessions'),
    path('sessions/<uuid:session_id>/terminate/', views.terminate_session_view, name='terminate_session'),
    path('sessions/terminate-all/', views.terminate_all_sessions_view, name='terminate_all_sessions'),
    path('sessions/management/', views.session_management_view, name='session_management'),
    path('sessions/<uuid:session_id>/admin-terminate/', views.terminate_user_session_view, name='admin_terminate_session'),
    path('sessions/export/', views.session_export_view, name='session_export'),
    
    # User Management Actions URLs
    path('users/<int:user_id>/unlock/', views.unlock_account_view, name='unlock_account'),
    path('users/<int:user_id>/reset-password/', views.reset_user_password_view, name='reset_user_password'),
    path('users/<int:user_id>/change-status/', views.change_user_status_view, name='change_user_status'),
    path('users/<int:user_id>/activity-log/', views.user_activity_log_view, name='user_activity_log'),
    path('activity-log/', views.user_activity_log_view, name='my_activity_log'),
    
    # System Configuration URLs - Single View Approach
    path('system-config/', views.SystemConfigurationView.as_view(), name='system_config'),
    path('system-config/<str:action>/', views.SystemConfigurationView.as_view(), name='system_config'),
    path('system-config/<str:action>/<int:config_id>/', views.SystemConfigurationView.as_view(), name='system_config'),
    
    # System Administration URLs
    path('system-init/', views.system_initialization_view, name='system_initialization'),
    
    # Audit Log URLs
    path('audit-logs/', views.audit_log_view, name='audit_logs'),
    path('audit-logs/export/', views.audit_log_export_view, name='audit_log_export'),
    
    # API Key Management URLs
    path('api-keys/', views.APIKeyListView.as_view(), name='api_key_list'),
    path('api-keys/create/', views.APIKeyCreateView.as_view(), name='api_key_create'),
    path('api-keys/<uuid:key_id>/revoke/', views.api_key_revoke_view, name='api_key_revoke'),
    
    # AJAX & Utility URLs
    path('ajax/dashboard-widgets/', views.dashboard_widgets_ajax, name='dashboard_widgets_ajax'),
    path('ajax/quick-stats/', views.quick_stats_ajax, name='quick_stats_ajax'),
    path('ajax/employee-autocomplete/', views.employee_autocomplete_ajax, name='employee_autocomplete_ajax'),
    path('ajax/validate-employee-code/', views.validate_employee_code_ajax, name='validate_employee_code_ajax'),
    path('ajax/validate-email/', views.validate_email_ajax, name='validate_email_ajax'),
    
    # Health Check URL
    path('health/', views.health_check_view, name='health_check'),
]
