from django.utils import timezone
from django.db.models import Sum, Q
from django.http import HttpResponse
from decimal import Decimal, ROUND_UP
import uuid
from datetime import datetime, date, timedelta
from enum import Enum
import math
import csv
import json

from accounts.models import CustomUser, Department


class Category(Enum):
    EMPLOYEE = "EMPLOYEE"
    OPERATIONAL = "OPERATIONAL"


class EmployeeExpenseType(Enum):
    MEDICAL = "MEDICAL"
    EDUCATION = "EDUCATION"
    SALARY_ADVANCE = "SALARY_ADVANCE"
    EMPLOYEE_LOAN = "EMPLOYEE_LOAN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    RELOCATION = "RELOCATION"
    ENTERTAINMENT = "ENTERTAINMENT"


class OperationalExpenseType(Enum):
    STATIONERY = "STATIONERY"
    EQUIPMENT = "EQUIPMENT"
    TRAINING = "TRAINING"
    TRAVEL = "TRAVEL"
    FUEL = "FUEL"
    SOFTWARE = "SOFTWARE"
    MAINTENANCE = "MAINTENANCE"


class PaymentMethod(Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"


class ExpensePeriod(Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class ExpenseStatus(Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISBURSED = "DISBURSED"
    CANCELLED = "CANCELLED"


class PaymentStatus(Enum):
    PAID_BY_EMPLOYEE = "PAID_BY_EMPLOYEE"
    ADVANCE_REQUESTED = "ADVANCE_REQUESTED"
    LOAN_REQUESTED = "LOAN_REQUESTED"


class PayrollEffect(Enum):
    ADD_TO_NEXT_PAYROLL = "ADD_TO_NEXT_PAYROLL"
    DEDUCT_FROM_NEXT_PAYROLL = "DEDUCT_FROM_NEXT_PAYROLL"
    DEDUCT_IN_INSTALLMENTS = "DEDUCT_IN_INSTALLMENTS"


class PayrollStatus(Enum):
    PENDING_PAYROLL_PROCESSING = "PENDING_PAYROLL_PROCESSING"
    ADDED_TO_PAYROLL = "ADDED_TO_PAYROLL"
    DEDUCTED_FROM_PAYROLL = "DEDUCTED_FROM_PAYROLL"
    PARTIALLY_PROCESSED = "PARTIALLY_PROCESSED"


class ExpensePriority(Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"


class ReturnStatus(Enum):
    NOT_RETURNABLE = "NOT_RETURNABLE"
    RETURNABLE = "RETURNABLE"
    RETURNED = "RETURNED"


def get_expense_type_choices(category=None):
    if category == Category.EMPLOYEE.value:
        return [
            (t.value, t.value.replace("_", " ").title()) for t in EmployeeExpenseType
        ]
    elif category == Category.OPERATIONAL.value:
        return [
            (t.value, t.value.replace("_", " ").title()) for t in OperationalExpenseType
        ]

    employee_types = [
        (f"EMPLOYEE_{t.value}", t.value.replace("_", " ").title())
        for t in EmployeeExpenseType
    ]
    operational_types = [
        (f"OPERATIONAL_{t.value}", t.value.replace("_", " ").title())
        for t in OperationalExpenseType
    ]
    return employee_types + operational_types


def get_expense_category_display(category_value):
    try:
        return Category(category_value).name.replace("_", " ").title()
    except ValueError:
        return category_value


def get_expense_type_display(type_value):
    try:
        if type_value.startswith("EMPLOYEE_"):
            return EmployeeExpenseType(type_value[9:]).name.replace("_", " ").title()
        elif type_value.startswith("OPERATIONAL_"):
            return (
                OperationalExpenseType(type_value[12:]).name.replace("_", " ").title()
            )

        for enum_class in [EmployeeExpenseType, OperationalExpenseType]:
            try:
                return enum_class(type_value).name.replace("_", " ").title()
            except ValueError:
                continue
        return type_value
    except (ValueError, AttributeError):
        return type_value


def generate_expense_reference():
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"EXP-{timestamp}-{random_suffix}"


def calculate_total_expense_amount(items):
    if not items:
        return Decimal("0.00")
    return sum(item.get("total_amount", Decimal("0.00")) for item in items)


def calculate_installment_details(total_amount, installment_amount, start_date=None):
    if not start_date:
        start_date = timezone.now().date()

    if not installment_amount or installment_amount <= Decimal("0.00"):
        return {
            "installments": [],
            "total_installments": 0,
            "total_amount": total_amount,
            "number_of_installments": 0,
        }

    remaining_amount = total_amount
    installments = []
    installment_number = 1
    current_date = start_date

    while remaining_amount > Decimal("0.00"):
        if remaining_amount <= installment_amount:
            amount = remaining_amount
            remaining_amount = Decimal("0.00")
        else:
            amount = installment_amount
            remaining_amount -= installment_amount

        installments.append(
            {
                "installment_number": installment_number,
                "date": current_date,
                "amount": amount,
                "remaining_balance": remaining_amount,
            }
        )

        installment_number += 1
        current_date = date(
            year=current_date.year + ((current_date.month + 1) // 13),
            month=((current_date.month + 1) % 12) or 12,
            day=min(current_date.day, 28),
        )

    return {
        "installments": installments,
        "total_installments": len(installments),
        "total_amount": total_amount,
        "number_of_installments": len(installments),
    }


def get_installment_plan_progress(plan_or_installments):
    from decimal import Decimal

    if hasattr(plan_or_installments, "installments"):
        installments = plan_or_installments.installments.filter(is_active=True)
        total_amount = plan_or_installments.total_amount
    else:
        installments = plan_or_installments
        total_amount = sum(inst.get("amount", 0) for inst in installments)

    processed_installments = sum(
        1 for inst in installments if getattr(inst, "is_processed", False)
    )
    total_installments = len(installments)

    processed_amount = sum(
        getattr(inst, "amount", inst.get("amount", 0))
        for inst in installments
        if getattr(inst, "is_processed", False)
    )

    remaining_amount = total_amount - processed_amount

    if total_amount > Decimal("0.00"):
        progress_percentage = processed_amount / total_amount * 100
    else:
        progress_percentage = Decimal("0.00")

    return {
        "processed_amount": processed_amount,
        "remaining_amount": remaining_amount,
        "progress_percentage": progress_percentage,
        "processed_installments": processed_installments,
        "total_installments": total_installments,
    }


def calculate_estimated_payoff_date(total_amount, threshold_amount, start_date=None):
    if not start_date:
        start_date = timezone.now().date()

    if threshold_amount <= Decimal("0.00"):
        return None

    remaining_amount = total_amount
    current_date = start_date

    while remaining_amount > Decimal("0.00"):
        if remaining_amount <= threshold_amount:
            amount = remaining_amount
            remaining_amount = Decimal("0.00")
        else:
            amount = threshold_amount
            remaining_amount -= threshold_amount

        if remaining_amount <= Decimal("0.00"):
            return current_date

        current_date = date(
            year=current_date.year + ((current_date.month + 1) // 13),
            month=((current_date.month + 1) % 12) or 12,
            day=min(current_date.day, 28),
        )

    return current_date


def validate_expense_amount(amount):
    if not isinstance(amount, (int, float, Decimal)):
        return False, "Amount must be a number"

    if Decimal(str(amount)) <= Decimal("0.00"):
        return False, "Amount must be greater than zero"

    return True, "Valid amount"


def validate_expense_dates(request_date, incurred_date):
    today = timezone.now().date()

    if request_date > today:
        return False, "Request date cannot be in the future"

    if incurred_date > today:
        return False, "Date incurred cannot be in the future"

    if incurred_date > request_date:
        return False, "Date incurred cannot be after request date"

    return True, "Valid dates"


def get_expense_status_transition_map():
    return {
        ExpenseStatus.DRAFT.value: [
            ExpenseStatus.SUBMITTED.value,
            ExpenseStatus.CANCELLED.value,
        ],
        ExpenseStatus.SUBMITTED.value: [
            ExpenseStatus.UNDER_REVIEW.value,
            ExpenseStatus.REJECTED.value,
            ExpenseStatus.CANCELLED.value,
        ],
        ExpenseStatus.UNDER_REVIEW.value: [
            ExpenseStatus.APPROVED.value,
            ExpenseStatus.REJECTED.value,
            ExpenseStatus.CANCELLED.value,
        ],
        ExpenseStatus.APPROVED.value: [
            ExpenseStatus.DISBURSED.value,
            ExpenseStatus.CANCELLED.value,
        ],
        ExpenseStatus.REJECTED.value: [
            ExpenseStatus.SUBMITTED.value,
            ExpenseStatus.CANCELLED.value,
        ],
        ExpenseStatus.DISBURSED.value: [],
        ExpenseStatus.CANCELLED.value: [],
    }


def is_valid_status_transition(current_status, new_status):
    transition_map = get_expense_status_transition_map()
    allowed_transitions = transition_map.get(current_status, [])
    return new_status in allowed_transitions


def get_payroll_status_for_expense(expense_status, payment_status, payroll_effect):
    if expense_status != ExpenseStatus.APPROVED.value:
        return None

    if (
        payment_status == PaymentStatus.PAID_BY_EMPLOYEE.value
        and payroll_effect == PayrollEffect.ADD_TO_NEXT_PAYROLL.value
    ):
        return PayrollStatus.PENDING_PAYROLL_PROCESSING.value

    if payment_status in [
        PaymentStatus.ADVANCE_REQUESTED.value,
        PaymentStatus.LOAN_REQUESTED.value,
    ]:
        if payroll_effect == PayrollEffect.DEDUCT_FROM_NEXT_PAYROLL.value:
            return PayrollStatus.PENDING_PAYROLL_PROCESSING.value
        elif payroll_effect == PayrollEffect.DEDUCT_IN_INSTALLMENTS.value:
            return PayrollStatus.PENDING_PAYROLL_PROCESSING.value

    return None


def prepare_expense_for_payroll(expense_data):
    payroll_data = {
        "expense_id": expense_data.get("id"),
        "employee_id": expense_data.get("employee_id"),
        "amount": expense_data.get("total_amount"),
        "expense_reference": expense_data.get("reference"),
        "expense_type": expense_data.get("expense_type"),
        "payment_status": expense_data.get("payment_status"),
        "payroll_effect": expense_data.get("payroll_effect"),
        "installment_amount": expense_data.get("installment_amount"),
        "payroll_status": expense_data.get("payroll_status"),
        "is_taxable": expense_data.get("is_taxable_benefit", False),
    }

    if expense_data.get("payment_status") == PaymentStatus.PAID_BY_EMPLOYEE.value:
        payroll_data["operation"] = "ADD"
    else:
        payroll_data["operation"] = "DEDUCT"

    return payroll_data


def update_expense_after_payroll_processing(expense_data, payroll_result):
    if not payroll_result or not expense_data:
        return expense_data

    payroll_status = payroll_result.get("status")
    processed_amount = payroll_result.get("processed_amount", Decimal("0.00"))

    if payroll_status == "SUCCESS":
        if expense_data.get("payment_status") == PaymentStatus.PAID_BY_EMPLOYEE.value:
            expense_data["payroll_status"] = PayrollStatus.ADDED_TO_PAYROLL.value
        elif (
            expense_data.get("payroll_effect")
            == PayrollEffect.DEDUCT_FROM_NEXT_PAYROLL.value
        ):
            expense_data["payroll_status"] = PayrollStatus.DEDUCTED_FROM_PAYROLL.value
        elif (
            expense_data.get("payroll_effect")
            == PayrollEffect.DEDUCT_IN_INSTALLMENTS.value
        ):
            remaining_amount = (
                expense_data.get("total_amount", Decimal("0.00")) - processed_amount
            )

            if remaining_amount <= Decimal("0.00"):
                expense_data["payroll_status"] = (
                    PayrollStatus.DEDUCTED_FROM_PAYROLL.value
                )
            else:
                expense_data["payroll_status"] = PayrollStatus.PARTIALLY_PROCESSED.value
                expense_data["remaining_amount"] = remaining_amount

    expense_data["last_payroll_sync"] = timezone.now()
    expense_data["last_processed_amount"] = processed_amount

    return expense_data


def prepare_expense_for_quickbooks(expense_data):
    qb_data = {
        "expense_id": expense_data.get("id"),
        "reference": expense_data.get("reference"),
        "date": expense_data.get("request_date"),
        "employee": {
            "id": expense_data.get("employee_id"),
            "name": expense_data.get("employee_name"),
        },
        "department": {
            "id": expense_data.get("department_id"),
            "name": expense_data.get("department_name"),
        },
        "expense_category": expense_data.get("expense_category"),
        "expense_type": expense_data.get("expense_type"),
        "description": expense_data.get("description"),
        "amount": expense_data.get("total_amount"),
        "payment_method": expense_data.get("payment_method"),
        "expense_account": expense_data.get("expense_account"),
        "cost_center": expense_data.get("cost_center"),
        "tax_category": expense_data.get("tax_category"),
        "is_reimbursable": expense_data.get("is_reimbursable", False),
    }

    if expense_data.get("expense_type") == EmployeeExpenseType.PURCHASE_RETURN.value:
        qb_data["items"] = expense_data.get("items", [])

    return qb_data


def apply_threshold_based_deduction(
    total_outstanding, threshold_amount, minimum_salary_protection=None
):
    if total_outstanding <= threshold_amount:
        return total_outstanding, Decimal("0.00")

    deduction_amount = threshold_amount
    remaining_amount = total_outstanding - threshold_amount

    if minimum_salary_protection:
        max_deduction = minimum_salary_protection
        if deduction_amount > max_deduction:
            deduction_amount = max_deduction
            remaining_amount = total_outstanding - deduction_amount

    return deduction_amount, remaining_amount


def estimate_payroll_cycles(total_amount, threshold_amount):
    """
    Estimate how many payroll cycles needed to complete deduction.

    Args:
        total_amount (Decimal): Total amount to be deducted
        threshold_amount (Decimal): Maximum amount that can be deducted per cycle

    Returns:
        int: Estimated number of cycles needed
    """
    if total_amount <= Decimal("0.00") or threshold_amount <= Decimal("0.00"):
        return 0

    return math.ceil(total_amount / threshold_amount)


def create_audit_trail_entry(
    expense_id, action, user_id, previous_state=None, current_state=None, notes=None
):
    audit_data = {
        "expense_id": expense_id,
        "action": action,
        "user_id": user_id,
        "timestamp": timezone.now(),
        "notes": notes or "",
    }

    if previous_state:
        audit_data["previous_state"] = previous_state

    if current_state:
        audit_data["current_state"] = current_state

    return audit_data




##############################################################################


###############################################################################

def get_expense_summary_by_category(expenses):
    summary = {}

    for expense in expenses:
        category = expense.get("expense_category")
        amount = expense.get("total_amount", Decimal("0.00"))

        if category not in summary:
            summary[category] = {
                "count": 0,
                "total_amount": Decimal("0.00"),
                "types": {},
            }

        summary[category]["count"] += 1
        summary[category]["total_amount"] += amount

        expense_type = expense.get("expense_type")
        if expense_type:
            if expense_type not in summary[category]["types"]:
                summary[category]["types"][expense_type] = {
                    "count": 0,
                    "total_amount": Decimal("0.00"),
                }

            summary[category]["types"][expense_type]["count"] += 1
            summary[category]["types"][expense_type]["total_amount"] += amount

    return summary


def get_expense_summary_by_department(expenses):
    summary = {}

    for expense in expenses:
        department = expense.get("department_name", "Unassigned")
        amount = expense.get("total_amount", Decimal("0.00"))

        if department not in summary:
            summary[department] = {
                "count": 0,
                "total_amount": Decimal("0.00"),
                "categories": {},
            }

        summary[department]["count"] += 1
        summary[department]["total_amount"] += amount

        category = expense.get("expense_category")
        if category:
            if category not in summary[department]["categories"]:
                summary[department]["categories"][category] = {
                    "count": 0,
                    "total_amount": Decimal("0.00"),
                }

            summary[department]["categories"][category]["count"] += 1
            summary[department]["categories"][category]["total_amount"] += amount

    return summary


def get_expense_summary_by_employee(expenses):
    summary = {}

    for expense in expenses:
        employee_id = expense.get("employee_id")
        employee_name = expense.get("employee_name", "Unknown")
        amount = expense.get("total_amount", Decimal("0.00"))

        if employee_id not in summary:
            summary[employee_id] = {
                "employee_name": employee_name,
                "count": 0,
                "total_amount": Decimal("0.00"),
                "categories": {},
            }

        summary[employee_id]["count"] += 1
        summary[employee_id]["total_amount"] += amount

        category = expense.get("expense_category")
        if category:
            if category not in summary[employee_id]["categories"]:
                summary[employee_id]["categories"][category] = {
                    "count": 0,
                    "total_amount": Decimal("0.00"),
                }

            summary[employee_id]["categories"][category]["count"] += 1
            summary[employee_id]["categories"][category]["total_amount"] += amount

    return summary


def get_expense_summary_by_status(expenses):
    summary = {}

    for expense in expenses:
        status = expense.get("status", "Unknown")
        amount = expense.get("total_amount", Decimal("0.00"))

        if status not in summary:
            summary[status] = {"count": 0, "total_amount": Decimal("0.00")}

        summary[status]["count"] += 1
        summary[status]["total_amount"] += amount

    return summary


def generate_category_report(queryset, include_details):
    report = {}
    categories = ExpenseCategory.active.all()
    for category in categories:
        category_expenses = queryset.filter(expense_category=category)
        if not category_expenses.exists():
            continue
        total_amount = (
            category_expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        report[category.name] = {
            "total": total_amount,
            "count": category_expenses.count(),
            "details": category_expenses if include_details else [],
        }
    return report


def generate_department_report(queryset, include_details):
    report = {}
    departments = Department.objects.filter(is_active=True)
    for department in departments:
        department_expenses = queryset.filter(department=department)
        if not department_expenses.exists():
            continue
        total_amount = (
            department_expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        report[department.name] = {
            "total": total_amount,
            "count": department_expenses.count(),
            "details": department_expenses if include_details else [],
        }
    return report


def generate_employee_report(queryset, include_details):
    report = {}
    employees = CustomUser.objects.filter(
        is_active=True, id__in=queryset.values_list("employee", flat=True).distinct()
    )
    for employee in employees:
        employee_expenses = queryset.filter(employee=employee)
        if not employee_expenses.exists():
            continue
        total_amount = (
            employee_expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        report[f"{employee.first_name} {employee.last_name}"] = {
            "total": total_amount,
            "count": employee_expenses.count(),
            "details": employee_expenses if include_details else [],
        }
    return report


def generate_status_report(queryset, include_details):
    report = {}
    for status in ExpenseStatus:
        status_expenses = queryset.filter(status=status.value)
        if not status_expenses.exists():
            continue
        total_amount = (
            status_expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        )
        report[status.value] = {
            "total": total_amount,
            "count": status_expenses.count(),
            "details": status_expenses if include_details else [],
        }
    return report


def export_report_as_csv(report_data, report_title, include_details):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{report_title.replace(" ", "_")}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([report_title])
    writer.writerow(["Category", "Count", "Total Amount"])

    for category, data in report_data.items():
        writer.writerow([category, data["count"], data["total"]])
        if include_details and data["details"]:
            writer.writerow(
                ["Reference", "Date", "Employee", "Description", "Amount", "Status"]
            )
            for expense in data["details"]:
                writer.writerow(
                    [
                        expense.reference,
                        expense.date_incurred,
                        f"{expense.employee.first_name} {expense.employee.last_name}",
                        expense.description,
                        expense.total_amount,
                        expense.status,
                    ]
                )
            writer.writerow([])
    return response


def export_report_as_excel(report_data, report_title, include_details):
    try:
        import xlwt
    except ImportError:
        return None

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = (
        f'attachment; filename="{report_title.replace(" ", "_")}.xls"'
    )

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Report")
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    ws.write(row_num, 0, report_title, font_style)
    row_num += 2

    columns = ["Category", "Count", "Total Amount"]
    for col_num, column_title in enumerate(columns):
        ws.write(row_num, col_num, column_title, font_style)

    row_num += 1
    font_style = xlwt.XFStyle()

    for category, data in report_data.items():
        ws.write(row_num, 0, category, font_style)
        ws.write(row_num, 1, data["count"], font_style)
        ws.write(row_num, 2, float(data["total"]), font_style)
        row_num += 1

        if include_details and data["details"]:
            detail_columns = [
                "Reference",
                "Date",
                "Employee",
                "Description",
                "Amount",
                "Status",
            ]
            row_num += 1

            for col_num, column_title in enumerate(detail_columns):
                ws.write(row_num, col_num, column_title, font_style)

            row_num += 1

            for expense in data["details"]:
                ws.write(row_num, 0, expense.reference, font_style)
                ws.write(
                    row_num, 1, expense.date_incurred.strftime("%Y-%m-%d"), font_style
                )
                ws.write(
                    row_num,
                    2,
                    f"{expense.employee.first_name} {expense.employee.last_name}",
                    font_style,
                )
                ws.write(row_num, 3, expense.description, font_style)
                ws.write(row_num, 4, float(expense.total_amount), font_style)
                ws.write(row_num, 5, expense.status, font_style)
                row_num += 1

            row_num += 1

    wb.save(response)
    return response


def export_report_as_pdf(report_data, report_title, include_details):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        return None

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{report_title.replace(" ", "_")}.pdf"'
    )

    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]

    elements.append(Paragraph(report_title, title_style))
    elements.append(Spacer(1, 12))

    data = [["Category", "Count", "Total Amount"]]

    for category, category_data in report_data.items():
        data.append(
            [category, category_data["count"], f"${category_data['total']:.2f}"]
        )

        if include_details and category_data["details"]:
            data.append(["", "", ""])
            data.append(
                ["Reference", "Date", "Employee", "Description", "Amount", "Status"]
            )

            for expense in category_data["details"]:
                data.append(
                    [
                        expense.reference,
                        expense.date_incurred.strftime("%Y-%m-%d"),
                        f"{expense.employee.first_name} {expense.employee.last_name}",
                        expense.description,
                        f"${expense.total_amount:.2f}",
                        expense.status,
                    ]
                )

            data.append(["", "", ""])

    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)

    return response


def export_expenses_as_csv(queryset, include_details, include_audit_trail):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses_export.csv"'

    writer = csv.writer(response)
    writer.writerow(["Expense Export"])
    writer.writerow(
        [
            "Reference",
            "Date",
            "Employee",
            "Department",
            "Category",
            "Type",
            "Description",
            "Amount",
            "Status",
            "Payment Status",
        ]
    )

    for expense in queryset:
        writer.writerow(
            [
                expense.reference,
                expense.date_incurred,
                f"{expense.employee.first_name} {expense.employee.last_name}",
                expense.department.name if expense.department else "",
                expense.expense_category.name,
                expense.expense_type.name,
                expense.description,
                expense.total_amount,
                expense.status,
                expense.payment_status,
            ]
        )

        if include_details:
            # Purchase items
            if hasattr(expense, "purchase_items") and expense.purchase_items.exists():
                writer.writerow(["", "Purchase Items:"])
                writer.writerow(["", "Item", "Quantity", "Unit Price", "Total"])

                for item in expense.purchase_items.filter(is_active=True):
                    writer.writerow(
                        [
                            "",
                            item.item_description,
                            item.quantity,
                            item.unit_price,
                            item.total_price,
                        ]
                    )

            # Installment plans
            if (
                hasattr(expense, "installment_plans")
                and expense.installment_plans.filter(is_active=True).exists()
            ):
                plan = expense.installment_plans.filter(is_active=True).first()
                writer.writerow(["", "Installment Plan:"])
                writer.writerow(
                    [
                        "",
                        "Total Amount",
                        "Installment Amount",
                        "Number of Installments",
                        "Start Date",
                    ]
                )
                writer.writerow(
                    [
                        "",
                        plan.total_amount,
                        plan.installment_amount,
                        plan.number_of_installments,
                        plan.start_date,
                    ]
                )

                if hasattr(plan, "installments") and plan.installments.exists():
                    writer.writerow(["", "Installments:"])
                    writer.writerow(
                        [
                            "",
                            "Number",
                            "Date",
                            "Amount",
                            "Remaining Balance",
                            "Processed",
                        ]
                    )

                    for installment in plan.installments.filter(
                        is_active=True
                    ).order_by("installment_number"):
                        writer.writerow(
                            [
                                "",
                                installment.installment_number,
                                installment.scheduled_date,
                                installment.amount,
                                installment.remaining_balance,
                                "Yes" if installment.is_processed else "No",
                            ]
                        )

        if include_audit_trail:
            audit_entries = ExpenseAuditTrail.objects.filter(expense=expense).order_by(
                "timestamp"
            )

            if audit_entries.exists():
                writer.writerow(["", "Audit Trail:"])
                writer.writerow(["", "Date", "User", "Action", "Notes"])

                for entry in audit_entries:
                    writer.writerow(
                        [
                            "",
                            entry.timestamp,
                            f"{entry.user.first_name} {entry.user.last_name}",
                            entry.action,
                            entry.notes,
                        ]
                    )

        writer.writerow([])

    return response

def export_expenses_as_excel(queryset, include_details, include_audit_trail):
    try:
        import xlwt
    except ImportError:
        return None

    response = HttpResponse(content_type="application/ms-excel")
    response["Content-Disposition"] = 'attachment; filename="expenses_export.xls"'

    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("Expenses")

    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    columns = [
        "Reference",
        "Date",
        "Employee",
        "Department",
        "Category",
        "Type",
        "Description",
        "Amount",
        "Status",
        "Payment Status",
    ]

    for col_num, column_title in enumerate(columns):
        ws.write(row_num, col_num, column_title, font_style)

    font_style = xlwt.XFStyle()

    for expense in queryset:
        row_num += 1

        row = [
            expense.reference,
            expense.date_incurred.strftime("%Y-%m-%d"),
            f"{expense.employee.first_name} {expense.employee.last_name}",
            expense.department.name if expense.department else "",
            expense.expense_category.name,
            expense.expense_type.name,
            expense.description,
            float(expense.total_amount),
            expense.status,
            expense.payment_status,
        ]

        for col_num, cell_value in enumerate(row):
            ws.write(row_num, col_num, cell_value, font_style)

    wb.save(response)
    return response

def export_expenses_as_pdf(queryset, include_details, include_audit_trail):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        return None

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="expenses_export.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]

    elements.append(Paragraph("Expense Export", title_style))
    elements.append(Spacer(1, 12))

    data = [
        [
            "Reference",
            "Date",
            "Employee",
            "Category",
            "Description",
            "Amount",
            "Status",
        ]
    ]

    for expense in queryset:
        data.append(
            [
                expense.reference,
                expense.date_incurred.strftime("%Y-%m-%d"),
                f"{expense.employee.first_name} {expense.employee.last_name}",
                expense.expense_category.name,
                expense.description,
                f"${expense.total_amount:.2f}",
                expense.status,
            ]
        )

    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)

    return response
