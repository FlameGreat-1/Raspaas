from django.db import models
from django.utils import timezone
from accounts.models import CustomUser, Department, ActiveManager
from decimal import Decimal
import uuid
import json


class QuickBooksCredentials(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    refresh_token = models.TextField()
    access_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    realm_id = models.CharField(max_length=255)
    environment = models.CharField(
        max_length=20,
        default="sandbox",
        choices=[("sandbox", "Sandbox"), ("production", "Production")],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_qb_credentials",
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_quickbooks_credentials"
        verbose_name = "QuickBooks Credentials"
        verbose_name_plural = "QuickBooks Credentials"
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"QuickBooks {self.environment} - {self.realm_id}"

    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at


class AccountMapping(models.Model):
    MAPPING_TYPES = [
        ("EXPENSE_CATEGORY", "Expense Category"),
        ("EXPENSE_TYPE", "Expense Type"),
        ("DEPARTMENT", "Department"),
        ("PAYROLL_COMPONENT", "Payroll Component"),
        ("PAYROLL_DEDUCTION", "Payroll Deduction"),
        ("PAYROLL_TAX", "Payroll Tax"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mapping_type = models.CharField(max_length=50, choices=MAPPING_TYPES)
    source_id = models.CharField(max_length=255)
    source_name = models.CharField(max_length=255)
    quickbooks_account_id = models.CharField(max_length=255)
    quickbooks_account_name = models.CharField(max_length=255)
    quickbooks_account_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_account_mappings",
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_account_mappings"
        verbose_name = "Account Mapping"
        verbose_name_plural = "Account Mappings"
        indexes = [
            models.Index(fields=["mapping_type"]),
            models.Index(fields=["source_id"]),
            models.Index(fields=["quickbooks_account_id"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["mapping_type", "source_id"]]

    def __str__(self):
        return f"{self.source_name} → {self.quickbooks_account_name}"


class DepartmentMapping(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="quickbooks_mappings"
    )
    quickbooks_department_id = models.CharField(max_length=255)
    quickbooks_department_name = models.CharField(max_length=255)
    quickbooks_class_id = models.CharField(max_length=255, null=True, blank=True)
    quickbooks_class_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_department_mappings",
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_department_mappings"
        verbose_name = "Department Mapping"
        verbose_name_plural = "Department Mappings"
        indexes = [
            models.Index(fields=["department"]),
            models.Index(fields=["quickbooks_department_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.department.name} → {self.quickbooks_department_name}"


class SyncConfiguration(models.Model):
    SYNC_FREQUENCIES = [
        ("REALTIME", "Real-time"),
        ("MINUTES_15", "Every 15 minutes"),
        ("MINUTES_30", "Every 30 minutes"),
        ("HOURLY", "Hourly"),
        ("DAILY", "Daily"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_sync_enabled = models.BooleanField(default=True)
    expense_sync_enabled = models.BooleanField(default=True)
    sync_frequency = models.CharField(
        max_length=20, choices=SYNC_FREQUENCIES, default="MINUTES_15"
    )
    realtime_sync_enabled = models.BooleanField(default=True)
    scheduled_sync_enabled = models.BooleanField(default=True)
    max_retries = models.PositiveIntegerField(default=3)
    retry_delay_minutes = models.PositiveIntegerField(default=15)
    last_full_sync = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sync_configurations",
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_sync_configurations"
        verbose_name = "Sync Configuration"
        verbose_name_plural = "Sync Configurations"
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"QuickBooks Sync Configuration - {self.sync_frequency}"

    @classmethod
    def get_active_config(cls):
        try:
            return cls.active.latest("created_at")
        except cls.DoesNotExist:
            return cls.objects.create()


class SyncLog(models.Model):
    SYNC_TYPES = [
        ("PAYROLL", "Payroll"),
        ("EXPENSE", "Expense"),
        ("PAYROLL_PERIOD", "Payroll Period"),
        ("DEPARTMENT_SUMMARY", "Department Summary"),
        ("EXPENSE_CATEGORY", "Expense Category"),
        ("FULL_SYNC", "Full Sync"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("PARTIAL", "Partial Success"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_type = models.CharField(max_length=50, choices=SYNC_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    source_id = models.CharField(max_length=255, null=True, blank=True)
    source_reference = models.CharField(max_length=255, null=True, blank=True)
    quickbooks_reference = models.CharField(max_length=255, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    records_succeeded = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    error_details = models.JSONField(default=dict, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sync_logs",
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_sync_logs"
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sync_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["source_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.sync_type} - {self.status} - {self.created_at}"

    def mark_as_started(self):
        self.status = "IN_PROGRESS"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def mark_as_completed(self, records_processed, records_succeeded, records_failed=0):
        self.status = "COMPLETED" if records_failed == 0 else "PARTIAL"
        self.completed_at = timezone.now()
        self.records_processed = records_processed
        self.records_succeeded = records_succeeded
        self.records_failed = records_failed
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "records_processed",
                "records_succeeded",
                "records_failed",
            ]
        )

    def mark_as_failed(self, error_message, error_details=None):
        self.status = "FAILED"
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_details"]
        )

    def schedule_retry(self, delay_minutes=None):
        config = SyncConfiguration.get_active_config()

        if self.retry_count >= config.max_retries:
            self.mark_as_failed(
                f"Maximum retry attempts ({config.max_retries}) exceeded"
            )
            return False

        self.retry_count += 1
        delay = delay_minutes or config.retry_delay_minutes
        self.next_retry_at = timezone.now() + timezone.timedelta(minutes=delay)
        self.status = "PENDING"
        self.save(update_fields=["retry_count", "next_retry_at", "status"])
        return True


class PayrollSyncStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_period_id = models.CharField(max_length=255)
    payroll_period_name = models.CharField(max_length=255)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    is_synced = models.BooleanField(default=False)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    quickbooks_reference = models.CharField(max_length=255, null=True, blank=True)
    sync_log = models.ForeignKey(
        SyncLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_sync_statuses",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_payroll_sync_statuses"
        verbose_name = "Payroll Sync Status"
        verbose_name_plural = "Payroll Sync Statuses"
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["payroll_period_id"]),
            models.Index(fields=["year", "month"]),
            models.Index(fields=["is_synced"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["year", "month"]]

    def __str__(self):
        return f"Payroll {self.payroll_period_name} - {'Synced' if self.is_synced else 'Not Synced'}"


class ExpenseSyncStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_id = models.CharField(max_length=255)
    expense_reference = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=255)
    employee_name = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    expense_date = models.DateField()
    is_synced = models.BooleanField(default=False)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    quickbooks_reference = models.CharField(max_length=255, null=True, blank=True)
    sync_log = models.ForeignKey(
        SyncLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_sync_statuses",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "accounting_expense_sync_statuses"
        verbose_name = "Expense Sync Status"
        verbose_name_plural = "Expense Sync Statuses"
        ordering = ["-expense_date"]
        indexes = [
            models.Index(fields=["expense_id"]),
            models.Index(fields=["expense_reference"]),
            models.Index(fields=["employee_id"]),
            models.Index(fields=["expense_date"]),
            models.Index(fields=["is_synced"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"Expense {self.expense_reference} - {'Synced' if self.is_synced else 'Not Synced'}"
