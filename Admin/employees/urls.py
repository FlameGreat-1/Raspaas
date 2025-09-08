from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard_alt'),
    path('system-stats/', views.system_statistics_view, name='system_statistics'),
    
    # Employee Management URLs
    path('employees/search/', views.advanced_search_view, name='advanced_search'),
    path('employees/hierarchy/', views.employee_hierarchy_view, name='employee_hierarchy'),
    
    # Employee Export URLs
    path('employees/export/csv/', views.export_employees_csv, name='export_employees_csv'),
    path('employees/export/excel/', views.export_employees_excel, name='export_employees_excel'),
    
    # Bulk Employee Operations URLs
    path('employees/bulk-upload/', views.BulkEmployeeUploadView.as_view(), name='bulk_employee_upload'),
    path('employees/bulk-salary-update/', views.bulk_salary_update, name='bulk_salary_update'),
    path('employees/bulk-confirm/', views.bulk_confirm_employees, name='bulk_confirm_employees'),
    path('employees/bulk-deactivate/', views.bulk_deactivate_employees, name='bulk_deactivate_employees'),
    
    # Department Management URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.department_delete_view, name='department_delete'),
    path('departments/export/', views.department_export_view, name='department_export'),
    
    # Role Management URLs
    path('roles/', views.RoleListView.as_view(), name='role_list'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    
    # Contract Management URLs
    path('contracts/', views.ContractListView.as_view(), name='contract_list'),
    path('contracts/create/', views.ContractCreateView.as_view(), name='contract_create'),
    path('contracts/<uuid:pk>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('contracts/<uuid:pk>/edit/', views.ContractUpdateView.as_view(), name='contract_update'),
    path('contracts/<uuid:pk>/renew/', views.ContractRenewalView.as_view(), name='contract_renewal'),
    path('contracts/<uuid:pk>/activate/', views.activate_contract, name='activate_contract'),
    path('contracts/<uuid:pk>/terminate/', views.terminate_contract, name='terminate_contract'),
    
    # Contract Export URLs
    path('contracts/export/csv/', views.export_contracts_csv, name='export_contracts_csv'),
    
    # Education Management URLs
    path('education/', views.EducationListView.as_view(), name='education_list'),
    path('education/create/', views.EducationCreateView.as_view(), name='education_create'),
    path('education/create/<int:employee_id>/', views.EducationCreateView.as_view(), name='education_create_for_employee'),
    path('education/<int:pk>/', views.EducationDetailView.as_view(), name='education_detail'),
    path('education/<int:pk>/edit/', views.EducationUpdateView.as_view(), name='education_update'),
    path('education/<int:pk>/verify/', views.verify_education, name='verify_education'),
    
    # Notification URLs
    path('bulk-notification/', views.bulk_notification_view, name='bulk_notification'),
    
    # Session Management URLs
    path('sessions/', views.user_sessions_view, name='user_sessions'),
    path('sessions/management/', views.session_management_view, name='session_management'),
    path('activity-log/', views.user_activity_log_view, name='user_activity_log'),
    path('audit-logs/', views.audit_log_view, name='audit_logs'),
    
    # Report URLs
    path('reports/probation/', views.probation_report_view, name='probation_report'),
    path('reports/contract-expiry/', views.contract_expiry_report_view, name='contract_expiry_report'),
    path('reports/salary-analysis/', views.salary_analysis_report_view, name='salary_analysis_report'),
    
    # AJAX & API URLs
    path('ajax/dashboard-widgets/', views.dashboard_widgets_ajax, name='dashboard_widgets_ajax'),
    path('ajax/quick-stats/', views.quick_stats_ajax, name='quick_stats_ajax'),
    path('ajax/employee-autocomplete/', views.employee_autocomplete_ajax, name='employee_autocomplete_ajax'),
    path('ajax/validate-employee-code/', views.validate_employee_code_ajax, name='validate_employee_code_ajax'),
    path('ajax/validate-email/', views.validate_email_ajax, name='validate_email_ajax'),
    
    path('calendar/', views.employee_calendar, name='employee_calendar'),
    
    # Health Check URL
    path('health/', views.health_check_view, name='health_check'),
]
