from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from payroll.models import PayrollPeriod, Payslip
from expenses.models import Expense
from accounting.models import SyncConfiguration, SyncLog
from accounting.tasks import sync_new_payroll_period, sync_new_expense


@receiver(post_save, sender=PayrollPeriod)
def handle_payroll_period_save(sender, instance, created, **kwargs):
    config = SyncConfiguration.get_active_config()

    if not config.realtime_sync_enabled or not config.payroll_sync_enabled:
        return

    if instance.status in ["COMPLETED", "APPROVED", "PAID"]:
        sync_log = SyncLog.objects.create(
            sync_type="PAYROLL_PERIOD",
            source_id=str(instance.id),
            source_reference=instance.period_name,
            status="PENDING",
        )

        sync_new_payroll_period.delay(str(instance.id))


@receiver(post_save, sender=Expense)
def handle_expense_save(sender, instance, created, **kwargs):
    config = SyncConfiguration.get_active_config()

    if not config.realtime_sync_enabled or not config.expense_sync_enabled:
        return

    if instance.status == "APPROVED" and instance.is_active:
        sync_log = SyncLog.objects.create(
            sync_type="EXPENSE",
            source_id=str(instance.id),
            source_reference=instance.reference,
            status="PENDING",
        )

        sync_new_expense.delay(instance.id)


@receiver(post_save, sender=Payslip)
def handle_payslip_save(sender, instance, created, **kwargs):
    config = SyncConfiguration.get_active_config()

    if not config.realtime_sync_enabled or not config.payroll_sync_enabled:
        return

    if instance.status == "APPROVED":
        payroll_period = instance.payroll_period

        if payroll_period.status in ["COMPLETED", "APPROVED", "PAID"]:
            sync_log, created = SyncLog.objects.get_or_create(
                sync_type="PAYROLL_PERIOD",
                source_id=str(payroll_period.id),
                status="PENDING",
                defaults={"source_reference": payroll_period.period_name},
            )

            if created:
                sync_new_payroll_period.delay(str(payroll_period.id))


@receiver(post_save, sender=Expense)
def handle_expense_quickbooks_sync(sender, instance, created, **kwargs):
    if not created and instance.quickbooks_sync_status == "PENDING":
        config = SyncConfiguration.get_active_config()

        if not config.expense_sync_enabled:
            return

        sync_log = SyncLog.objects.create(
            sync_type="EXPENSE",
            source_id=str(instance.id),
            source_reference=instance.reference,
            status="PENDING",
        )

        sync_new_expense.delay(instance.id)


@receiver(post_save, sender=PayrollPeriod)
def handle_payroll_period_status_change(sender, instance, created, **kwargs):
    if not created:
        config = SyncConfiguration.get_active_config()

        if not config.payroll_sync_enabled:
            return

        if instance.status in ["COMPLETED", "APPROVED", "PAID"]:
            sync_log, created = SyncLog.objects.get_or_create(
                sync_type="PAYROLL_PERIOD",
                source_id=str(instance.id),
                defaults={
                    "source_reference": instance.period_name,
                    "status": "PENDING",
                },
            )

            if created or sync_log.status in ["FAILED", "PENDING"]:
                sync_new_payroll_period.delay(str(instance.id))


@receiver(post_delete, sender=Expense)
def handle_expense_delete(sender, instance, **kwargs):
    SyncLog.objects.filter(
        sync_type="EXPENSE", source_id=str(instance.id), status="PENDING"
    ).update(
        status="CANCELLED",
        error_message="Expense was deleted before sync could complete",
    )


@receiver(post_delete, sender=PayrollPeriod)
def handle_payroll_period_delete(sender, instance, **kwargs):
    SyncLog.objects.filter(
        sync_type="PAYROLL_PERIOD", source_id=str(instance.id), status="PENDING"
    ).update(
        status="CANCELLED",
        error_message="Payroll period was deleted before sync could complete",
    )
