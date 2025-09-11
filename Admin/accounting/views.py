from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.conf import settings

from accounting.models import (
    QuickBooksCredentials,
    AccountMapping,
    DepartmentMapping,
    SyncConfiguration,
    SyncLog,
    PayrollSyncStatus,
    ExpenseSyncStatus,
)
from accounting.services.quickbooks_connector import QuickBooksConnector
from accounting.tasks import (
    sync_payroll_period,
    sync_expense,
    full_sync,
)
from expenses.models import ExpenseCategory, ExpenseType
from accounts.models import Department

import json
from datetime import datetime, timedelta


@login_required
@permission_required("accounting.view_synclog", raise_exception=True)
def dashboard(request):
    sync_config = SyncConfiguration.get_active_config()

    recent_syncs = SyncLog.active.order_by("-created_at")[:10]

    payroll_sync_stats = {
        "total": PayrollSyncStatus.active.count(),
        "synced": PayrollSyncStatus.active.filter(is_synced=True).count(),
        "pending": PayrollSyncStatus.active.filter(is_synced=False).count(),
    }

    expense_sync_stats = {
        "total": ExpenseSyncStatus.active.count(),
        "synced": ExpenseSyncStatus.active.filter(is_synced=True).count(),
        "pending": ExpenseSyncStatus.active.filter(is_synced=False).count(),
    }

    sync_logs_by_status = (
        SyncLog.active.values("status").annotate(count=Count("id")).order_by("status")
    )

    sync_logs_by_type = (
        SyncLog.active.values("sync_type")
        .annotate(count=Count("id"))
        .order_by("sync_type")
    )

    recent_failures = SyncLog.active.filter(status="FAILED").order_by("-created_at")[:5]

    credentials_exist = QuickBooksCredentials.active.exists()

    context = {
        "sync_config": sync_config,
        "recent_syncs": recent_syncs,
        "payroll_sync_stats": payroll_sync_stats,
        "expense_sync_stats": expense_sync_stats,
        "sync_logs_by_status": sync_logs_by_status,
        "sync_logs_by_type": sync_logs_by_type,
        "recent_failures": recent_failures,
        "credentials_exist": credentials_exist,
        "last_full_sync": sync_config.last_full_sync,
    }

    return render(request, "accounting/dashboard.html", context)


@login_required
@permission_required("accounting.view_synclog", raise_exception=True)
def sync_logs(request):
    sync_type = request.GET.get("type", "")
    status = request.GET.get("status", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    logs = SyncLog.active.all().order_by("-created_at")

    if sync_type:
        logs = logs.filter(sync_type=sync_type)

    if status:
        logs = logs.filter(status=status)

    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            logs = logs.filter(created_at__date__gte=date_from)
        except ValueError:
            pass

    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            logs = logs.filter(created_at__date__lte=date_to)
        except ValueError:
            pass

    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    sync_types = SyncLog.active.values_list("sync_type", flat=True).distinct()
    statuses = SyncLog.active.values_list("status", flat=True).distinct()

    context = {
        "page_obj": page_obj,
        "sync_types": sync_types,
        "statuses": statuses,
        "sync_type": sync_type,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
    }

    return render(request, "accounting/sync_logs.html", context)


@login_required
@permission_required("accounting.view_synclog", raise_exception=True)
def sync_log_detail(request, log_id):
    log = get_object_or_404(SyncLog, id=log_id)

    related_logs = []
    if log.sync_type == "PAYROLL_PERIOD" and log.source_id:
        related_logs = (
            SyncLog.active.filter(sync_type="PAYROLL_PERIOD", source_id=log.source_id)
            .exclude(id=log.id)
            .order_by("-created_at")
        )
    elif log.sync_type == "EXPENSE" and log.source_id:
        related_logs = (
            SyncLog.active.filter(sync_type="EXPENSE", source_id=log.source_id)
            .exclude(id=log.id)
            .order_by("-created_at")
        )

    context = {
        "log": log,
        "related_logs": related_logs,
    }

    return render(request, "accounting/sync_log_detail.html", context)


@login_required
@permission_required("accounting.change_syncconfiguration", raise_exception=True)
def sync_configuration(request):
    config = SyncConfiguration.get_active_config()

    if request.method == "POST":
        config.payroll_sync_enabled = request.POST.get("payroll_sync_enabled") == "on"
        config.expense_sync_enabled = request.POST.get("expense_sync_enabled") == "on"
        config.sync_frequency = request.POST.get("sync_frequency")
        config.realtime_sync_enabled = request.POST.get("realtime_sync_enabled") == "on"
        config.scheduled_sync_enabled = (
            request.POST.get("scheduled_sync_enabled") == "on"
        )
        config.max_retries = int(request.POST.get("max_retries", 3))
        config.retry_delay_minutes = int(request.POST.get("retry_delay_minutes", 15))
        config.save()

        messages.success(request, "Sync configuration updated successfully.")
        return redirect("accounting:sync_configuration")

    context = {
        "config": config,
        "sync_frequencies": SyncConfiguration.SYNC_FREQUENCIES,
    }

    return render(request, "accounting/sync_configuration.html", context)


@login_required
@permission_required("accounting.add_quickbookscredentials", raise_exception=True)
def quickbooks_credentials(request):
    try:
        credentials = QuickBooksCredentials.active.latest("created_at")
    except QuickBooksCredentials.DoesNotExist:
        credentials = None

    if request.method == "POST":
        client_id = request.POST.get("client_id")
        client_secret = request.POST.get("client_secret")
        refresh_token = request.POST.get("refresh_token")
        realm_id = request.POST.get("realm_id")
        environment = request.POST.get("environment")

        if credentials:
            credentials.client_id = client_id
            credentials.client_secret = client_secret
            credentials.refresh_token = refresh_token
            credentials.realm_id = realm_id
            credentials.environment = environment
            credentials.token_expires_at = None
            credentials.save()
        else:
            credentials = QuickBooksCredentials.objects.create(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                realm_id=realm_id,
                environment=environment,
                created_by=request.user,
            )

        messages.success(request, "QuickBooks credentials updated successfully.")
        return redirect("accounting:quickbooks_credentials")

    context = {
        "credentials": credentials,
    }

    return render(request, "accounting/quickbooks_credentials.html", context)

@login_required
@permission_required('accounting.view_accountmapping', raise_exception=True)
def account_mappings(request):
    mapping_type = request.GET.get('type', '')
    
    mappings = AccountMapping.active.all().order_by('mapping_type', 'source_name')
    
    if mapping_type:
        mappings = mappings.filter(mapping_type=mapping_type)
    
    mapping_types = AccountMapping.MAPPING_TYPES
    
    context = {
        'mappings': mappings,
        'mapping_types': mapping_types,
        'selected_type': mapping_type,
    }
    
    return render(request, 'accounting/account_mappings.html', context)


@login_required
@permission_required('accounting.change_accountmapping', raise_exception=True)
def edit_account_mapping(request, mapping_id=None):
    if mapping_id:
        mapping = get_object_or_404(AccountMapping, id=mapping_id)
    else:
        mapping = None
    
    if request.method == 'POST':
        mapping_type = request.POST.get('mapping_type')
        source_id = request.POST.get('source_id')
        source_name = request.POST.get('source_name')
        quickbooks_account_id = request.POST.get('quickbooks_account_id')
        quickbooks_account_name = request.POST.get('quickbooks_account_name')
        quickbooks_account_type = request.POST.get('quickbooks_account_type')
        
        if mapping:
            mapping.mapping_type = mapping_type
            mapping.source_id = source_id
            mapping.source_name = source_name
            mapping.quickbooks_account_id = quickbooks_account_id
            mapping.quickbooks_account_name = quickbooks_account_name
            mapping.quickbooks_account_type = quickbooks_account_type
            mapping.save()
            messages.success(request, 'Account mapping updated successfully.')
        else:
            AccountMapping.objects.create(
                mapping_type=mapping_type,
                source_id=source_id,
                source_name=source_name,
                quickbooks_account_id=quickbooks_account_id,
                quickbooks_account_name=quickbooks_account_name,
                quickbooks_account_type=quickbooks_account_type,
                created_by=request.user
            )
            messages.success(request, 'Account mapping created successfully.')
        
        return redirect('accounting:account_mappings')
    
    mapping_types = AccountMapping.MAPPING_TYPES
    
    expense_categories = ExpenseCategory.active.all()
    expense_types = ExpenseType.active.all()
    
    try:
        connector = QuickBooksConnector()
        quickbooks_accounts = connector.get_accounts()
    except Exception as e:
        quickbooks_accounts = []
        messages.error(request, f"Error fetching QuickBooks accounts: {str(e)}")
    
    context = {
        'mapping': mapping,
        'mapping_types': mapping_types,
        'expense_categories': expense_categories,
        'expense_types': expense_types,
        'quickbooks_accounts': quickbooks_accounts,
    }
    
    return render(request, 'accounting/edit_account_mapping.html', context)


@login_required
@permission_required('accounting.delete_accountmapping', raise_exception=True)
@require_POST
def delete_account_mapping(request, mapping_id):
    mapping = get_object_or_404(AccountMapping, id=mapping_id)
    mapping.is_active = False
    mapping.save()
    
    messages.success(request, 'Account mapping deleted successfully.')
    return redirect('accounting:account_mappings')


@login_required
@permission_required('accounting.view_departmentmapping', raise_exception=True)
def department_mappings(request):
    mappings = DepartmentMapping.active.all().order_by('department__name')
    
    departments_with_mappings = DepartmentMapping.active.values_list('department_id', flat=True)
    unmapped_departments = Department.active.exclude(id__in=departments_with_mappings)
    
    context = {
        'mappings': mappings,
        'unmapped_departments': unmapped_departments,
    }
    
    return render(request, 'accounting/department_mappings.html', context)


@login_required
@permission_required('accounting.change_departmentmapping', raise_exception=True)
def edit_department_mapping(request, mapping_id=None):
    if mapping_id:
        mapping = get_object_or_404(DepartmentMapping, id=mapping_id)
    else:
        mapping = None
    
    if request.method == 'POST':
        department_id = request.POST.get('department')
        quickbooks_department_id = request.POST.get('quickbooks_department_id')
        quickbooks_department_name = request.POST.get('quickbooks_department_name')
        quickbooks_class_id = request.POST.get('quickbooks_class_id')
        quickbooks_class_name = request.POST.get('quickbooks_class_name')
        
        department = get_object_or_404(Department, id=department_id)
        
        if mapping:
            mapping.department = department
            mapping.quickbooks_department_id = quickbooks_department_id
            mapping.quickbooks_department_name = quickbooks_department_name
            mapping.quickbooks_class_id = quickbooks_class_id
            mapping.quickbooks_class_name = quickbooks_class_name
            mapping.save()
            messages.success(request, 'Department mapping updated successfully.')
        else:
            DepartmentMapping.objects.create(
                department=department,
                quickbooks_department_id=quickbooks_department_id,
                quickbooks_department_name=quickbooks_department_name,
                quickbooks_class_id=quickbooks_class_id,
                quickbooks_class_name=quickbooks_class_name,
                created_by=request.user
            )
            messages.success(request, 'Department mapping created successfully.')
        
        return redirect('accounting:department_mappings')
    
    departments = Department.active.all()
    
    try:
        connector = QuickBooksConnector()
        quickbooks_departments = connector.get_departments()
        quickbooks_classes = connector.get_classes()
    except Exception as e:
        quickbooks_departments = []
        quickbooks_classes = []
        messages.error(request, f"Error fetching QuickBooks data: {str(e)}")
    
    context = {
        'mapping': mapping,
        'departments': departments,
        'quickbooks_departments': quickbooks_departments,
        'quickbooks_classes': quickbooks_classes,
    }
    
    return render(request, 'accounting/edit_department_mapping.html', context)


@login_required
@permission_required('accounting.delete_departmentmapping', raise_exception=True)
@require_POST
def delete_department_mapping(request, mapping_id):
    mapping = get_object_or_404(DepartmentMapping, id=mapping_id)
    mapping.is_active = False
    mapping.save()
    
    messages.success(request, 'Department mapping deleted successfully.')
    return redirect('accounting:department_mappings')


@login_required
@permission_required('accounting.view_payrollsyncstatus', raise_exception=True)
def payroll_sync_status(request):
    year = request.GET.get('year', datetime.now().year)
    try:
        year = int(year)
    except ValueError:
        year = datetime.now().year
    
    sync_statuses = PayrollSyncStatus.active.filter(year=year).order_by('-year', '-month')
    
    years = PayrollSyncStatus.active.values_list('year', flat=True).distinct().order_by('-year')
    
    context = {
        'sync_statuses': sync_statuses,
        'years': years,
        'selected_year': year,
    }
    
    return render(request, 'accounting/payroll_sync_status.html', context)


@login_required
@permission_required('accounting.view_expensesyncstatus', raise_exception=True)
def expense_sync_status(request):
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    sync_statuses = ExpenseSyncStatus.active.all().order_by('-expense_date')
    
    if status:
        if status == 'synced':
            sync_statuses = sync_statuses.filter(is_synced=True)
        elif status == 'pending':
            sync_statuses = sync_statuses.filter(is_synced=False)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            sync_statuses = sync_statuses.filter(expense_date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            sync_statuses = sync_statuses.filter(expense_date__lte=date_to)
        except ValueError:
            pass
    
    paginator = Paginator(sync_statuses, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'accounting/expense_sync_status.html', context)


@login_required
@permission_required('accounting.add_synclog', raise_exception=True)
@require_POST
def trigger_sync_payroll(request, period_id):
    sync_payroll_period.delay(period_id)
    messages.success(request, 'Payroll sync triggered successfully.')
    
    redirect_url = request.POST.get('redirect_url')
    if redirect_url:
        return redirect(redirect_url)
    return redirect('accounting:payroll_sync_status')


@login_required
@permission_required('accounting.add_synclog', raise_exception=True)
@require_POST
def trigger_sync_expense(request, expense_id):
    sync_expense.delay(expense_id)
    messages.success(request, 'Expense sync triggered successfully.')
    
    redirect_url = request.POST.get('redirect_url')
    if redirect_url:
        return redirect(redirect_url)
    return redirect('accounting:expense_sync_status')


@login_required
@permission_required('accounting.add_synclog', raise_exception=True)
@require_POST
def trigger_full_sync(request):
    full_sync.delay()
    messages.success(request, 'Full sync triggered successfully.')
    return redirect('accounting:dashboard')
