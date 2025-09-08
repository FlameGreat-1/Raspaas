from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from .models import Expense, ExpenseAuditTrail, PayrollExpenseIntegration
from .utils import PayrollStatus, PayrollEffect


class ExpensePayrollService:
    @staticmethod
    def get_payroll_amounts(employee_id):
        pending_expenses = Expense.active.filter(
            employee_id=employee_id,
            status="APPROVED",
            add_to_payroll=True,
            payroll_status=PayrollStatus.PENDING_PAYROLL_PROCESSING.value,
        )

        addition_expenses = pending_expenses.filter(
            payroll_effect=PayrollEffect.ADD_TO_NEXT_PAYROLL.value
        )
        addition_amount = sum(
            expense.installment_amount or expense.total_amount
            for expense in addition_expenses
        )

        deduction_expenses = pending_expenses.filter(
            payroll_effect=PayrollEffect.DEDUCT_FROM_NEXT_PAYROLL.value
        )
        deduction_amount = sum(
            expense.installment_amount or expense.total_amount
            for expense in deduction_expenses
        )

        return {
            "employee_id": employee_id,
            "addition_amount": addition_amount,
            "deduction_amount": deduction_amount,
            "expense_ids": list(pending_expenses.values_list("id", flat=True)),
            "has_pending_expenses": pending_expenses.exists(),
        }

    @staticmethod
    @transaction.atomic
    def mark_as_processed(expense_ids, payroll_reference, payroll_period):
        processed_date = timezone.now().date()
        results = {"success_count": 0, "failed_count": 0, "details": []}

        for expense_id in expense_ids:
            try:
                expense = Expense.active.get(id=expense_id)

                processed_amount = expense.installment_amount or expense.total_amount

                remaining = max(
                    Decimal("0.00"), expense.total_amount - processed_amount
                )
                if expense.remaining_amount:
                    remaining = max(
                        Decimal("0.00"), expense.remaining_amount - processed_amount
                    )

                operation = (
                    "ADD"
                    if expense.payroll_effect == PayrollEffect.ADD_TO_NEXT_PAYROLL.value
                    else "DEDUCT"
                )

                integration = PayrollExpenseIntegration.objects.create(
                    expense=expense,
                    payroll_period=payroll_period,
                    payroll_date=processed_date,
                    processed_amount=processed_amount,
                    remaining_amount=remaining,
                    operation=operation,
                    status="PROCESSED",
                    payroll_reference=payroll_reference,
                )

                if expense.payroll_effect == PayrollEffect.ADD_TO_NEXT_PAYROLL.value:
                    expense.payroll_status = (
                        PayrollStatus.ADDED_TO_PAYROLL.value
                        if remaining <= Decimal("0.00")
                        else PayrollStatus.PARTIALLY_PROCESSED.value
                    )
                else:
                    expense.payroll_status = (
                        PayrollStatus.DEDUCTED_FROM_PAYROLL.value
                        if remaining <= Decimal("0.00")
                        else PayrollStatus.PARTIALLY_PROCESSED.value
                    )
                expense.last_payroll_sync = timezone.now()
                expense.last_processed_amount = processed_amount
                expense.remaining_amount = remaining
                expense.save(
                    update_fields=[
                        "payroll_status",
                        "last_payroll_sync",
                        "last_processed_amount",
                        "remaining_amount",
                    ]
                )

                ExpenseAuditTrail.objects.create(
                    expense=expense,
                    action=f"Processed in payroll for period {payroll_period}",
                    current_state={
                        "payroll_period": payroll_period,
                        "payroll_date": str(processed_date),
                        "processed_amount": str(processed_amount),
                        "remaining_amount": str(remaining),
                        "payroll_reference": payroll_reference,
                        "operation": operation,
                    },
                )

                results["success_count"] += 1
                results["details"].append(
                    {
                        "expense_id": expense_id,
                        "success": True,
                        "processed_amount": str(processed_amount),
                        "remaining_amount": str(remaining),
                    }
                )

            except Expense.DoesNotExist:
                results["failed_count"] += 1
                results["details"].append(
                    {
                        "expense_id": expense_id,
                        "success": False,
                        "message": "Expense not found",
                    }
                )
            except Exception as e:
                results["failed_count"] += 1
                results["details"].append(
                    {"expense_id": expense_id, "success": False, "message": str(e)}
                )

        return results
