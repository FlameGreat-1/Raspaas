from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sync-logs/', views.sync_logs, name='sync_logs'),
    path('sync-logs/<uuid:log_id>/', views.sync_log_detail, name='sync_log_detail'),
    path('configuration/', views.sync_configuration, name='sync_configuration'),
    path('credentials/', views.quickbooks_credentials, name='quickbooks_credentials'),
    path('account-mappings/', views.account_mappings, name='account_mappings'),
    path('account-mappings/add/', views.edit_account_mapping, name='add_account_mapping'),
    path('account-mappings/<uuid:mapping_id>/edit/', views.edit_account_mapping, name='edit_account_mapping'),
    path('account-mappings/<uuid:mapping_id>/delete/', views.delete_account_mapping, name='delete_account_mapping'),
    path('department-mappings/', views.department_mappings, name='department_mappings'),
    path('department-mappings/add/', views.edit_department_mapping, name='add_department_mapping'),
    path('department-mappings/<uuid:mapping_id>/edit/', views.edit_department_mapping, name='edit_department_mapping'),
    path('department-mappings/<uuid:mapping_id>/delete/', views.delete_department_mapping, name='delete_department_mapping'),
    path('payroll-sync-status/', views.payroll_sync_status, name='payroll_sync_status'),
    path('expense-sync-status/', views.expense_sync_status, name='expense_sync_status'),
    path('trigger-sync/payroll/<int:period_id>/', views.trigger_sync_payroll, name='trigger_sync_payroll'),
    path('trigger-sync/expense/<int:expense_id>/', views.trigger_sync_expense, name='trigger_sync_expense'),
    path('trigger-full-sync/', views.trigger_full_sync, name='trigger_full_sync'),
]
