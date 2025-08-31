from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import calendar

from .models import (
    PayrollPeriod,
    Payslip,
    SalaryAdvance,
    PayrollBankTransfer,
    PayslipItem,
)
from accounts.models import CustomUser, Department, Role, SystemConfiguration
from employees.models import EmployeeProfile
from attendance.models import MonthlyAttendanceSummary


class PayrollPeriodForm(forms.ModelForm):
    year = forms.TypedChoiceField(
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        year_choices = [(y, str(y)) for y in range(current_year - 2, current_year + 2)]
        self.fields["year"].choices = year_choices

    class Meta:
        model = PayrollPeriod
        fields = [
            "year",
            "month",
            "start_date",
            "end_date",
            "processing_date",
            "cutoff_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "processing_date": forms.DateInput(attrs={"type": "date"}),
            "cutoff_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_year(self):
        year = self.cleaned_data.get("year")
        if isinstance(year, str):
            year = year.replace(",", "")
        try:
            return int(year) if year else None
        except (ValueError, TypeError):
            raise forms.ValidationError("Please enter a valid year")

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("year")
        month = cleaned_data.get("month")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        processing_date = cleaned_data.get("processing_date")
        cutoff_date = cleaned_data.get("cutoff_date")

        if year and month:
            if PayrollPeriod.objects.filter(year=year, month=month).exists():
                if not self.instance.pk or (
                    self.instance.year != year or self.instance.month != month
                ):
                    raise ValidationError(
                        f"Payroll period for {calendar.month_name[month]} {year} already exists."
                    )

        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")
        
        if processing_date and start_date and processing_date < start_date:
            raise ValidationError("Processing date cannot be before period start date.")

        if start_date and start_date.month != month:
            raise ValidationError("Start date month must match selected month.")

        if end_date and end_date.month != month:
            raise ValidationError("End date month must match selected month.")

        return cleaned_data

class PayslipCalculationForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=CustomUser.active.filter(status="ACTIVE")
    )
    payroll_period = forms.ModelChoiceField(
        queryset=PayrollPeriod.objects.filter(status__in=["DRAFT", "PROCESSING"])
    )

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get("employee")
        payroll_period = cleaned_data.get("payroll_period")

        if employee and payroll_period:
            if Payslip.objects.filter(
                employee=employee, payroll_period=payroll_period
            ).exists():
                raise ValidationError(
                    "Payslip already exists for this employee in this period."
                )

        return cleaned_data


class BulkPayslipCalculationForm(forms.Form):
    payroll_period = forms.ModelChoiceField(
        queryset=PayrollPeriod.objects.filter(status__in=["DRAFT", "PROCESSING"]),
        label="Payroll Period",
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        label="Department (Optional)",
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        label="Role (Optional)",
    )


class SalaryAdvanceForm(forms.ModelForm):
    class Meta:
        model = SalaryAdvance
        fields = [
            "employee",
            "advance_type",
            "amount",
            "installments",
            "reason",
            "purpose_details",
        ]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
            "purpose_details": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get("employee")
        amount = cleaned_data.get("amount")
        installments = cleaned_data.get("installments")

        if employee and amount:
            from .utils import PayrollAdvanceCalculator

            advance_data = PayrollAdvanceCalculator.calculate_available_advance_amount(
                employee
            )

            if amount > advance_data["available_amount"]:
                raise ValidationError(
                    f"Amount exceeds available limit of LKR {advance_data['available_amount']}"
                )

            max_advances_per_year = SystemConfiguration.get_int_setting(
                "MAX_ADVANCES_PER_YEAR", 10
            )
            if advance_data["advance_count_this_year"] >= max_advances_per_year:
                raise ValidationError(
                    f"Maximum {max_advances_per_year} advances per year exceeded"
                )

            if installments < 1:
                raise ValidationError("Installments must be at least 1")

            max_installments = SystemConfiguration.get_int_setting(
                "MAX_ADVANCE_INSTALLMENTS", 12
            )
            if installments > max_installments:
                raise ValidationError(
                    f"Maximum installments allowed is {max_installments}"
                )

            min_installment_amount = SystemConfiguration.get_decimal_setting(
                "MIN_ADVANCE_INSTALLMENT_AMOUNT", Decimal("100.00")
            )
            installment_amount = amount / installments
            if installment_amount < min_installment_amount:
                raise ValidationError(
                    f"Installment amount (LKR {installment_amount}) is below minimum (LKR {min_installment_amount})"
                )

        return cleaned_data


class BulkSalaryAdvanceApproveForm(forms.Form):
    advance_ids = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple, label="Select Advances to Approve"
    )

    def __init__(self, *args, **kwargs):
        pending_advances = kwargs.pop("pending_advances", None)
        super().__init__(*args, **kwargs)

        if pending_advances:
            self.fields["advance_ids"].choices = [
                (
                    advance.id,
                    f"{advance.employee.get_full_name()} - LKR {advance.amount} ({advance.reference_number})",
                )
                for advance in pending_advances
            ]


class PayrollBankTransferForm(forms.ModelForm):
    class Meta:
        model = PayrollBankTransfer
        fields = ["payroll_period", "bank_file_format"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payroll_period"].queryset = PayrollPeriod.objects.filter(
            status="APPROVED"
        ).exclude(
            id__in=PayrollBankTransfer.objects.filter(
                status__in=["PENDING", "GENERATED", "SENT", "PROCESSED"]
            ).values_list("payroll_period_id", flat=True)
        )

        self.fields["bank_file_format"].initial = SystemConfiguration.get_setting(
            "BANK_FILE_FORMAT", "CSV"
        )
        self.fields["bank_file_format"].widget = forms.Select(
            choices=[("CSV", "CSV"), ("XML", "XML")]
        )

    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get("payroll_period")

        if period:
            approved_payslips = Payslip.objects.filter(
                payroll_period=period, status="APPROVED", net_salary__gt=0
            )

            if not approved_payslips.exists():
                raise ValidationError(
                    "No approved payslips with positive net salary found for this period."
                )

        return cleaned_data


class SystemConfigurationForm(forms.Form):
    setting_key = forms.CharField(max_length=100, label="Setting Key")
    setting_value = forms.CharField(max_length=255, label="Setting Value")
    setting_type = forms.ChoiceField(
        choices=[
            ("TEXT", "Text"),
            ("DECIMAL", "Decimal"),
            ("INTEGER", "Integer"),
            ("BOOLEAN", "Boolean"),
        ],
        label="Setting Type",
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Description"
    )

    def clean(self):
        cleaned_data = super().clean()
        key = cleaned_data.get("setting_key")
        value = cleaned_data.get("setting_value")
        setting_type = cleaned_data.get("setting_type")

        if key and SystemConfiguration.objects.filter(key=key).exists():
            raise ValidationError(f"Setting with key '{key}' already exists.")

        if setting_type == "DECIMAL":
            try:
                Decimal(value)
            except:
                raise ValidationError("Value must be a valid decimal number.")
        elif setting_type == "INTEGER":
            try:
                int(value)
            except:
                raise ValidationError("Value must be a valid integer.")
        elif setting_type == "BOOLEAN":
            if value.lower() not in ["true", "false", "0", "1", "yes", "no"]:
                raise ValidationError(
                    "Value must be a valid boolean (true/false, yes/no, 1/0)."
                )

        return cleaned_data


class PayrollReportForm(forms.Form):
    period = forms.ModelChoiceField(
        queryset=PayrollPeriod.objects.filter(
            status__in=["COMPLETED", "APPROVED", "PAID"]
        ).order_by("-year", "-month"),
        required=False,
        label="Payroll Period",
    )
    year = forms.ChoiceField(required=False, label="Year")
    month = forms.ChoiceField(required=False, label="Month")
    employee = forms.ModelChoiceField(
        queryset=CustomUser.active.filter(status="ACTIVE").order_by(
            "first_name", "last_name"
        ),
        required=False,
        label="Employee",
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        label="Department",
    )

    def __init__(self, *args, **kwargs):
        report_type = kwargs.pop("report_type", None)
        super().__init__(*args, **kwargs)

        current_year = timezone.now().year
        years = [(str(y), str(y)) for y in range(current_year - 5, current_year + 1)]
        months = [(str(m), calendar.month_name[m]) for m in range(1, 13)]

        self.fields["year"].choices = [("", "-- Select Year --")] + years
        self.fields["month"].choices = [("", "-- Select Month --")] + months

        if report_type == "department_summary":
            self.fields.pop("year")
            self.fields.pop("month")
            self.fields.pop("employee")
            self.fields["period"].required = True
        elif report_type == "tax_report":
            self.fields.pop("period")
            self.fields.pop("month")
            self.fields.pop("employee")
            self.fields.pop("department")
            self.fields["year"].required = True
        elif report_type == "ytd_report":
            self.fields.pop("period")
            self.fields.pop("month")
            self.fields.pop("department")
            self.fields["year"].required = True
            self.fields["employee"].required = True
        elif report_type == "comparison_report":
            self.fields.pop("year")
            self.fields.pop("month")
            self.fields.pop("employee")
            self.fields.pop("department")
            self.fields["period"].required = False
            self.fields["period1"] = forms.ModelChoiceField(
                queryset=PayrollPeriod.objects.filter(
                    status__in=["COMPLETED", "APPROVED", "PAID"]
                ).order_by("-year", "-month"),
                required=True,
                label="First Period",
            )
            self.fields["period2"] = forms.ModelChoiceField(
                queryset=PayrollPeriod.objects.filter(
                    status__in=["COMPLETED", "APPROVED", "PAID"]
                ).order_by("-year", "-month"),
                required=True,
                label="Second Period",
            )
