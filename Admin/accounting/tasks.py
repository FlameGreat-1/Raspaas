from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from accounting.models import (
    SyncConfiguration,
    SyncLog,
    PayrollSyncStatus,
    ExpenseSyncStatus,
)
from accounting.services.quickbooks_connector import QuickBooksConnector
from payroll.models import PayrollPeriod
from expenses.models import Expense


@shared_task
def sync_payroll_period(payroll_period_id):
    connector = QuickBooksConnector()
    return connector.sync_payroll_period(payroll_period_id)


@shared_task
def sync_expense(expense_id):
    connector = QuickBooksConnector()
    return connector.sync_expense(expense_id)


@shared_task
def batch_sync_expenses(expense_ids=None, status=None, date_range=None):
    connector = QuickBooksConnector()
    return connector.batch_sync_expenses(expense_ids, status, date_range)


@shared_task
def batch_sync_payroll(period_ids=None, year=None, month=None):
    connector = QuickBooksConnector()
    return connector.batch_sync_payroll(period_ids, year, month)


@shared_task
def full_sync():
    connector = QuickBooksConnector()
    return connector.full_sync()


@shared_task
def scheduled_sync():
    config = SyncConfiguration.get_active_config()

    if not config.scheduled_sync_enabled:
        return "Scheduled sync disabled in configuration"

    connector = QuickBooksConnector()

    results = {"payroll": None, "expenses": None}

    if config.payroll_sync_enabled:
        unsynced_periods = PayrollPeriod.objects.filter(
            is_active=True, status__in=["COMPLETED", "APPROVED", "PAID"]
        ).exclude(
            id__in=PayrollSyncStatus.objects.filter(is_synced=True).values_list(
                "payroll_period_id", flat=True
            )
        )

        if unsynced_periods.exists():
            success, message, _ = connector.batch_sync_payroll(
                period_ids=[str(p.id) for p in unsynced_periods]
            )
            results["payroll"] = {"success": success, "message": message}

    if config.expense_sync_enabled:
        unsynced_expenses = Expense.objects.filter(
            is_active=True, status="APPROVED"
        ).exclude(
            id__in=ExpenseSyncStatus.objects.filter(is_synced=True).values_list(
                "expense_id", flat=True
            )
        )

        if unsynced_expenses.exists():
            success, message, _ = connector.batch_sync_expenses(
                expense_ids=[e.id for e in unsynced_expenses]
            )
            results["expenses"] = {"success": success, "message": message}

    return results


@shared_task
def retry_failed_syncs():
    now = timezone.now()

    failed_logs = SyncLog.objects.filter(
        status="FAILED",
        retry_count__lt=SyncConfiguration.get_active_config().max_retries,
        next_retry_at__lte=now,
    )

    results = []

    for log in failed_logs:
        if log.sync_type == "PAYROLL_PERIOD" and log.source_id:
            success, message, _ = sync_payroll_period(log.source_id)
            results.append(
                {
                    "id": str(log.id),
                    "type": log.sync_type,
                    "success": success,
                    "message": message,
                }
            )

        elif log.sync_type == "EXPENSE" and log.source_id:
            success, message, _ = sync_expense(log.source_id)
            results.append(
                {
                    "id": str(log.id),
                    "type": log.sync_type,
                    "success": success,
                    "message": message,
                }
            )

    return results


@shared_task
def sync_new_payroll_period(payroll_period_id):
    connector = QuickBooksConnector()

    config = SyncConfiguration.get_active_config()
    if not config.payroll_sync_enabled:
        return "Payroll sync disabled in configuration"

    return connector.sync_payroll_period(payroll_period_id)


@shared_task
def sync_new_expense(expense_id):
    connector = QuickBooksConnector()

    config = SyncConfiguration.get_active_config()
    if not config.expense_sync_enabled:
        return "Expense sync disabled in configuration"

    return connector.sync_expense(expense_id)


@shared_task
def sync_pending_items():
    config = SyncConfiguration.get_active_config()

    results = {"payroll": None, "expenses": None}

    if config.payroll_sync_enabled:
        pending_payroll_syncs = SyncLog.objects.filter(
            sync_type="PAYROLL_PERIOD", status="PENDING"
        )

        for log in pending_payroll_syncs:
            if log.source_id:
                sync_payroll_period.delay(log.source_id)

        results["payroll"] = f"{pending_payroll_syncs.count()} payroll syncs queued"

    if config.expense_sync_enabled:
        pending_expense_syncs = SyncLog.objects.filter(
            sync_type="EXPENSE", status="PENDING"
        )

        for log in pending_expense_syncs:
            if log.source_id:
                sync_expense.delay(log.source_id)

        results["expenses"] = f"{pending_expense_syncs.count()} expense syncs queued"

    return results


@shared_task
def cleanup_old_sync_logs(days=30):
    cutoff_date = timezone.now() - timedelta(days=days)

    old_logs = SyncLog.objects.filter(
        created_at__lt=cutoff_date, status__in=["COMPLETED", "FAILED"]
    )

    count = old_logs.count()
    old_logs.update(is_active=False)

    return f"Cleaned up {count} old sync logs"
