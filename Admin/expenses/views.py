from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.views import View
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, Count, F, Value, CharField
from django.db.models.functions import Concat
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory, inlineformset_factory
from decimal import Decimal
import csv
import json
import datetime

from accounts.models import CustomUser, Department
from employees.models import EmployeeProfile

from .models import (
    Expense,
    ExpenseCategory,
    ExpenseType,
    ExpenseDocument,
    PurchaseItem,
    PurchaseSummary,
    ExpenseAuditTrail,
    ExpenseApprovalWorkflow,
    ExpenseApprovalStep,
    ExpenseDeductionThreshold,
    EmployeeDeductionThreshold,
    ExpenseInstallmentPlan,
    ExpenseInstallment,
)

from .forms import (
    ExpenseCategoryForm,
    ExpenseTypeForm,
    ExpenseForm,
    ExpenseDocumentForm,
    PurchaseItemForm,
    PurchaseItemReturnForm,
    PurchaseExpenseForm,
    ExpenseDeductionThresholdForm,
    EmployeeDeductionThresholdForm,
    ExpenseStatusUpdateForm,
    ExpenseFilterForm,
    ExpenseReportForm,
    ExpenseBulkActionForm,
    ExpenseQuickbooksSyncForm,
    ExpenseExportForm,
    ExpenseApprovalForm,
    ExpenseDisbursementForm,
    ExpenseSearchForm,
    ExpenseBatchApprovalForm,
    ExpenseBatchDisbursementForm,
    ExpenseNotesForm,
)

from .utils import (
    ExpenseStatus,
    PaymentStatus,
    PayrollEffect,
    PayrollStatus,
    ReturnStatus,
    generate_expense_reference,
    apply_threshold_based_deduction, 
    estimate_payroll_cycles,
    get_installment_plan_progress,
    is_valid_status_transition,
    generate_category_report,
    generate_department_report,
    generate_employee_report,
    generate_status_report,
    export_report_as_csv,
    export_report_as_excel,
    export_report_as_pdf,
    export_expenses_as_csv,
    export_expenses_as_excel,
    export_expenses_as_pdf,
)

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.now().date()
        thirty_days_ago = today - datetime.timedelta(days=30)
        
        recent_expenses = Expense.active.filter(
            created_at__gte=thirty_days_ago
        ).order_by('-created_at')[:10]
        
        pending_approval = Expense.active.filter(
            status=ExpenseStatus.UNDER_REVIEW.value
        ).count()
        
        approved_expenses = Expense.active.filter(
            status=ExpenseStatus.APPROVED.value
        ).count()
        
        rejected_expenses = Expense.active.filter(
            status=ExpenseStatus.REJECTED.value
        ).count()
        
        total_expenses_amount = Expense.active.filter(
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        employee_expenses = Expense.active.filter(
            expense_category__is_employee_expense=True,
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        operational_expenses = Expense.active.filter(
            expense_category__is_operational_expense=True,
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        expense_by_status = Expense.active.filter(
            created_at__gte=thirty_days_ago
        ).values('status').annotate(count=Count('id')).order_by('status')
        
        expense_by_category = Expense.active.filter(
            created_at__gte=thirty_days_ago
        ).values('expense_category__name').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')
        
        expense_by_department = Expense.active.filter(
            created_at__gte=thirty_days_ago
        ).values('department__name').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')
        
        context = {
            'recent_expenses': recent_expenses,
            'pending_approval': pending_approval,
            'approved_expenses': approved_expenses,
            'rejected_expenses': rejected_expenses,
            'total_expenses_amount': total_expenses_amount,
            'employee_expenses': employee_expenses,
            'operational_expenses': operational_expenses,
            'expense_by_status': expense_by_status,
            'expense_by_category': expense_by_category,
            'expense_by_department': expense_by_department,
        }
        
        return render(request, 'expenses/dashboard.html', context)


class ExpenseCategoryListView(LoginRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'expenses/category_list.html'
    context_object_name = 'categories'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = ExpenseCategory.active.all()
        search_term = self.request.GET.get('search', '')
        
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) | 
                Q(code__icontains=search_term) |
                Q(description__icontains=search_term)
            )
            
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_term'] = self.request.GET.get('search', '')
        return context


class ExpenseCategoryCreateView(LoginRequiredMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Expense category created successfully.')
        return super().form_valid(form)


class ExpenseCategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    success_url = reverse_lazy('expenses:category_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Expense category updated successfully.')
        return super().form_valid(form)


class ExpenseCategoryDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(ExpenseCategory, pk=pk)
        
        if Expense.active.filter(expense_category=category).exists():
            messages.error(request, 'Cannot delete category as it has associated expenses.')
            return redirect('expenses:category_list')
        
        category.soft_delete()
        messages.success(request, 'Expense category deleted successfully.')
        return redirect('expenses:category_list')


class ExpenseTypeListView(LoginRequiredMixin, ListView):
    model = ExpenseType
    template_name = 'expenses/type_list.html'
    context_object_name = 'expense_types'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = ExpenseType.active.all()
        search_term = self.request.GET.get('search', '')
        category_id = self.request.GET.get('category', '')
        
        if search_term:
            queryset = queryset.filter(
                Q(name__icontains=search_term) | 
                Q(code__icontains=search_term) |
                Q(description__icontains=search_term)
            )
            
        if category_id:
            queryset = queryset.filter(category_id=category_id)
            
        return queryset.order_by('category__name', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_term'] = self.request.GET.get('search', '')
        context['category_id'] = self.request.GET.get('category', '')
        context['categories'] = ExpenseCategory.active.all()
        return context


class ExpenseTypeCreateView(LoginRequiredMixin, CreateView):
    model = ExpenseType
    form_class = ExpenseTypeForm
    template_name = 'expenses/type_form.html'
    success_url = reverse_lazy('expenses:type_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = ExpenseCategory.active.all()
        return form
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Expense type created successfully.')
        return super().form_valid(form)


class ExpenseTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = ExpenseType
    form_class = ExpenseTypeForm
    template_name = 'expenses/type_form.html'
    success_url = reverse_lazy('expenses:type_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['category'].queryset = ExpenseCategory.active.all()
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'Expense type updated successfully.')
        return super().form_valid(form)


class ExpenseTypeDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        expense_type = get_object_or_404(ExpenseType, pk=pk)
        
        if Expense.active.filter(expense_type=expense_type).exists():
            messages.error(request, 'Cannot delete expense type as it has associated expenses.')
            return redirect('expenses:type_list')
        
        expense_type.soft_delete()
        messages.success(request, 'Expense type deleted successfully.')
        return redirect('expenses:type_list')

class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Expense.active.all()
        
        filter_form = ExpenseFilterForm(self.request.GET)
        if filter_form.is_valid():
            data = filter_form.cleaned_data
            
            if data.get('employee'):
                queryset = queryset.filter(employee=data['employee'])
                
            if data.get('department'):
                queryset = queryset.filter(department=data['department'])
                
            if data.get('expense_category'):
                queryset = queryset.filter(expense_category=data['expense_category'])
                
            if data.get('expense_type'):
                queryset = queryset.filter(expense_type=data['expense_type'])
                
            if data.get('status'):
                queryset = queryset.filter(status=data['status'])
                
            if data.get('payment_status'):
                queryset = queryset.filter(payment_status=data['payment_status'])
                
            if data.get('payroll_status'):
                queryset = queryset.filter(payroll_status=data['payroll_status'])
                
            if data.get('date_from'):
                queryset = queryset.filter(date_incurred__gte=data['date_from'])
                
            if data.get('date_to'):
                queryset = queryset.filter(date_incurred__lte=data['date_to'])
                
            if data.get('amount_min'):
                queryset = queryset.filter(total_amount__gte=data['amount_min'])
                
            if data.get('amount_max'):
                queryset = queryset.filter(total_amount__lte=data['amount_max'])
                
            if data.get('reference'):
                queryset = queryset.filter(reference__icontains=data['reference'])
        
        search_term = self.request.GET.get('search', '')
        if search_term:
            queryset = queryset.filter(
                Q(reference__icontains=search_term) |
                Q(employee__first_name__icontains=search_term) |
                Q(employee__last_name__icontains=search_term) |
                Q(description__icontains=search_term)
            )
            
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ExpenseFilterForm(self.request.GET)
        context['bulk_action_form'] = ExpenseBulkActionForm()
        
        expense_totals = Expense.active.aggregate(
            total=Sum('total_amount'),
            pending=Sum('total_amount', filter=Q(status=ExpenseStatus.UNDER_REVIEW.value)),
            approved=Sum('total_amount', filter=Q(status=ExpenseStatus.APPROVED.value)),
            rejected=Sum('total_amount', filter=Q(status=ExpenseStatus.REJECTED.value))
        )
        
        context['expense_totals'] = expense_totals
        return context


class ExpenseDetailView(LoginRequiredMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'expense'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense = self.get_object()
        
        context['documents'] = ExpenseDocument.active.filter(expense=expense)
        context['audit_trail'] = ExpenseAuditTrail.objects.filter(expense=expense).order_by('-timestamp')
        
        if hasattr(expense, 'approval_workflow'):
            context['approval_workflow'] = expense.approval_workflow.all().first()
            if context['approval_workflow']:
                context['approval_steps'] = ExpenseApprovalStep.active.filter(
                    workflow=context['approval_workflow']
                ).order_by('step_number')
        
        if hasattr(expense, 'purchase_items'):
            context['purchase_items'] = PurchaseItem.active.filter(expense=expense)
            
        if hasattr(expense, 'purchase_summary'):
            context['purchase_summary'] = expense.purchase_summary
            
        if hasattr(expense, 'installment_plans'):
            context['installment_plan'] = expense.installment_plans.filter(is_active=True).first()
            if context['installment_plan']:
                context['installments'] = ExpenseInstallment.active.filter(
                    plan=context['installment_plan']
                ).order_by('installment_number')
                
        if hasattr(expense, 'payroll_integrations'):
            context['payroll_integrations'] = expense.payroll_integrations.filter(is_active=True)
            
        context['status_form'] = ExpenseStatusUpdateForm(expense=expense)
        context['approval_form'] = ExpenseApprovalForm()
        context['document_form'] = ExpenseDocumentForm(expense=expense)
        
        return context

class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        old_status = self.object.status
        old_total = self.object.total_amount
        
        response = super().form_valid(form)
        
        expense = self.object
        
        if old_status != expense.status:
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=f"Status changed from {old_status} to {expense.status}",
                user=self.request.user,
                previous_state={'status': old_status},
                current_state={'status': expense.status}
            )
            
        if old_total != expense.total_amount:
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=f"Amount changed from {old_total} to {expense.total_amount}",
                user=self.request.user,
                previous_state={'total_amount': str(old_total)},
                current_state={'total_amount': str(expense.total_amount)}
            )
        
        messages.success(self.request, f'Expense {expense.reference} updated successfully.')
        return response
    
    def get_success_url(self):
        return reverse('expenses:expense_detail', kwargs={'pk': self.object.pk})


class ExpenseDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        
        if expense.status not in [ExpenseStatus.DRAFT.value, ExpenseStatus.REJECTED.value]:
            messages.error(request, 'Only draft or rejected expenses can be deleted.')
            return redirect('expenses:expense_detail', pk=expense.pk)
        
        expense.soft_delete()
        
        ExpenseAuditTrail.objects.create(
            expense=expense,
            action="Expense deleted",
            user=request.user,
            previous_state={'status': expense.status},
            current_state={'status': 'DELETED'}
        )
        
        messages.success(request, f'Expense {expense.reference} deleted successfully.')
        return redirect('expenses:expense_list')

class ExpenseStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseStatusUpdateForm(request.POST, expense=expense)
        
        if form.is_valid():
            new_status = form.cleaned_data['status']
            reason = form.cleaned_data.get('reason', '')
            
            if not is_valid_status_transition(expense.status, new_status):
                messages.error(request, f'Invalid status transition from {expense.status} to {new_status}.')
                return redirect('expenses:expense_detail', pk=expense.pk)
            
            old_status = expense.status
            expense.status = new_status
            
            if new_status == ExpenseStatus.APPROVED.value:
                expense.approved_by = request.user
                expense.approved_date = timezone.now()
                
                if expense.add_to_payroll:
                    expense.payroll_status = PayrollStatus.PENDING_PAYROLL_PROCESSING.value
            
            if new_status == ExpenseStatus.REJECTED.value:
                expense.rejected_by = request.user
                expense.rejected_date = timezone.now()
                expense.rejection_reason = reason
            
            expense.save()
            
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=f"Status changed from {old_status} to {new_status}",
                user=request.user,
                previous_state={'status': old_status},
                current_state={'status': new_status},
                notes=reason
            )
            
            messages.success(request, f'Expense status updated to {new_status}.')
        else:
            for error in form.errors.values():
                messages.error(request, error)
        
        return redirect('expenses:expense_detail', pk=expense.pk)


class ExpenseApprovalView(LoginRequiredMixin, View):
    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseApprovalForm(request.POST)

        if form.is_valid():
            decision = form.cleaned_data['decision']
            notes = form.cleaned_data.get('notes', '')

            if decision == 'approve':
                if expense.status != ExpenseStatus.UNDER_REVIEW.value:
                    messages.error(request, 'Only expenses under review can be approved.')
                    return redirect('expenses:expense_detail', pk=expense.pk)

                expense.status = ExpenseStatus.APPROVED.value
                expense.approved_by = request.user
                expense.approved_date = timezone.now()

                if expense.add_to_payroll:
                    expense.payroll_status = PayrollStatus.PENDING_PAYROLL_PROCESSING.value

                action = "Expense approved"
                message = 'Expense approved successfully.'
            else:
                if expense.status != ExpenseStatus.UNDER_REVIEW.value:
                    messages.error(request, 'Only expenses under review can be rejected.')
                    return redirect('expenses:expense_detail', pk=expense.pk)

                expense.status = ExpenseStatus.REJECTED.value
                expense.rejected_by = request.user
                expense.rejected_date = timezone.now()
                expense.rejection_reason = notes

                action = "Expense rejected"
                message = 'Expense rejected successfully.'

            expense.save()

            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=action,
                user=request.user,
                previous_state={'status': ExpenseStatus.UNDER_REVIEW.value},
                current_state={'status': expense.status},
                notes=notes
            )

            messages.success(request, message)
        else:
            for error in form.errors.values():
                messages.error(request, error)

        return redirect('expenses:expense_detail', pk=expense.pk)


class DocumentUploadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseDocumentForm(expense=expense)
        documents = ExpenseDocument.active.filter(expense=expense)

        context = {"expense": expense, "form": form, "documents": documents}

        return render(request, "expenses/document_upload.html", context)

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = ExpenseDocumentForm(request.POST, request.FILES, expense=expense)

        if form.is_valid():
            document = form.save(commit=False)
            document.created_by = request.user
            document.save()

            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=f"Document uploaded: {document.document_type}",
                user=request.user,
                current_state={"document_id": document.id},
            )

            messages.success(request, "Document uploaded successfully.")

            if "save_and_continue" in request.POST:
                return redirect("expenses:document_upload", pk=expense.pk)
            return redirect("expenses:expense_detail", pk=expense.pk)

        documents = ExpenseDocument.active.filter(expense=expense)
        context = {"expense": expense, "form": form, "documents": documents}

        return render(request, "expenses/document_upload.html", context)


class DocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(ExpenseDocument, pk=pk)
        expense = document.expense

        document.soft_delete()

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action=f"Document deleted: {document.document_type}",
            user=request.user,
            previous_state={"document_id": document.id},
        )

        messages.success(request, "Document deleted successfully.")
        return redirect("expenses:expense_detail", pk=expense.pk)


class PurchaseExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = PurchaseExpenseForm
    template_name = "expenses/purchase_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.reference = generate_expense_reference()

        response = super().form_valid(form)

        expense = self.object

        if expense.receipt_attached:
            messages.info(
                self.request, "Please upload receipt documents for this purchase."
            )

        messages.success(
            self.request, f"Purchase expense {expense.reference} created successfully."
        )
        return response

    def get_success_url(self):
        if self.object.receipt_attached:
            return reverse("expenses:document_upload", kwargs={"pk": self.object.pk})
        return reverse("expenses:purchase_items", kwargs={"pk": self.object.pk})


class PurchaseItemsView(LoginRequiredMixin, View):
    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)

        if not expense.expense_type.is_purchase_return:
            messages.error(request, "This expense is not a purchase expense.")
            return redirect("expenses:expense_detail", pk=expense.pk)

        form = PurchaseItemForm(expense=expense)
        items = PurchaseItem.active.filter(expense=expense)

        context = {"expense": expense, "form": form, "items": items}

        return render(request, "expenses/purchase_items.html", context)

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        form = PurchaseItemForm(request.POST, expense=expense)

        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()

            ExpenseAuditTrail.objects.create(
                expense=expense,
                action=f"Purchase item added: {item.item_description}",
                user=request.user,
                current_state={"item_id": item.id},
            )

            messages.success(request, "Purchase item added successfully.")

            if "save_and_continue" in request.POST:
                return redirect("expenses:purchase_items", pk=expense.pk)
            return redirect("expenses:expense_detail", pk=expense.pk)

        items = PurchaseItem.active.filter(expense=expense)
        context = {"expense": expense, "form": form, "items": items}

        return render(request, "expenses/purchase_items.html", context)


class PurchaseItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(PurchaseItem, pk=pk)
        expense = item.expense

        item.soft_delete()

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action=f"Purchase item deleted: {item.item_description}",
            user=request.user,
            previous_state={"item_id": item.id},
        )

        messages.success(request, "Purchase item deleted successfully.")
        return redirect("expenses:purchase_items", pk=expense.pk)


class PurchaseItemReturnView(LoginRequiredMixin, UpdateView):
    model = PurchaseItem
    form_class = PurchaseItemReturnForm
    template_name = "expenses/purchase_return.html"

    def get_success_url(self):
        return reverse("expenses:expense_detail", kwargs={"pk": self.object.expense.pk})

    def form_valid(self, form):
        item = self.object
        expense = item.expense

        form.instance.return_status = ReturnStatus.RETURNED.value
        form.instance.return_date = (
            form.cleaned_data.get("return_date") or timezone.now().date()
        )

        response = super().form_valid(form)

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action=f"Item returned: {item.item_description}",
            user=self.request.user,
            previous_state={"return_status": ReturnStatus.PENDING.value},
            current_state={"return_status": ReturnStatus.RETURNED.value},
        )

        messages.success(self.request, "Item return processed successfully.")
        return response

class PurchaseSummaryView(LoginRequiredMixin, DetailView):
    model = PurchaseSummary
    template_name = 'expenses/purchase_summary_detail.html'
    context_object_name = 'summary'
    
    def get_object(self, queryset=None):
        expense_id = self.kwargs.get('expense_id')
        return get_object_or_404(PurchaseSummary, expense_id=expense_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['purchase_items'] = self.object.expense.purchase_items.filter(is_active=True)
        return context

class AutoCreateWorkflowMixin:
    def create_standard_workflow(self, expense, created_by):
        if hasattr(expense, "approval_workflow") and expense.approval_workflow.exists():
            return None, "This expense already has an approval workflow."

        workflow = ExpenseApprovalWorkflow.objects.create(
            expense=expense, current_step=1, total_steps=5, created_by=created_by
        )

        step_names = [
            "Employee Request",
            "Admin/HR Entry",
            "Review",
            "Approval",
            "Disbursement",
        ]

        step_descriptions = [
            "Employee submits expense request with supporting documents",
            "Admin/HR enters the expense into the system and validates documentation",
            "Manager or designated approver reviews the expense for legitimacy",
            "Authorized person approves the expense",
            "Finance processes payment and records payment details",
        ]

        for i, (name, description) in enumerate(zip(step_names, step_descriptions), 1):
            approver = None
            if i == 1:
                approver = expense.employee
            elif i == 2:
                approver = created_by
            elif i == 3 or i == 4:
                approver = (
                    expense.employee.manager
                    if hasattr(expense.employee, "manager")
                    else created_by
                )
            else:
                approver = created_by

            ExpenseApprovalStep.objects.create(
                workflow=workflow,
                step_number=i,
                name=name,
                description=description,
                approver=approver,
                created_by=created_by,
            )

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action="Standard approval workflow created",
            user=created_by,
            current_state={"workflow_id": workflow.id},
        )

        return workflow, "Standard approval workflow created successfully."


class ExpenseCreateView(LoginRequiredMixin, AutoCreateWorkflowMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.reference = generate_expense_reference()
        
        response = super().form_valid(form)
        
        workflow, workflow_message = self.create_standard_workflow(self.object, self.request.user)
        if workflow:
            messages.success(self.request, workflow_message)
        
        expense = self.object
        
        if expense.receipt_attached:
            messages.info(self.request, 'Please upload receipt documents for this expense.')
        
        if expense.add_to_payroll and expense.payroll_effect == PayrollEffect.DEDUCT_IN_INSTALLMENTS.value:
            if not expense.installment_amount:
                default_threshold = ExpenseDeductionThreshold.get_current_threshold()
                expense.installment_amount = default_threshold.default_threshold_amount
                expense.save(update_fields=["installment_amount"])
            
            plan = ExpenseInstallmentPlan.objects.create(
                expense=expense,
                total_amount=expense.total_amount,
                installment_amount=expense.installment_amount,
                start_date=timezone.now().date(),
                created_by=self.request.user
            )
            
            installment_details = calculate_installment_details(
                expense.total_amount, 
                expense.installment_amount,
                plan.start_date
            )
            
            for installment in installment_details['installments']:
                ExpenseInstallment.objects.create(
                    plan=plan,
                    installment_number=installment['installment_number'],
                    scheduled_date=installment['date'],
                    amount=installment['amount'],
                    remaining_balance=installment['remaining_balance']
                )
            
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action="Installment plan created automatically",
                user=self.request.user,
                current_state={
                    "plan_id": plan.id,
                    "total_amount": str(plan.total_amount),
                    "installment_amount": str(plan.installment_amount),
                    "number_of_installments": plan.number_of_installments
                }
            )
            
            messages.success(self.request, f'Installment plan created with {plan.number_of_installments} installments.')
        
        messages.success(self.request, f'Expense {expense.reference} created successfully.')
        return response
    
    def get_success_url(self):
        if self.object.receipt_attached:
            return reverse('expenses:document_upload', kwargs={'pk': self.object.pk})
        return reverse('expenses:expense_detail', kwargs={'pk': self.object.pk})


class WorkflowAdvanceView(LoginRequiredMixin, View):
    def post(self, request, pk):
        workflow = get_object_or_404(ExpenseApprovalWorkflow, pk=pk)
        expense = workflow.expense

        if workflow.is_completed:
            messages.error(request, "This workflow is already completed.")
            return redirect("expenses:expense_detail", pk=expense.pk)

        success, message = workflow.advance_to_next_step(request.user)

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        return redirect("expenses:expense_detail", pk=expense.pk)


class WorkflowStepUpdateView(LoginRequiredMixin, UpdateView):
    model = ExpenseApprovalStep
    fields = ["approver", "notes"]
    template_name = "expenses/workflow_step_form.html"

    def get_success_url(self):
        return reverse(
            "expenses:expense_detail", kwargs={"pk": self.object.workflow.expense.pk}
        )

    def form_valid(self, form):
        response = super().form_valid(form)

        ExpenseAuditTrail.objects.create(
            expense=self.object.workflow.expense,
            action=f"Step {self.object.step_number} ({self.object.name}) updated",
            user=self.request.user,
            current_state={"step_id": self.object.id},
        )

        messages.success(self.request, f"Step {self.object.name} updated successfully.")
        return response


class DeductionThresholdListView(LoginRequiredMixin, ListView):
    model = ExpenseDeductionThreshold
    template_name = "expenses/threshold_list.html"
    context_object_name = "thresholds"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_threshold"] = ExpenseDeductionThreshold.get_current_threshold()
        context[
            "employee_thresholds"
        ] = EmployeeDeductionThreshold.active.all().order_by(
            "employee__last_name", "employee__first_name"
        )
        return context


class DeductionThresholdCreateView(LoginRequiredMixin, CreateView):
    model = ExpenseDeductionThreshold
    form_class = ExpenseDeductionThresholdForm
    template_name = "expenses/threshold_form.html"
    success_url = reverse_lazy("expenses:threshold_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        current_thresholds = ExpenseDeductionThreshold.active.all()
        for threshold in current_thresholds:
            threshold.is_active = False
            threshold.save()

        messages.success(
            self.request, "Default deduction threshold updated successfully."
        )
        return super().form_valid(form)


class EmployeeThresholdCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeDeductionThreshold
    form_class = EmployeeDeductionThresholdForm
    template_name = "expenses/employee_threshold_form.html"
    success_url = reverse_lazy("expenses:threshold_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        employee = form.cleaned_data["employee"]
        effective_from = form.cleaned_data["effective_from"]

        existing_thresholds = EmployeeDeductionThreshold.active.filter(
            employee=employee, effective_from__lte=effective_from
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))

        for threshold in existing_thresholds:
            threshold.effective_to = effective_from - datetime.timedelta(days=1)
            threshold.save()

        messages.success(
            self.request, "Employee deduction threshold created successfully."
        )
        return super().form_valid(form)


class EmployeeThresholdUpdateView(LoginRequiredMixin, UpdateView):
    model = EmployeeDeductionThreshold
    form_class = EmployeeDeductionThresholdForm
    template_name = "expenses/employee_threshold_form.html"
    success_url = reverse_lazy("expenses:threshold_list")

    def form_valid(self, form):
        messages.success(
            self.request, "Employee deduction threshold updated successfully."
        )
        return super().form_valid(form)


class EmployeeThresholdDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        threshold = get_object_or_404(EmployeeDeductionThreshold, pk=pk)
        threshold.soft_delete()

        messages.success(request, "Employee deduction threshold deleted successfully.")
        return redirect("expenses:threshold_list")


class AllInstallmentPlansView(LoginRequiredMixin, ListView):
    model = ExpenseInstallmentPlan
    template_name = 'expenses/all_installment_plans.html'
    context_object_name = 'plans'
    
    def get_queryset(self):
        return ExpenseInstallmentPlan.active.all().order_by(
            'expense__employee__last_name', 
            'expense__employee__first_name',
            'start_date'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        plans_by_employee = {}
        all_employees_total = Decimal('0.00')
        all_employees_processed = Decimal('0.00')
        
        for plan in context['plans']:
            employee = plan.expense.employee
            employee_name = f"{employee.first_name} {employee.last_name}"
            employee_id = employee.id
            
            if employee_id not in plans_by_employee:
                plans_by_employee[employee_id] = {
                    'employee': employee,
                    'employee_name': employee_name,
                    'plans': [],
                    'total_outstanding': Decimal('0.00'),
                    'total_processed': Decimal('0.00'),
                    'total_amount': Decimal('0.00'),
                    'department': getattr(employee, 'department', None),
                    'employee_id': getattr(employee, 'employee_id', None),
                    'email': employee.email
                }
            
            progress = get_installment_plan_progress(plan)
            
            plan_data = {
                'plan': plan,
                'expense': plan.expense,
                'expense_date': plan.expense.expense_date,
                'expense_type': plan.expense.expense_type,
                'expense_description': plan.expense.description,
                'total_amount': plan.total_amount,
                'installment_amount': plan.installment_amount,
                'start_date': plan.start_date,
                'remaining': progress['remaining_amount'],
                'processed': progress['processed_amount'],
                'progress_percentage': progress['progress_percentage'],
                'processed_installments': progress['processed_installments'],
                'total_installments': progress['total_installments']
            }
            
            plans_by_employee[employee_id]['plans'].append(plan_data)
            plans_by_employee[employee_id]['total_outstanding'] += progress['remaining_amount']
            plans_by_employee[employee_id]['total_processed'] += progress['processed_amount']
            plans_by_employee[employee_id]['total_amount'] += plan.total_amount
            
            all_employees_total += plan.total_amount
            all_employees_processed += progress['processed_amount']
        
        overall_progress = 0
        if all_employees_total > 0:
            overall_progress = (all_employees_processed / all_employees_total * 100)
        
        sorted_employees = sorted(plans_by_employee.values(), key=lambda x: x['employee_name'])
        
        context['plans_by_employee'] = sorted_employees
        context['overall_progress'] = overall_progress
        context['total_employees'] = len(plans_by_employee)
        context['total_amount'] = all_employees_total
        context['total_processed'] = all_employees_processed
        context['total_outstanding'] = all_employees_total - all_employees_processed
        
        return context


class InstallmentDetailView(LoginRequiredMixin, DetailView):
    model = ExpenseInstallmentPlan
    template_name = 'expenses/installment_detail.html'
    context_object_name = 'plan'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = self.object
        
        installments = ExpenseInstallment.active.filter(plan=plan).order_by('installment_number')
        
        progress = get_installment_plan_progress(plan)
        
        employee = plan.expense.employee
        employee_details = {
            'name': f"{employee.first_name} {employee.last_name}",
            'email': employee.email,
            'department': getattr(employee, 'department', None),
            'employee_id': getattr(employee, 'employee_id', None),
        }
        
        expense_details = {
            'id': plan.expense.id,
            'date': plan.expense.expense_date,
            'type': plan.expense.expense_type,
            'description': plan.expense.description,
            'total_amount': plan.expense.total_amount,
            'status': plan.expense.status,
            'payment_status': plan.expense.payment_status,
            'payroll_status': plan.expense.payroll_status,
        }
        
        context['installments'] = installments
        context['progress'] = progress
        context['employee'] = employee_details
        context['expense'] = expense_details
        
        return context


class BatchApprovalView(LoginRequiredMixin, FormView):
    form_class = ExpenseBatchApprovalForm
    template_name = 'expenses/batch_approval.html'
    success_url = reverse_lazy('expenses:expense_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['expenses'].queryset = Expense.active.filter(
            status=ExpenseStatus.UNDER_REVIEW.value
        )
        return form
    
    def form_valid(self, form):
        expenses = form.cleaned_data['expenses']
        notes = form.cleaned_data.get('notes', '')
        
        approved_count = 0
        for expense in expenses:
            expense.status = ExpenseStatus.APPROVED.value
            expense.approved_by = self.request.user
            expense.approved_date = timezone.now()
            
            if expense.add_to_payroll:
                expense.payroll_status = PayrollStatus.PENDING_PAYROLL_PROCESSING.value
                
            expense.save()
            
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action="Expense approved in batch",
                user=self.request.user,
                previous_state={'status': ExpenseStatus.UNDER_REVIEW.value},
                current_state={'status': ExpenseStatus.APPROVED.value},
                notes=notes
            )
            
            approved_count += 1
        
        messages.success(self.request, f'{approved_count} expenses approved successfully.')
        return super().form_valid(form)


class BatchDisbursementView(LoginRequiredMixin, FormView):
    form_class = ExpenseBatchDisbursementForm
    template_name = 'expenses/batch_disbursement.html'
    success_url = reverse_lazy('expenses:expense_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['expenses'].queryset = Expense.active.filter(
            status=ExpenseStatus.APPROVED.value,
            payment_status=PaymentStatus.PENDING.value
        )
        return form
    
    def form_valid(self, form):
        expenses = form.cleaned_data['expenses']
        disbursement_date = form.cleaned_data['disbursement_date']
        payment_method = form.cleaned_data['payment_method']
        notes = form.cleaned_data.get('notes', '')
        
        disbursed_count = 0
        for expense in expenses:
            expense.payment_status = PaymentStatus.PAID.value
            expense.payment_date = disbursement_date
            expense.payment_method = payment_method
            expense.save()
            
            ExpenseAuditTrail.objects.create(
                expense=expense,
                action="Expense disbursed in batch",
                user=self.request.user,
                previous_state={'payment_status': PaymentStatus.PENDING.value},
                current_state={
                    'payment_status': PaymentStatus.PAID.value,
                    'payment_date': str(disbursement_date),
                    'payment_method': payment_method
                },
                notes=notes
            )
            
            disbursed_count += 1
        
        messages.success(self.request, f'{disbursed_count} expenses disbursed successfully.')
        return super().form_valid(form)


class PayrollProcessingView(LoginRequiredMixin, ListView):
    template_name = 'expenses/payroll_processing.html'
    context_object_name = 'pending_expenses'
    
    def get_queryset(self):
        return Expense.active.filter(
            status=ExpenseStatus.APPROVED.value,
            add_to_payroll=True,
            payroll_status=PayrollStatus.PENDING_PAYROLL_PROCESSING.value
        ).order_by('employee__last_name', 'employee__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        expenses_by_employee = {}
        for expense in context['pending_expenses']:
            employee_name = f"{expense.employee.first_name} {expense.employee.last_name}"
            if employee_name not in expenses_by_employee:
                expenses_by_employee[employee_name] = {
                    'employee': expense.employee,
                    'expenses': [],
                    'total_additions': Decimal('0.00'),
                    'total_deductions': Decimal('0.00')
                }
            
            if expense.payment_status == PaymentStatus.PAID_BY_EMPLOYEE.value:
                expenses_by_employee[employee_name]['total_additions'] += expense.total_amount
            else:
                expenses_by_employee[employee_name]['total_deductions'] += expense.total_amount
                
            expenses_by_employee[employee_name]['expenses'].append(expense)
        
        default_threshold = ExpenseDeductionThreshold.get_current_threshold()
        
        employee_thresholds = {}
        for employee_threshold in EmployeeDeductionThreshold.active.filter(
            employee__in=[data['employee'] for data in expenses_by_employee.values()],
            effective_from__lte=timezone.now().date()
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=timezone.now().date())
        ):
            employee_thresholds[employee_threshold.employee.id] = employee_threshold.threshold_amount
        
        for employee_data in expenses_by_employee.values():
            employee_id = employee_data['employee'].id
            threshold = employee_thresholds.get(employee_id, default_threshold.threshold_amount if default_threshold else Decimal('5000.00'))
            
            total_deductions = employee_data['total_deductions']
            this_cycle_deduction, remaining_deduction = apply_threshold_based_deduction(
                total_deductions, threshold
            )
            
            employee_data['this_cycle_deduction'] = this_cycle_deduction
            employee_data['remaining_deduction'] = remaining_deduction
            employee_data['estimated_cycles'] = estimate_payroll_cycles(total_deductions, threshold)
        
        context['expenses_by_employee'] = expenses_by_employee
        context['default_threshold'] = default_threshold
        context['total_pending_expenses'] = context['pending_expenses'].count()
        context['total_pending_amount'] = sum(
            (e.total_amount for e in context['pending_expenses']), 
            Decimal('0.00')
        )
        
        return context

class ExpenseReportView(LoginRequiredMixin, FormView):
    form_class = ExpenseReportForm
    template_name = 'expenses/report_form.html'

    def form_valid(self, form):
        report_type = form.cleaned_data['report_type']
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        include_details = form.cleaned_data.get('include_details', True)
        export_format = form.cleaned_data.get('export_format', 'html')

        queryset = Expense.active.all()

        if date_from:
            queryset = queryset.filter(date_incurred__gte=date_from)

        if date_to:
            queryset = queryset.filter(date_incurred__lte=date_to)

        if report_type == 'category':
            report_data = generate_category_report(queryset, include_details)
            report_title = "Expense Report by Category"
        elif report_type == 'department':
            report_data = generate_department_report(queryset, include_details)
            report_title = "Expense Report by Department"
        elif report_type == 'employee':
            report_data = generate_employee_report(queryset, include_details)
            report_title = "Expense Report by Employee"
        elif report_type == 'status':
            report_data = generate_status_report(queryset, include_details)
            report_title = "Expense Report by Status"
        else:
            messages.error(self.request, 'Invalid report type.')
            return self.form_invalid(form)

        context = {
            'report_title': report_title,
            'report_type': report_type,
            'date_from': date_from,
            'date_to': date_to,
            'report_data': report_data,
            'include_details': include_details,
        }

        if export_format == 'html':
            return render(self.request, 'expenses/report_result.html', context)
        elif export_format == 'csv':
            return export_report_as_csv(report_data, report_title, include_details)
        elif export_format == 'excel':
            excel_response = export_report_as_excel(report_data, report_title, include_details)
            if excel_response:
                return excel_response
            messages.error(self.request, "Excel export requires xlwt module.")
            return redirect("expenses:report")
        elif export_format == 'pdf':
            pdf_response = export_report_as_pdf(report_data, report_title, include_details)
            if pdf_response:
                return pdf_response
            messages.error(self.request, "PDF export requires reportlab module.")
            return redirect("expenses:report")

        messages.error(self.request, 'Invalid export format.')
        return self.form_invalid(form)


class ExpenseExportView(LoginRequiredMixin, FormView):
    form_class = ExpenseExportForm
    template_name = "expenses/export_form.html"

    def form_valid(self, form):
        export_format = form.cleaned_data["export_format"]
        include_details = form.cleaned_data.get("include_details", True)
        include_audit_trail = form.cleaned_data.get("include_audit_trail", False)
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")

        queryset = Expense.active.all()

        if date_from:
            queryset = queryset.filter(date_incurred__gte=date_from)

        if date_to:
            queryset = queryset.filter(date_incurred__lte=date_to)

        if export_format == "csv":
            return export_expenses_as_csv(
                queryset, include_details, include_audit_trail
            )
        elif export_format == "excel":
            excel_response = export_expenses_as_excel(
                queryset, include_details, include_audit_trail
            )
            if excel_response:
                return excel_response
            messages.error(self.request, "Excel export requires xlwt module.")
            return redirect("expenses:export")
        elif export_format == "pdf":
            pdf_response = export_expenses_as_pdf(
                queryset, include_details, include_audit_trail
            )
            if pdf_response:
                return pdf_response
            messages.error(self.request, "PDF export requires reportlab module.")
            return redirect("expenses:export")

        messages.error(self.request, "Invalid export format.")
        return self.form_invalid(form)


class ExpenseSearchView(LoginRequiredMixin, FormView):
    form_class = ExpenseSearchForm
    template_name = "expenses/search_form.html"

    def form_valid(self, form):
        search_term = form.cleaned_data["search_term"]
        search_in = form.cleaned_data["search_in"]

        queryset = Expense.active.all()

        filters = Q()
        if "reference" in search_in:
            filters |= Q(reference__icontains=search_term)

        if "employee" in search_in:
            filters |= Q(employee__first_name__icontains=search_term)
            filters |= Q(employee__last_name__icontains=search_term)

        if "description" in search_in:
            filters |= Q(description__icontains=search_term)

        if "notes" in search_in:
            filters |= Q(notes__icontains=search_term)

        results = queryset.filter(filters).distinct()

        context = {
            "form": form,
            "search_term": search_term,
            "results": results,
            "count": results.count(),
        }

        return render(self.request, "expenses/search_results.html", context)

class ExpenseBulkActionView(LoginRequiredMixin, View):
    def post(self, request):
        form = ExpenseBulkActionForm(request.POST)

        if form.is_valid():
            action = form.cleaned_data["action"]
            reason = form.cleaned_data.get("reason", "")
            expense_ids = request.POST.getlist("expense_ids")

            if not expense_ids:
                messages.error(request, "No expenses selected.")
                return redirect("expenses:expense_list")

            expenses = Expense.active.filter(id__in=expense_ids)

            if action == "approve":
                count = 0
                for expense in expenses:
                    if expense.status == ExpenseStatus.UNDER_REVIEW.value:
                        expense.status = ExpenseStatus.APPROVED.value
                        expense.approved_by = request.user
                        expense.approved_date = timezone.now()

                        if expense.add_to_payroll:
                            expense.payroll_status = (
                                PayrollStatus.PENDING_PAYROLL_PROCESSING.value
                            )

                        expense.save()

                        ExpenseAuditTrail.objects.create(
                            expense=expense,
                            action="Expense approved in bulk",
                            user=request.user,
                            previous_state={"status": ExpenseStatus.UNDER_REVIEW.value},
                            current_state={"status": ExpenseStatus.APPROVED.value},
                        )

                        count += 1

                messages.success(request, f"{count} expenses approved successfully.")

            elif action == "reject":
                if not reason:
                    messages.error(request, "Reason is required for rejection.")
                    return redirect("expenses:expense_list")

                count = 0
                for expense in expenses:
                    if expense.status == ExpenseStatus.UNDER_REVIEW.value:
                        expense.status = ExpenseStatus.REJECTED.value
                        expense.rejected_by = request.user
                        expense.rejected_date = timezone.now()
                        expense.rejection_reason = reason
                        expense.save()

                        ExpenseAuditTrail.objects.create(
                            expense=expense,
                            action="Expense rejected in bulk",
                            user=request.user,
                            previous_state={"status": ExpenseStatus.UNDER_REVIEW.value},
                            current_state={"status": ExpenseStatus.REJECTED.value},
                            notes=reason,
                        )

                        count += 1

                messages.success(request, f"{count} expenses rejected successfully.")

            elif action == "delete":
                count = 0
                for expense in expenses:
                    if expense.status in [
                        ExpenseStatus.DRAFT.value,
                        ExpenseStatus.REJECTED.value,
                    ]:
                        expense.soft_delete()

                        ExpenseAuditTrail.objects.create(
                            expense=expense,
                            action="Expense deleted in bulk",
                            user=request.user,
                            previous_state={"status": expense.status},
                            current_state={"status": "DELETED"},
                        )

                        count += 1

                messages.success(request, f"{count} expenses deleted successfully.")

            else:
                messages.error(request, "Invalid action.")
        else:
            for error in form.errors.values():
                messages.error(request, error)

        return redirect("expenses:expense_list")

class ExpenseQuickbooksSyncView(LoginRequiredMixin, FormView):
    form_class = ExpenseQuickbooksSyncForm
    template_name = "expenses/quickbooks_sync_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        expense_id = self.kwargs.get("pk")
        if expense_id:
            expense = get_object_or_404(Expense, pk=expense_id)
            kwargs["expense"] = expense
        return kwargs

    def form_valid(self, form):
        expense_id = self.kwargs.get("pk")
        expense = get_object_or_404(Expense, pk=expense_id)

        expense.expense_account = form.cleaned_data["expense_account"]
        expense.cost_center = form.cleaned_data.get("cost_center", "")
        expense.tax_category = form.cleaned_data.get("tax_category", "")
        expense.is_reimbursable = form.cleaned_data.get("is_reimbursable", False)
        expense.is_taxable_benefit = form.cleaned_data.get("is_taxable_benefit", False)
        expense.save()

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action="QuickBooks sync settings updated",
            user=self.request.user,
            current_state={
                "expense_account": expense.expense_account,
                "cost_center": expense.cost_center,
                "tax_category": expense.tax_category,
            },
        )

        messages.success(self.request, "QuickBooks sync settings updated successfully.")
        return redirect("expenses:expense_detail", pk=expense.pk)


class ExpenseNotesView(LoginRequiredMixin, FormView):
    form_class = ExpenseNotesForm
    template_name = "expenses/notes_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        expense_id = self.kwargs.get("pk")
        if expense_id:
            expense = get_object_or_404(Expense, pk=expense_id)
            kwargs["initial"] = {"notes": expense.notes}
        return kwargs

    def form_valid(self, form):
        expense_id = self.kwargs.get("pk")
        expense = get_object_or_404(Expense, pk=expense_id)

        old_notes = expense.notes
        new_notes = form.cleaned_data["notes"]

        expense.notes = new_notes
        expense.save()

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action="Notes updated",
            user=self.request.user,
            previous_state={"notes": old_notes},
            current_state={"notes": new_notes},
        )

        messages.success(self.request, "Notes updated successfully.")
        return redirect("expenses:expense_detail", pk=expense.pk)


class ExpenseDisbursementView(LoginRequiredMixin, FormView):
    form_class = ExpenseDisbursementForm
    template_name = "expenses/disbursement_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense_id = self.kwargs.get("pk")
        expense = get_object_or_404(Expense, pk=expense_id)
        context["expense"] = expense
        return context

    def form_valid(self, form):
        expense_id = self.kwargs.get("pk")
        expense = get_object_or_404(Expense, pk=expense_id)

        if expense.status != ExpenseStatus.APPROVED.value:
            messages.error(self.request, "Only approved expenses can be disbursed.")
            return redirect("expenses:expense_detail", pk=expense.pk)

        if expense.payment_status != PaymentStatus.PENDING.value:
            messages.error(self.request, "This expense has already been disbursed.")
            return redirect("expenses:expense_detail", pk=expense.pk)

        disbursement_date = form.cleaned_data["disbursement_date"]
        disbursement_reference = form.cleaned_data["disbursement_reference"]
        payment_method = form.cleaned_data["payment_method"]
        notes = form.cleaned_data.get("notes", "")

        expense.payment_status = PaymentStatus.PAID.value
        expense.payment_date = disbursement_date
        expense.payment_reference = disbursement_reference
        expense.payment_method = payment_method
        expense.save()

        ExpenseAuditTrail.objects.create(
            expense=expense,
            action="Expense disbursed",
            user=self.request.user,
            previous_state={"payment_status": PaymentStatus.PENDING.value},
            current_state={
                "payment_status": PaymentStatus.PAID.value,
                "payment_date": str(disbursement_date),
                "payment_reference": disbursement_reference,
                "payment_method": payment_method,
            },
            notes=notes,
        )

        messages.success(self.request, "Expense disbursed successfully.")
        return redirect("expenses:expense_detail", pk=expense.pk)
