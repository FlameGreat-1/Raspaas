from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView().get, name='dashboard'),
    
    # Report Views
    path('reports/department-summary/', views.DashboardView().get_department_summary_report, name='department_summary_report'),
    path('reports/tax-report/', views.DashboardView().get_tax_report, name='tax_report'),
    path('reports/year-to-date/', views.DashboardView().get_year_to_date_report, name='year_to_date_report'),
    path('reports/comparison/', views.DashboardView().get_payroll_comparison_report, name='payroll_comparison_report'),
    
    # Report Exports
    path('reports/department-summary/export-pdf/<uuid:period_id>/', views.DashboardView().export_department_summary_pdf, name='export_department_summary_pdf'),
    path('reports/department-summary/export-excel/<uuid:period_id>/', views.DashboardView().export_department_summary_excel, name='export_department_summary_excel'),
    path('reports/tax-report/export-pdf/<int:year>/<str:report_type>/', views.DashboardView().export_tax_report_pdf, name='export_tax_report_pdf'),
    path('reports/tax-report/export-excel/<int:year>/<str:report_type>/', views.DashboardView().export_tax_report_excel, name='export_tax_report_excel'),
    path('reports/year-to-date/export-pdf/<int:employee_id>/<int:year>/', views.DashboardView().export_ytd_report_pdf, name='export_ytd_report_pdf'),
    path('reports/year-to-date/export-excel/<int:employee_id>/<int:year>/', views.DashboardView().export_ytd_report_excel, name='export_ytd_report_excel'),
    path('reports/comparison/export-pdf/<uuid:period1_id>/<uuid:period2_id>/', views.DashboardView().export_comparison_report_pdf, name='export_comparison_report_pdf'),
    path('reports/comparison/export-excel/<uuid:period1_id>/<uuid:period2_id>/', views.DashboardView().export_comparison_report_excel, name='export_comparison_report_excel'),
    
    # Payroll Period Views
    path('periods/', views.PayrollPeriodViews.PayrollPeriodListView.as_view(), name='period_list'),
    path('periods/create/', views.PayrollPeriodViews.PayrollPeriodCreateView.as_view(), name='period_create'),
    path('periods/<uuid:pk>/', views.PayrollPeriodViews.PayrollPeriodDetailView.as_view(), name='period_detail'),
    path('periods/<uuid:pk>/update/', views.PayrollPeriodViews.PayrollPeriodUpdateView.as_view(), name='period_update'),
    path('periods/<uuid:pk>/process/', views.PayrollPeriodViews.PayrollPeriodProcessView.as_view(), name='period_process'),
    path('periods/<uuid:pk>/approve/', views.PayrollPeriodViews.PayrollPeriodApproveView.as_view(), name='period_approve'),
    path('periods/<uuid:pk>/complete/', views.PayrollPeriodViews.PayrollPeriodCompleteView.as_view(), name='period_complete'),
    path('periods/<uuid:pk>/cancel/', views.PayrollPeriodViews.PayrollPeriodCancelView.as_view(), name='period_cancel'),
    
    # Payslip Views
    path('payslips/', views.PayslipViews.PayslipListView.as_view(), name='payslip_list'),
    path('payslips/<uuid:pk>/', views.PayslipViews.PayslipDetailView.as_view(), name='payslip_detail'),
    path('payslips/<uuid:pk>/calculate/', views.PayslipViews.PayslipCalculateView.as_view(), name='payslip_calculate'),
    path('payslips/<uuid:pk>/approve/', views.PayslipViews.PayslipApproveView.as_view(), name='payslip_approve'),
    path('payslips/bulk-calculate/', views.PayslipViews.BulkPayslipCalculateView.as_view(), name='bulk_calculate'),
    path('payslips/bulk-approve/', views.PayslipViews.BulkPayslipApproveView.as_view(), name='bulk_approve'),
    path('payslips/employee/<uuid:employee_id>/', views.PayslipViews.EmployeePayslipHistoryView.as_view(), name='employee_payslip_history'),
    path('payslips/<uuid:pk>/print/', views.PayslipViews.PrintPayslipView.as_view(), name='print_payslip'),
    path('employee-payslip-select/', views.PayslipViews.EmployeePayslipSelectView.as_view(), name='employee_payslip_select'),

    # Salary Advance Views
    path('advances/', views.SalaryAdvanceViews.SalaryAdvanceListView.as_view(), name='advance_list'),
    path('advances/create/', views.SalaryAdvanceViews.SalaryAdvanceCreateView.as_view(), name='advance_create'),
    path('advances/<uuid:pk>/', views.SalaryAdvanceViews.SalaryAdvanceDetailView.as_view(), name='advance_detail'),
    path('advances/<uuid:pk>/approve/', views.SalaryAdvanceViews.SalaryAdvanceApproveView.as_view(), name='advance_approve'),
    path('advances/<uuid:pk>/activate/', views.SalaryAdvanceViews.SalaryAdvanceActivateView.as_view(), name='advance_activate'),
    path('advances/<uuid:pk>/cancel/', views.SalaryAdvanceViews.SalaryAdvanceCancelView.as_view(), name='advance_cancel'),
    path('advances/bulk-approve/', views.SalaryAdvanceViews.BulkSalaryAdvanceApproveView.as_view(), name='bulk_advance_approve'),
    
    # Bank Transfer Views
    path('bank-transfers/', views.BankTransferViews.BankTransferListView.as_view(), name='bank_transfer_list'),
    path('bank-transfers/create/', views.BankTransferViews.BankTransferCreateView.as_view(), name='bank_transfer_create'),
    path('bank-transfers/<uuid:pk>/', views.BankTransferViews.BankTransferDetailView.as_view(), name='bank_transfer_detail'),
    path('bank-transfers/<uuid:pk>/generate-file/', views.BankTransferViews.BankTransferGenerateFileView.as_view(), name='bank_transfer_generate_file'),
    path('bank-transfers/<uuid:pk>/mark-as-sent/', views.BankTransferViews.BankTransferMarkAsSentView.as_view(), name='bank_transfer_mark_as_sent'),
    path('bank-transfers/<uuid:pk>/mark-as-processed/', views.BankTransferViews.BankTransferMarkAsProcessedView.as_view(), name='bank_transfer_mark_as_processed'),
    path('bank-transfers/<uuid:pk>/download-file/', views.BankTransferViews.BankTransferDownloadFileView.as_view(), name='bank_transfer_download_file'),
    
    # System Configuration
    path('system-configuration/', views.PayrollSystemConfigurationView.as_view(), name='system_configuration'),
    path('system-configuration/add/', views.PayrollSystemConfigurationView().add_configuration, name='add_configuration'),
    path('system-configuration/initialize/', views.PayrollSystemConfigurationView().initialize_system, name='initialize_system'),
]
