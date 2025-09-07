from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from django.core.exceptions import ValidationError
from accounts.models import CustomUser, Department, ActiveManager
from employees.models import EmployeeProfile

from .utils import (
    Category,
    EmployeeExpenseType,
    OperationalExpenseType,
    PaymentMethod,
    ExpensePeriod,
    ExpenseStatus,
    PaymentStatus,
    PayrollEffect,
    PayrollStatus,
    ExpensePriority,
    ReturnStatus,
    generate_expense_reference,
    validate_expense_amount,
    validate_expense_dates,
)


class ExpenseManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ExpenseCategory(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    is_employee_expense = models.BooleanField(default=False)
    is_operational_expense = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expense_categories",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])
    
    def get_category_enum(self):
        """Map database category to enum value"""
        if self.is_employee_expense:
            return Category.EMPLOYEE
        elif self.is_operational_expense:
            return Category.OPERATIONAL
        return None

class ExpenseType(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.CASCADE, related_name="expense_types"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    requires_receipt = models.BooleanField(default=True)
    is_taxable_benefit = models.BooleanField(default=False)
    is_reimbursable = models.BooleanField(default=True)
    is_purchase_return = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expense_types",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_types"
        ordering = ["category", "name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["code"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["category", "name"]]

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    def validate_against_enum(self):
        """Validate expense type against standard enums"""
        
        if self.category.is_employee_expense:
            try:
                EmployeeExpenseType(self.code)
                return True
            except ValueError:
                return True
        
        elif self.category.is_operational_expense:
            try:
                OperationalExpenseType(self.code)
                return True
            except ValueError:
                return True
        
        return False
    
    @classmethod
    def get_standard_types(cls, category_type=None):
        """Get all standard expense types defined in enums"""
        if category_type == Category.EMPLOYEE.value:
            return [type_enum.value for type_enum in EmployeeExpenseType]
        elif category_type == Category.OPERATIONAL.value:
            return [type_enum.value for type_enum in OperationalExpenseType]
        else:
            employee_types = [type_enum.value for type_enum in EmployeeExpenseType]
            operational_types = [type_enum.value for type_enum in OperationalExpenseType]
            return employee_types + operational_types
    

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])


class Expense(models.Model):
    id = models.AutoField(primary_key=True)
    reference = models.CharField(max_length=50, unique=True, editable=False)

    # Basic Information
    employee = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="expenses"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="department_expenses"
    )
    job_title = models.CharField(max_length=100)
    request_date = models.DateField()
    date_incurred = models.DateField()
    location = models.CharField(max_length=255)

    # Expense Details
    expense_category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="expenses"
    )
    expense_type = models.ForeignKey(
        ExpenseType, on_delete=models.PROTECT, related_name="expenses"
    )
    description = models.TextField()
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    currency = models.CharField(max_length=3, default="LKR")

    # Expense Status and Tracking
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value) for status in ExpenseStatus],
        default=ExpenseStatus.DRAFT.value,
    )
    period = models.CharField(
        max_length=10,
        choices=[(period.value, period.value) for period in ExpensePeriod],
        default=ExpensePeriod.MONTHLY.value,
    )
    priority = models.CharField(
        max_length=10,
        choices=[(priority.value, priority.value) for priority in ExpensePriority],
        default=ExpensePriority.NORMAL.value,
    )

    # Payment Information
    payment_status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value) for status in PaymentStatus],
        null=True,
        blank=True,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=[(method.value, method.value) for method in PaymentMethod],
        null=True,
        blank=True,
    )
    bank_account = models.CharField(max_length=50, null=True, blank=True)

    # Payroll Integration
    add_to_payroll = models.BooleanField(default=False)
    payroll_effect = models.CharField(
        max_length=30,
        choices=[(effect.value, effect.value) for effect in PayrollEffect],
        null=True,
        blank=True,
    )
    installment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    payroll_status = models.CharField(
        max_length=30,
        choices=[(status.value, status.value) for status in PayrollStatus],
        null=True,
        blank=True,
    )
    last_payroll_sync = models.DateTimeField(null=True, blank=True)
    last_processed_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    remaining_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    # QuickBooks Integration
    expense_account = models.CharField(max_length=50, null=True, blank=True)
    cost_center = models.CharField(max_length=50, null=True, blank=True)
    tax_category = models.CharField(max_length=50, null=True, blank=True)
    is_reimbursable = models.BooleanField(default=False)
    is_taxable_benefit = models.BooleanField(default=False)
    quickbooks_sync_status = models.CharField(max_length=20, null=True, blank=True)
    quickbooks_sync_date = models.DateTimeField(null=True, blank=True)
    quickbooks_reference = models.CharField(max_length=50, null=True, blank=True)

    # Documentation
    receipt_attached = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    # Approval Information
    approver = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="approved_expenses",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="reviewed_expenses",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="expense_approvals",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="rejected_expenses",
        null=True,
        blank=True,
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    # Disbursement Information
    disbursed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="disbursed_expenses",
        null=True,
        blank=True,
    )
    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursement_reference = models.CharField(max_length=50, null=True, blank=True)

    # System Fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ExpenseManager()

    class Meta:
        db_table = "expenses"
        ordering = ["-request_date", "-created_at"]
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["employee"]),
            models.Index(fields=["department"]),
            models.Index(fields=["expense_category"]),
            models.Index(fields=["expense_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["request_date"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["payroll_status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return (
            f"{self.reference} - {self.employee.get_full_name()} - {self.total_amount}"
        )

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_expense_reference()

        if not self.pk:
            # Set default values for new expenses
            if self.employee and self.employee.department:
                self.department = self.employee.department

            if self.employee and self.employee.job_title:
                self.job_title = self.employee.job_title

        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def get_employee_profile(self):
        try:
            return EmployeeProfile.objects.get(user=self.employee)
        except EmployeeProfile.DoesNotExist:
            return None

    def update_status(self, new_status, user=None, reason=None):
        from .utils import is_valid_status_transition, get_payroll_status_for_expense

        if not is_valid_status_transition(self.status, new_status):
            return (
                False,
                f"Invalid status transition from {self.status} to {new_status}",
            )

        old_status = self.status
        self.status = new_status

        if new_status == ExpenseStatus.UNDER_REVIEW.value:
            self.reviewed_by = user
            self.reviewed_at = timezone.now()

        elif new_status == ExpenseStatus.APPROVED.value:
            self.approved_by = user
            self.approved_at = timezone.now()

            # Update payroll status if applicable
            payroll_status = get_payroll_status_for_expense(
                self.status, self.payment_status, self.payroll_effect
            )
            if payroll_status:
                self.payroll_status = payroll_status

        elif new_status == ExpenseStatus.REJECTED.value:
            self.rejected_by = user
            self.rejected_at = timezone.now()
            self.rejection_reason = reason

        elif new_status == ExpenseStatus.DISBURSED.value:
            self.disbursed_by = user
            self.disbursed_at = timezone.now()

        self.save()
        return True, f"Status updated from {old_status} to {new_status}"

    def get_bank_account(self):
        if self.bank_account:
            return self.bank_account

        profile = self.get_employee_profile()
        if profile and profile.bank_account_number:
            return profile.bank_account_number

        return None

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        
        valid_amount, amount_msg = validate_expense_amount(self.total_amount)
        if not valid_amount:
            raise ValidationError({'total_amount': amount_msg})
        
        if self.request_date and self.date_incurred:
            valid_dates, dates_msg = validate_expense_dates(self.request_date, self.date_incurred)
            if not valid_dates:
                raise ValidationError({'date_incurred': dates_msg})

class ExpenseDocument(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=50)
    file = models.FileField(upload_to="expenses/documents/%Y/%m/")
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # Size in KB
    file_type = models.CharField(max_length=100)
    upload_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    is_receipt = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_expense_documents",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_documents"
        ordering = ["-upload_date"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["document_type"]),
            models.Index(fields=["is_receipt"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.document_type} - {self.file_name}"

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])


class PurchaseItem(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="purchase_items"
    )
    item_description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    category = models.CharField(max_length=100, null=True, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_purchase_items",
    )
    return_status = models.CharField(
        max_length=20,
        choices=[(status.value, status.value) for status in ReturnStatus],
        default=ReturnStatus.NOT_RETURNABLE.value,
    )
    return_date = models.DateField(null=True, blank=True)
    return_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    refund_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    return_receipt = models.ForeignKey(
        ExpenseDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="returned_items",
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_items",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "purchase_items"
        ordering = ["expense", "id"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["return_status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.item_description} - {self.total_cost}"

    def save(self, *args, **kwargs):
        if not self.total_cost:
            self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def process_return(
        self, return_quantity, refund_amount, return_date=None, return_receipt=None
    ):
        if return_quantity > self.quantity:
            return False, "Return quantity cannot exceed original quantity"

        if refund_amount > self.total_cost:
            return False, "Refund amount cannot exceed original cost"

        self.return_status = ReturnStatus.RETURNED.value
        self.return_quantity = return_quantity
        self.refund_amount = refund_amount
        self.return_date = return_date or timezone.now().date()
        self.return_receipt = return_receipt
        self.save()

        # Update the expense total amount
        expense = self.expense
        expense.total_amount = expense.total_amount - refund_amount
        expense.save(update_fields=["total_amount"])

        return True, "Return processed successfully"


class PurchaseSummary(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.OneToOneField(
        Expense, on_delete=models.CASCADE, related_name="purchase_summary"
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    tax_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    vendor_name = models.CharField(max_length=255, null=True, blank=True)
    purchase_location = models.CharField(max_length=255, null=True, blank=True)
    purchase_reference = models.CharField(max_length=100, null=True, blank=True)
    reimbursement_status = models.CharField(max_length=50, null=True, blank=True)
    total_returned = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_summaries",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "purchase_summaries"
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.total_amount}"

    def update_totals(self):
        items = self.expense.purchase_items.filter(is_active=True)
        self.subtotal = sum(item.total_cost for item in items)
        self.total_amount = self.subtotal + self.tax_amount
        self.total_returned = sum(
            item.refund_amount
            for item in items
            if item.return_status == ReturnStatus.RETURNED.value
        )
        self.save(update_fields=["subtotal", "total_amount", "total_returned"])

        self.expense.total_amount = self.total_amount - self.total_returned
        self.expense.save(update_fields=["total_amount"])

class ExpenseAuditTrail(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="audit_trail"
    )
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_audit_actions",
    )
    previous_state = models.JSONField(null=True, blank=True)
    current_state = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "expense_audit_trail"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["action"]),
            models.Index(fields=["timestamp"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.action} - {self.timestamp}"

    def save(self, *args, **kwargs):
        if self.previous_state:
            self.previous_state = self._convert_decimals(self.previous_state)
        if self.current_state:
            self.current_state = self._convert_decimals(self.current_state)
        super().save(*args, **kwargs)

    def _convert_decimals(self, data):
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, dict):
            return {k: self._convert_decimals(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_decimals(i) for i in data]
        return data


class ExpenseApprovalWorkflow(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="approval_workflow"
    )
    current_step = models.PositiveIntegerField(default=1)
    total_steps = models.PositiveIntegerField(default=5)
    current_approver = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_expense_approvals",
    )
    next_approver = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upcoming_expense_approvals",
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_approval_workflows",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_approval_workflows"
        ordering = ["expense", "current_step"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["current_approver"]),
            models.Index(fields=["is_completed"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - Step {self.current_step}/{self.total_steps}"

    def advance_to_next_step(self, approved_by):
        if self.is_completed:
            return False, "Workflow already completed"

        current_step = self.steps.get(step_number=self.current_step)
        current_step.complete_step()

        if self.current_step >= self.total_steps:
            self.is_completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=["is_completed", "completed_at"])

            self.expense.update_status(ExpenseStatus.APPROVED.value, approved_by)
            return True, "Workflow completed, expense approved"

        self.current_step += 1

        step_names = ["Employee Request", "Admin/HR Entry", "Review", "Approval", "Disbursement"]
        expense_statuses = [
            ExpenseStatus.SUBMITTED.value,
            ExpenseStatus.PROCESSING.value,
            ExpenseStatus.UNDER_REVIEW.value,
            ExpenseStatus.APPROVED.value,
            ExpenseStatus.DISBURSED.value
        ]

        if self.current_step <= len(expense_statuses):
            self.expense.update_status(expense_statuses[self.current_step-1], approved_by)

        current_step_approver = self.get_approver_for_step(self.current_step)
        next_step_approver = (
            self.get_approver_for_step(self.current_step + 1)
            if self.current_step < self.total_steps
            else None
        )

        self.current_approver = current_step_approver
        self.next_approver = next_step_approver
        self.save(update_fields=["current_step", "current_approver", "next_approver"])

        return True, f"Advanced to step {self.current_step}/{self.total_steps}"

    def get_approver_for_step(self, step):
        try:
            step_config = ExpenseApprovalStep.objects.get(
                workflow=self, step_number=step, is_active=True
            )
            return step_config.approver
        except ExpenseApprovalStep.DoesNotExist:
            return self.expense.employee.manager

    def get_current_step_name(self):
        step_names = ["Employee Request", "Admin/HR Entry", "Review", "Approval", "Disbursement"]
        if 1 <= self.current_step <= len(step_names):
            return step_names[self.current_step-1]
        return f"Step {self.current_step}"


class ExpenseApprovalStep(models.Model):
    id = models.AutoField(primary_key=True)
    workflow = models.ForeignKey(
        ExpenseApprovalWorkflow, on_delete=models.CASCADE, related_name="steps"
    )
    step_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    approver = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="approval_steps"
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_approval_steps",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_approval_steps"
        ordering = ["workflow", "step_number"]
        indexes = [
            models.Index(fields=["workflow"]),
            models.Index(fields=["step_number"]),
            models.Index(fields=["approver"]),
            models.Index(fields=["is_completed"]),
            models.Index(fields=["is_active"]),
        ]
        unique_together = [["workflow", "step_number"]]

    def __str__(self):
        return f"{self.workflow.expense.reference} - {self.name} - {self.approver.get_full_name()}"

    def complete_step(self, notes=None):
        if self.is_completed:
            return False, "Step already completed"

        self.is_completed = True
        self.completed_at = timezone.now()
        if notes:
            self.notes = notes
        self.save(update_fields=["is_completed", "completed_at", "notes"])

        return True, "Step completed successfully"


class ExpenseDeductionThreshold(models.Model):
    id = models.AutoField(primary_key=True)
    default_threshold_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("5000.00")
    )
    minimum_salary_protection_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
        default=Decimal("70.00"),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_deduction_thresholds",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_deduction_thresholds"
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"Default Threshold: {self.default_threshold_amount}, Protection: {self.minimum_salary_protection_percent}%"

    @classmethod
    def get_current_threshold(cls):
        try:
            return cls.active.latest("created_at")
        except cls.DoesNotExist:
            return cls.objects.create(
                default_threshold_amount=Decimal("5000.00"),
                minimum_salary_protection_percent=Decimal("70.00"),
            )


class EmployeeDeductionThreshold(models.Model):
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="expense_deduction_thresholds",
    )
    threshold_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    minimum_salary_protection_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
        null=True,
        blank=True,
    )
    reason = models.TextField(blank=True, null=True)
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_employee_thresholds",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "employee_deduction_thresholds"
        ordering = ["employee", "-effective_from"]
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["effective_from"]),
            models.Index(fields=["effective_to"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.threshold_amount}"

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    @classmethod
    def get_employee_threshold(cls, employee, date=None):
        if date is None:
            date = timezone.now().date()

        try:
            return (
                cls.active.filter(employee=employee, effective_from__lte=date)
                .filter(
                    models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=date)
                )
                .latest("effective_from")
            )
        except cls.DoesNotExist:
            # Return the global default if no employee-specific threshold exists
            global_threshold = ExpenseDeductionThreshold.get_current_threshold()
            return {
                "threshold_amount": global_threshold.default_threshold_amount,
                "minimum_salary_protection_percent": global_threshold.minimum_salary_protection_percent,
            }


class PayrollExpenseIntegration(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="payroll_integrations"
    )
    payroll_period = models.CharField(max_length=20)
    payroll_date = models.DateField()
    processed_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    remaining_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    operation = models.CharField(max_length=20)  # ADD or DEDUCT
    status = models.CharField(max_length=20)
    payroll_reference = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payroll_integrations",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "payroll_expense_integrations"
        ordering = ["-payroll_date", "-created_at"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["payroll_period"]),
            models.Index(fields=["payroll_date"]),
            models.Index(fields=["operation"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.operation} - {self.processed_amount}"

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])


class ExpenseInstallmentPlan(models.Model):
    id = models.AutoField(primary_key=True)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="installment_plans"
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    installment_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    number_of_installments = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_installment_plans",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_installment_plans"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expense"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.expense.reference} - {self.installment_amount} x {self.number_of_installments}"

    def save(self, *args, **kwargs):
        if not self.number_of_installments:
            self.number_of_installments = (
                self.total_amount / self.installment_amount
            ).quantize(Decimal("1"), rounding="ROUND_UP")

        if not self.end_date:
            from .utils import calculate_estimated_payoff_date

            self.end_date = calculate_estimated_payoff_date(
                self.total_amount, self.installment_amount, self.start_date
            )

        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])


class ExpenseInstallment(models.Model):
    id = models.AutoField(primary_key=True)
    plan = models.ForeignKey(
        ExpenseInstallmentPlan, on_delete=models.CASCADE, related_name="installments"
    )
    installment_number = models.PositiveIntegerField()
    scheduled_date = models.DateField()
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    remaining_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    is_processed = models.BooleanField(default=False)
    processed_date = models.DateField(null=True, blank=True)
    payroll_integration = models.ForeignKey(
        PayrollExpenseIntegration,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="installments",
    )
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        db_table = "expense_installments"
        ordering = ["plan", "installment_number"]
        indexes = [
            models.Index(fields=["plan"]),
            models.Index(fields=["scheduled_date"]),
            models.Index(fields=["is_processed"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.plan.expense.reference} - Installment {self.installment_number} - {self.amount}"

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])
