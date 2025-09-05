from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from accounts.models import CustomUser, Department

from .models import (
    Expense,
    ExpenseCategory,
    ExpenseType,
    ExpenseDocument,
    PurchaseItem,
    PurchaseSummary,
    ExpenseApprovalWorkflow,
    ExpenseApprovalStep,
    ExpenseDeductionThreshold,
    EmployeeDeductionThreshold,
    PayrollExpenseIntegration,
)
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
    validate_expense_amount,
    validate_expense_dates,
)


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = [
            "name",
            "code",
            "description",
            "is_employee_expense",
            "is_operational_expense",
            "is_active",
        ]

    def clean(self):
        cleaned_data = super().clean()
        is_employee_expense = cleaned_data.get("is_employee_expense")
        is_operational_expense = cleaned_data.get("is_operational_expense")

        if not is_employee_expense and not is_operational_expense:
            raise ValidationError(
                "Category must be either an employee expense or an operational expense"
            )

        if is_employee_expense and is_operational_expense:
            raise ValidationError(
                "Category cannot be both an employee expense and an operational expense"
            )

        return cleaned_data


class ExpenseTypeForm(forms.ModelForm):
    class Meta:
        model = ExpenseType
        fields = [
            "category",
            "name",
            "code",
            "description",
            "requires_receipt",
            "is_taxable_benefit",
            "is_reimbursable",
            "is_purchase_return",
            "is_active",
        ]

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        code = cleaned_data.get("code")

        if category and code:
            if category.is_employee_expense:
                try:
                    EmployeeExpenseType(code)
                except ValueError:
                    pass
            elif category.is_operational_expense:
                try:
                    OperationalExpenseType(code)
                except ValueError:
                    pass

        return cleaned_data


class ExpenseForm(forms.ModelForm):
    request_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.now().date,
    )
    date_incurred = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.now().date,
    )

    class Meta:
        model = Expense
        fields = [
            "employee",
            "department",
            "job_title",
            "request_date",
            "date_incurred",
            "location",
            "expense_category",
            "expense_type",
            "description",
            "total_amount",
            "currency",
            "status",
            "period",
            "priority",
            "payment_status",
            "payment_method",
            "bank_account",
            "add_to_payroll",
            "payroll_effect",
            "installment_amount",
            "expense_account",
            "cost_center",
            "tax_category",
            "is_reimbursable",
            "is_taxable_benefit",
            "receipt_attached",
            "notes",
            "approver",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields["created_by"].initial = user

        self.fields["employee"].queryset = CustomUser.objects.filter(is_active=True)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["approver"].queryset = CustomUser.objects.filter(
            is_active=True, is_staff=True
        )

        self.fields["expense_category"].queryset = ExpenseCategory.active.all()

        if "expense_category" in self.data:
            try:
                category_id = int(self.data.get("expense_category"))
                self.fields["expense_type"].queryset = ExpenseType.active.filter(
                    category_id=category_id
                )
            except (ValueError, TypeError):
                self.fields["expense_type"].queryset = ExpenseType.active.none()
        elif self.instance.pk and self.instance.expense_category:
            self.fields["expense_type"].queryset = ExpenseType.active.filter(
                category=self.instance.expense_category
            )
        else:
            self.fields["expense_type"].queryset = ExpenseType.active.none()

        if self.instance.pk:
            if self.instance.payment_status == PaymentStatus.PAID_BY_EMPLOYEE.value:
                self.fields["payroll_effect"].initial = (
                    PayrollEffect.ADD_TO_NEXT_PAYROLL.value
                )
            elif self.instance.payment_status in [
                PaymentStatus.ADVANCE_REQUESTED.value,
                PaymentStatus.LOAN_REQUESTED.value,
            ]:
                self.fields["payroll_effect"].initial = (
                    PayrollEffect.DEDUCT_FROM_NEXT_PAYROLL.value
                )

    def clean(self):
        cleaned_data = super().clean()
        total_amount = cleaned_data.get("total_amount")
        request_date = cleaned_data.get("request_date")
        date_incurred = cleaned_data.get("date_incurred")
        payment_status = cleaned_data.get("payment_status")
        payroll_effect = cleaned_data.get("payroll_effect")
        add_to_payroll = cleaned_data.get("add_to_payroll")
        installment_amount = cleaned_data.get("installment_amount")
        expense_type = cleaned_data.get("expense_type")

        if total_amount:
            valid_amount, amount_msg = validate_expense_amount(total_amount)
            if not valid_amount:
                self.add_error("total_amount", amount_msg)

        if request_date and date_incurred:
            valid_dates, dates_msg = validate_expense_dates(request_date, date_incurred)
            if not valid_dates:
                self.add_error("date_incurred", dates_msg)

        if add_to_payroll:
            if not payment_status:
                self.add_error(
                    "payment_status",
                    "Payment status is required when adding to payroll",
                )

            if not payroll_effect:
                self.add_error(
                    "payroll_effect",
                    "Payroll effect is required when adding to payroll",
                )

            if (
                payroll_effect == PayrollEffect.DEDUCT_IN_INSTALLMENTS.value
                and not installment_amount
            ):
                self.add_error(
                    "installment_amount",
                    "Installment amount is required for installment deductions",
                )

            if (
                payroll_effect == PayrollEffect.DEDUCT_IN_INSTALLMENTS.value
                and installment_amount
                and installment_amount >= total_amount
            ):
                self.add_error(
                    "installment_amount",
                    "Installment amount must be less than the total amount",
                )

        if expense_type and expense_type.is_purchase_return:
            if not self.instance.pk:
                self.add_error(
                    "expense_type",
                    "Purchase and Return expenses must be created through the Purchase form",
                )

        return cleaned_data


class ExpenseDocumentForm(forms.ModelForm):
    class Meta:
        model = ExpenseDocument
        fields = [
            "expense",
            "document_type",
            "file",
            "description",
            "is_receipt",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)

        if expense:
            self.fields["expense"].initial = expense
            self.fields["expense"].widget = forms.HiddenInput()

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError("File size cannot exceed 10MB")

            allowed_extensions = [
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            ]
            file_extension = "." + file.name.split(".")[-1].lower()

            if file_extension not in allowed_extensions:
                raise ValidationError(
                    f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
                )

            self.instance.file_name = file.name
            self.instance.file_size = file.size // 1024  # Convert to KB
            self.instance.file_type = file.content_type

        return file


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = [
            "expense",
            "item_description",
            "quantity",
            "unit_cost",
            "total_cost",
            "category",
            "department",
            "return_status",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)

        if expense:
            self.fields["expense"].initial = expense
            self.fields["expense"].widget = forms.HiddenInput()

        self.fields["department"].queryset = Department.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        unit_cost = cleaned_data.get("unit_cost")
        total_cost = cleaned_data.get("total_cost")

        if quantity and unit_cost:
            calculated_total = quantity * unit_cost
            if total_cost and abs(calculated_total - total_cost) > Decimal("0.01"):
                self.add_error(
                    "total_cost",
                    f"Total cost should be {calculated_total} (quantity × unit cost)",
                )
            else:
                cleaned_data["total_cost"] = calculated_total

        return cleaned_data


class PurchaseItemReturnForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = [
            "return_status",
            "return_quantity",
            "refund_amount",
            "return_date",
            "notes",
        ]
        widgets = {
            "return_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["return_date"].initial = timezone.now().date
        self.fields["return_status"].initial = ReturnStatus.RETURNED.value
        self.fields["return_status"].widget = forms.HiddenInput()

        if self.instance.pk:
            self.fields["return_quantity"].initial = self.instance.quantity
            self.fields["refund_amount"].initial = self.instance.total_cost

    def clean(self):
        cleaned_data = super().clean()
        return_quantity = cleaned_data.get("return_quantity")
        refund_amount = cleaned_data.get("refund_amount")

        if return_quantity and return_quantity > self.instance.quantity:
            self.add_error(
                "return_quantity", "Return quantity cannot exceed original quantity"
            )

        if refund_amount and refund_amount > self.instance.total_cost:
            self.add_error("refund_amount", "Refund amount cannot exceed original cost")

        return cleaned_data


class PurchaseExpenseForm(forms.ModelForm):
    request_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.now().date,
    )
    date_incurred = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.now().date,
    )
    vendor_name = forms.CharField(max_length=255, required=True)
    purchase_location = forms.CharField(max_length=255, required=True)
    purchase_reference = forms.CharField(max_length=100, required=False)
    subtotal = forms.DecimalField(max_digits=12, decimal_places=2, required=True)
    tax_amount = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, initial=Decimal("0.00")
    )

    class Meta:
        model = Expense
        fields = [
            "employee",
            "department",
            "job_title",
            "request_date",
            "date_incurred",
            "location",
            "description",
            "currency",
            "status",
            "period",
            "priority",
            "payment_status",
            "payment_method",
            "bank_account",
            "add_to_payroll",
            "payroll_effect",
            "installment_amount",
            "expense_account",
            "cost_center",
            "tax_category",
            "is_reimbursable",
            "is_taxable_benefit",
            "receipt_attached",
            "notes",
            "approver",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields["created_by"].initial = user

        self.fields["employee"].queryset = CustomUser.objects.filter(is_active=True)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["approver"].queryset = CustomUser.objects.filter(
            is_active=True, is_staff=True
        )

        try:
            purchase_return_category = ExpenseCategory.active.get(
                is_employee_expense=True
            )
            purchase_return_type = ExpenseType.active.get(
                category=purchase_return_category, is_purchase_return=True
            )
            self.instance.expense_category = purchase_return_category
            self.instance.expense_type = purchase_return_type
        except (ExpenseCategory.DoesNotExist, ExpenseType.DoesNotExist):
            pass

        if self.instance.pk:
            try:
                purchase_summary = self.instance.purchase_summary
                self.fields["vendor_name"].initial = purchase_summary.vendor_name
                self.fields["purchase_location"].initial = (
                    purchase_summary.purchase_location
                )
                self.fields["purchase_reference"].initial = (
                    purchase_summary.purchase_reference
                )
                self.fields["subtotal"].initial = purchase_summary.subtotal
                self.fields["tax_amount"].initial = purchase_summary.tax_amount
            except PurchaseSummary.DoesNotExist:
                pass

    def clean(self):
        cleaned_data = super().clean()
        subtotal = cleaned_data.get("subtotal")
        tax_amount = cleaned_data.get("tax_amount", Decimal("0.00"))

        if subtotal:
            total_amount = subtotal + (tax_amount or Decimal("0.00"))
            cleaned_data["total_amount"] = total_amount

        request_date = cleaned_data.get("request_date")
        date_incurred = cleaned_data.get("date_incurred")

        if request_date and date_incurred:
            valid_dates, dates_msg = validate_expense_dates(request_date, date_incurred)
            if not valid_dates:
                self.add_error("date_incurred", dates_msg)

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        try:
            purchase_return_category = ExpenseCategory.active.get(
                is_employee_expense=True
            )
            purchase_return_type = ExpenseType.active.get(
                category=purchase_return_category, is_purchase_return=True
            )
            instance.expense_category = purchase_return_category
            instance.expense_type = purchase_return_type
        except (ExpenseCategory.DoesNotExist, ExpenseType.DoesNotExist):
            pass

        if commit:
            instance.save()

            vendor_name = self.cleaned_data.get("vendor_name")
            purchase_location = self.cleaned_data.get("purchase_location")
            purchase_reference = self.cleaned_data.get("purchase_reference")
            subtotal = self.cleaned_data.get("subtotal")
            tax_amount = self.cleaned_data.get("tax_amount", Decimal("0.00"))
            total_amount = subtotal + tax_amount

            try:
                purchase_summary = instance.purchase_summary
                purchase_summary.vendor_name = vendor_name
                purchase_summary.purchase_location = purchase_location
                purchase_summary.purchase_reference = purchase_reference
                purchase_summary.subtotal = subtotal
                purchase_summary.tax_amount = tax_amount
                purchase_summary.total_amount = total_amount
                purchase_summary.save()
            except PurchaseSummary.DoesNotExist:
                PurchaseSummary.objects.create(
                    expense=instance,
                    vendor_name=vendor_name,
                    purchase_location=purchase_location,
                    purchase_reference=purchase_reference,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                )

        return instance


class ExpenseDeductionThresholdForm(forms.ModelForm):
    class Meta:
        model = ExpenseDeductionThreshold
        fields = [
            "default_threshold_amount",
            "minimum_salary_protection_percent",
        ]


class EmployeeDeductionThresholdForm(forms.ModelForm):
    class Meta:
        model = EmployeeDeductionThreshold
        fields = [
            "employee",
            "threshold_amount",
            "minimum_salary_protection_percent",
            "reason",
            "effective_from",
            "effective_to",
        ]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = CustomUser.objects.filter(is_active=True)
        self.fields["effective_from"].initial = timezone.now().date

    def clean(self):
        cleaned_data = super().clean()
        effective_from = cleaned_data.get("effective_from")
        effective_to = cleaned_data.get("effective_to")

        if effective_from and effective_to and effective_from > effective_to:
            self.add_error(
                "effective_to", "Effective to date cannot be before effective from date"
            )

        return cleaned_data


class ExpenseStatusUpdateForm(forms.Form):
    status = forms.ChoiceField(
        choices=[(status.value, status.value) for status in ExpenseStatus]
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, **kwargs):
        expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)

        if expense:
            from .utils import get_expense_status_transition_map

            transition_map = get_expense_status_transition_map()
            allowed_transitions = transition_map.get(expense.status, [])

            self.fields["status"].choices = [
                (status, status) for status in allowed_transitions
            ]

            if expense.status == ExpenseStatus.UNDER_REVIEW.value:
                self.fields["reason"].required = True


class ExpenseFilterForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True), required=False
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True), required=False
    )
    expense_category = forms.ModelChoiceField(
        queryset=ExpenseCategory.active.all(), required=False
    )
    expense_type = forms.ModelChoiceField(
        queryset=ExpenseType.active.all(), required=False
    )
    status = forms.ChoiceField(
        choices=[("", "All")]
        + [(status.value, status.value) for status in ExpenseStatus],
        required=False,
    )
    payment_status = forms.ChoiceField(
        choices=[("", "All")]
        + [(status.value, status.value) for status in PaymentStatus],
        required=False,
    )
    payroll_status = forms.ChoiceField(
        choices=[("", "All")]
        + [(status.value, status.value) for status in PayrollStatus],
        required=False,
    )
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    amount_min = forms.DecimalField(required=False)
    amount_max = forms.DecimalField(required=False)
    reference = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "expense_category" in self.data:
            try:
                category_id = int(self.data.get("expense_category"))
                self.fields["expense_type"].queryset = ExpenseType.active.filter(
                    category_id=category_id
                )
            except (ValueError, TypeError):
                self.fields["expense_type"].queryset = ExpenseType.active.none()
        else:
            self.fields["expense_type"].queryset = ExpenseType.active.all()


class ExpenseReportForm(forms.Form):
    report_type = forms.ChoiceField(
        choices=[
            ("category", "By Category"),
            ("department", "By Department"),
            ("employee", "By Employee"),
            ("status", "By Status"),
        ]
    )
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    include_details = forms.BooleanField(required=False, initial=True)
    export_format = forms.ChoiceField(
        choices=[
            ("html", "HTML"),
            ("csv", "CSV"),
            ("excel", "Excel"),
            ("pdf", "PDF"),
        ],
        initial="html",
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")

        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date cannot be before start date")

        return cleaned_data


class ExpenseBulkActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=[
            ("", "Select Action"),
            ("approve", "Approve Selected"),
            ("reject", "Reject Selected"),
            ("delete", "Delete Selected"),
        ]
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        reason = cleaned_data.get("reason")

        if action in ["reject"] and not reason:
            self.add_error("reason", "Reason is required for rejection")

        return cleaned_data


class PayrollExpenseIntegrationForm(forms.ModelForm):
    class Meta:
        model = PayrollExpenseIntegration
        fields = [
            "expense",
            "payroll_period",
            "payroll_date",
            "processed_amount",
            "operation",
            "status",
            "payroll_reference",
            "notes",
        ]
        widgets = {
            "payroll_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)

        if expense:
            self.fields["expense"].initial = expense
            self.fields["expense"].widget = forms.HiddenInput()

            if expense.payment_status == PaymentStatus.PAID_BY_EMPLOYEE.value:
                self.fields["operation"].initial = "ADD"
            else:
                self.fields["operation"].initial = "DEDUCT"

            self.fields["processed_amount"].initial = expense.total_amount

        self.fields["payroll_date"].initial = timezone.now().date
        self.fields["status"].initial = "PENDING"


class ExpenseQuickbooksSyncForm(forms.Form):
    expense_account = forms.CharField(max_length=50, required=True)
    cost_center = forms.CharField(max_length=50, required=False)
    tax_category = forms.CharField(max_length=50, required=False)
    is_reimbursable = forms.BooleanField(required=False)
    is_taxable_benefit = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        expense = kwargs.pop("expense", None)
        super().__init__(*args, **kwargs)

        if expense:
            self.fields["expense_account"].initial = expense.expense_account
            self.fields["cost_center"].initial = expense.cost_center
            self.fields["tax_category"].initial = expense.tax_category
            self.fields["is_reimbursable"].initial = expense.is_reimbursable
            self.fields["is_taxable_benefit"].initial = expense.is_taxable_benefit

class ExpenseExportForm(forms.Form):
    export_format = forms.ChoiceField(
        choices=[
            ("csv", "CSV"),
            ("excel", "Excel"),
            ("pdf", "PDF"),
        ],
        initial="excel",
    )
    include_details = forms.BooleanField(required=False, initial=True)
    include_audit_trail = forms.BooleanField(required=False, initial=False)
    date_from = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    date_to = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")

        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date cannot be before start date")

        return cleaned_data

class ExpenseApprovalForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[
            ("approve", "Approve"),
            ("reject", "Reject"),
        ]
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get("decision")
        notes = cleaned_data.get("notes")

        if decision == "reject" and not notes:
            self.add_error("notes", "Please provide a reason for rejection")

        return cleaned_data


class ExpenseDisbursementForm(forms.Form):
    disbursement_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.now().date
    )
    disbursement_reference = forms.CharField(max_length=50, required=True)
    payment_method = forms.ChoiceField(
        choices=[(method.value, method.value) for method in PaymentMethod]
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)


class ExpenseSearchForm(forms.Form):
    search_term = forms.CharField(required=True)
    search_in = forms.MultipleChoiceField(
        choices=[
            ("reference", "Reference"),
            ("employee", "Employee Name"),
            ("description", "Description"),
            ("notes", "Notes"),
        ],
        widget=forms.CheckboxSelectMultiple,
        initial=["reference", "employee", "description"],
    )


class ExpenseBatchApprovalForm(forms.Form):
    expenses = forms.ModelMultipleChoiceField(
        queryset=Expense.active.filter(status=ExpenseStatus.UNDER_REVIEW.value),
        widget=forms.CheckboxSelectMultiple,
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)


class ExpenseBatchDisbursementForm(forms.Form):
    expenses = forms.ModelMultipleChoiceField(
        queryset=Expense.active.filter(status=ExpenseStatus.APPROVED.value),
        widget=forms.CheckboxSelectMultiple,
    )
    disbursement_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.now().date
    )
    payment_method = forms.ChoiceField(
        choices=[(method.value, method.value) for method in PaymentMethod]
    )
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

class ExpenseNotesForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=True)


class ExpenseAttachmentUploadForm(forms.Form):
    document_type = forms.CharField(max_length=50, required=True)
    file = forms.FileField(required=True)
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False
    )
    is_receipt = forms.BooleanField(required=False)

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError("File size cannot exceed 10MB")

            allowed_extensions = [
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            ]
            file_extension = "." + file.name.split(".")[-1].lower()

            if file_extension not in allowed_extensions:
                raise ValidationError(
                    f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
                )

        return file
