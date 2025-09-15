from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Attendance URLs
    path('', views.AttendanceView.as_view(), name='attendance_list'),
    path('<uuid:id>/', views.AttendanceView.as_view(), name='attendance_detail'),
    path('employee/<int:employee_id>/', views.AttendanceView.as_view(), name='employee_attendance'),

    # Logs URLs
    path('logs/', views.Logs.as_view(), name='logs_list'),
    path('logs/<uuid:id>/', views.Logs.as_view(), name='log_detail'),
    
    # Dashboard URLs
    path('dashboard/', views.Dashboard.as_view(), name='dashboard'),
    path('reports/', views.Dashboard.as_view(), name='reports'),
    path('reports/<uuid:report_id>/', views.Dashboard.as_view(), name='report_detail'),
    path('summaries/', views.Dashboard.as_view(), name='summaries'),
    path('summaries/<uuid:summary_id>/', views.Dashboard.as_view(), name='summary_detail'),
    
    # Devices URLs
    path('devices/', views.Devices.as_view(), name='device_list'),
    path('devices/<uuid:id>/', views.Devices.as_view(), name='device_detail'),
    
    # Corrections URLs
    path('corrections/', views.Corrections.as_view(), name='correction_list'),
    path('corrections/<uuid:id>/', views.Corrections.as_view(), name='correction_detail'),
    
    # Holidays URLs
    path('holidays/', views.Holidays.as_view(), name='holiday_list'),
    path('holidays/<uuid:id>/', views.Holidays.as_view(), name='holiday_detail'),
    
    # Shifts URLs
    path('shifts/', views.Shifts.as_view(), name='shift_list'),
    path('shifts/<int:id>/', views.Shifts.as_view(), name='shift_detail'),
    path('employee_shifts/', views.Shifts.as_view(), name='employee_shift_list'),
    path('employee/<int:employee_id>/shifts/', views.Shifts.as_view(), name='employee_shifts'),
    path('employee/<int:employee_id>/shifts/<int:id>/', views.Shifts.as_view(), name='employee_shift_detail'),
    
    # Leave URLs
    path('leave/', views.Leave.as_view(), name='leave_request_list'),
    path('leave/<uuid:request_id>/', views.Leave.as_view(), name='leave_request_detail'),  # UUID for LeaveRequest
    path('leave/types/', views.Leave.as_view(), name='leave_type_list'),
    path('leave/types/<int:type_id>/', views.Leave.as_view(), name='leave_type_detail'),  # Integer for LeaveType
    path('leave/balances/', views.Leave.as_view(), name='leave_balance_list'),
    path('leave/balances/<int:balance_id>/', views.Leave.as_view(), name='leave_balance_detail'),  # Integer for LeaveBalance
    path('employee/<int:employee_id>/leave/', views.Leave.as_view(), name='employee_leave_requests'),
    path('employee/<int:employee_id>/leave/balances/', views.Leave.as_view(), name='employee_leave_balances'),
    
    path('import/', views.AttendanceImportView.as_view(), name='import'),
    path('import/progress/<uuid:job_id>/', views.CheckImportProgressView.as_view(), name='check_import_progress'),
    path('import/cancel/<uuid:job_id>/', views.CancelImportView.as_view(), name='cancel_import'),
    path('import/template/download/', views.download_template, name='template_download'),
    path('import/results/<uuid:job_id>/', views.AttendanceImportResultsView.as_view(), name='import_results'),
]
