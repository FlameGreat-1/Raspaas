from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Expense Categories
    path('categories/', views.ExpenseCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.ExpenseCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/update/', views.ExpenseCategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.ExpenseCategoryDeleteView.as_view(), name='category_delete'),
    
    # Expense Types
    path('types/', views.ExpenseTypeListView.as_view(), name='type_list'),
    path('types/create/', views.ExpenseTypeCreateView.as_view(), name='type_create'),
    path('types/<int:pk>/update/', views.ExpenseTypeUpdateView.as_view(), name='type_update'),
    path('types/<int:pk>/delete/', views.ExpenseTypeDeleteView.as_view(), name='type_delete'),

    path('api/types/', views.ExpenseTypeAPIView.as_view(), name='expense_type_api'),

    # Expenses
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('expenses/<int:pk>/update/', views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('expenses/<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    path('expenses/<int:pk>/status/', views.ExpenseStatusUpdateView.as_view(), name='expense_status_update'),
    path('expenses/<int:pk>/approval/', views.ExpenseApprovalView.as_view(), name='expense_approval'),
    path('expenses/<int:pk>/notes/', views.ExpenseNotesView.as_view(), name='expense_notes'),
    path('expenses/bulk-action/', views.ExpenseBulkActionView.as_view(), name='expense_bulk_action'),
    
    # Documents
    path('expenses/<int:pk>/documents/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='document_delete'),
    
    # Purchase Expenses
    path('purchases/create/', views.PurchaseExpenseCreateView.as_view(), name='purchase_create'),
    path('expenses/<int:pk>/items/', views.PurchaseItemsView.as_view(), name='purchase_items'),
    path('items/<int:pk>/delete/', views.PurchaseItemDeleteView.as_view(), name='purchase_item_delete'),
    path('items/<int:pk>/return/', views.PurchaseItemReturnView.as_view(), name='purchase_item_return'),
    path('expenses/<int:expense_id>/purchase-summary/', views.PurchaseSummaryView.as_view(), name='purchase_summary'),
    
    # Workflow Management
    path('workflows/<int:pk>/advance/', views.WorkflowAdvanceView.as_view(), name='workflow_advance'),
    path('workflow-steps/<int:pk>/update/', views.WorkflowStepUpdateView.as_view(), name='workflow_step_update'),
    
    # Installment Plans
    path('installment-plans/', views.AllInstallmentPlansView.as_view(), name='all_installment_plans'),
    path('installment-plans/<int:pk>/', views.InstallmentDetailView.as_view(), name='installment_detail'),
    
    # Deduction Thresholds
    path('thresholds/', views.DeductionThresholdListView.as_view(), name='threshold_list'),
    path('thresholds/create/', views.DeductionThresholdCreateView.as_view(), name='threshold_create'),
    path('employee-thresholds/create/', views.EmployeeThresholdCreateView.as_view(), name='employee_threshold_create'),
    path('employee-thresholds/<int:pk>/update/', views.EmployeeThresholdUpdateView.as_view(), name='employee_threshold_update'),
    path('employee-thresholds/<int:pk>/delete/', views.EmployeeThresholdDeleteView.as_view(), name='employee_threshold_delete'),
            
    # Batch Operations
    path('batch-approval/', views.BatchApprovalView.as_view(), name='batch_approval'),
    path('batch-disbursement/', views.BatchDisbursementView.as_view(), name='batch_disbursement'),
    path('payroll-processing/', views.PayrollProcessingView.as_view(), name='payroll_processing'),
    
    # Reporting and Export
    path('reports/', views.ExpenseReportView.as_view(), name='report'),
    path('export/', views.ExpenseExportView.as_view(), name='export'),
    
    # Search
    path('search/', views.ExpenseSearchView.as_view(), name='search'),
    
    # QuickBooks Sync
    path('expenses/<int:pk>/quickbooks-sync/', views.ExpenseQuickbooksSyncView.as_view(), name='quickbooks_sync'),
    
    # Disbursement
    path('expenses/<int:pk>/disburse/', views.ExpenseDisbursementView.as_view(), name='expense_disbursement'),
]
