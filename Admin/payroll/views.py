# Python standard library imports
import calendar
import csv
import io
import json
import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template, render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (CreateView, DetailView, ListView, TemplateView,
                                 UpdateView, View)

from xhtml2pdf import pisa
import xlsxwriter
from accounts.models import CustomUser, Department, Role, SystemConfiguration
from attendance.models import MonthlyAttendanceSummary
from employees.models import EmployeeProfile
from attendance.utils import EmployeeDataManager

from .forms import PayrollPeriodForm
from .models import (PayrollBankTransfer, PayrollDepartmentSummary,
                    PayrollPeriod, Payslip, SalaryAdvance,
                    calculate_employee_year_to_date, generate_payroll_comparison_report,
                    generate_tax_report, initialize_payroll_system,
                    log_payroll_activity, process_monthly_advance_deductions,
                    validate_employee_payroll_eligibility,
                    validate_payroll_system_integrity)
from .utils import (PayrollAdvanceCalculator, PayrollCacheManager,
                   PayrollCalculator, PayrollDataProcessor,
                   PayrollDeductionCalculator, PayrollTaxCalculator,
                   PayrollUtilityHelper, PayrollValidationHelper,
                   safe_payroll_calculation)

logger = logging.getLogger(__name__)

class PayrollPeriodViews:
    class PayrollPeriodListView(LoginRequiredMixin, ListView):
        model = PayrollPeriod
        template_name = "payroll/period_list.html"
        context_object_name = "periods"
        paginate_by = 10

        def get_queryset(self):
            queryset = PayrollPeriod.objects.all().order_by("-year", "-month")

            search_query = self.request.GET.get("search", "")
            if search_query:
                queryset = queryset.filter(
                    Q(period_name__icontains=search_query)
                    | Q(year__icontains=search_query)
                    | Q(month__icontains=search_query)
                    | Q(status__icontains=search_query)
                )

            status_filter = self.request.GET.get("status", "")
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            year_filter = self.request.GET.get("year", "")
            if year_filter and year_filter.isdigit():
                queryset = queryset.filter(year=int(year_filter))

            return queryset

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            years = (
                PayrollPeriod.objects.values_list("year", flat=True)
                .distinct()
                .order_by("-year")
            )
            statuses = [status[0] for status in PayrollPeriod.STATUS_CHOICES]

            current_year, current_month = (
                PayrollUtilityHelper.get_current_payroll_period()
            )

            context.update(
                {
                    "years": years,
                    "statuses": statuses,
                    "current_year": current_year,
                    "current_month": current_month,
                    "search_query": self.request.GET.get("search", ""),
                    "status_filter": self.request.GET.get("status", ""),
                    "year_filter": self.request.GET.get("year", ""),
                    "page_title": "Payroll Periods",
                    "can_create_period": True,
                    "can_process_payroll": True,
                    "can_approve_payroll": True,
                }
            )

            return context

    class PayrollPeriodCreateView(LoginRequiredMixin, CreateView):
        model = PayrollPeriod
        form_class = PayrollPeriodForm
        template_name = "payroll/period_create.html"
        success_url = reverse_lazy("payroll:period_list")

        def get_initial(self):
            current_year, current_month = (
                PayrollUtilityHelper.get_current_payroll_period()
            )

            start_date = date(current_year, current_month, 1)
            end_date = date(
                current_year,
                current_month,
                calendar.monthrange(current_year, current_month)[1],
            )
            processing_date = PayrollUtilityHelper.get_payroll_processing_date()

            return {
                "year": current_year,
                "month": current_month,
                "start_date": start_date,
                "end_date": end_date,
                "processing_date": processing_date,
                "cutoff_date": end_date,
            }

        def form_valid(self, form):
            year = form.cleaned_data["year"]
            month = form.cleaned_data["month"]

            if PayrollPeriod.objects.filter(year=year, month=month).exists():
                form.add_error(
                    None,
                    f"Payroll period for {calendar.month_name[month]} {year} already exists.",
                )
                return self.form_invalid(form)

            form.instance.created_by = self.request.user
            form.instance.period_name = f"{calendar.month_name[month]} {year}"
            form.instance.total_working_days = (
                PayrollDataProcessor.get_working_days_in_month(year, month)
            )

            with transaction.atomic():
                response = super().form_valid(form)

                active_employees = CustomUser.active.filter(status="ACTIVE")
                missing_summaries = []

                for employee in active_employees:
                    try:
                        MonthlyAttendanceSummary.generate_for_employee_month(
                            employee, year, month
                        )
                    except Exception as e:
                        missing_summaries.append(f"{employee.employee_code}: {str(e)}")

                if missing_summaries:
                    logger.warning(
                        f"Missing attendance summaries: {'; '.join(missing_summaries)}"
                    )

                log_payroll_activity(
                    self.request.user,
                    "PERIOD_CREATED",
                    {
                        "period_id": str(self.object.id),
                        "year": year,
                        "month": month,
                        "total_employees": active_employees.count(),
                        "missing_summaries_count": len(missing_summaries),
                    },
                )

                messages.success(
                    self.request,
                    f"Payroll period for {calendar.month_name[month]} {year} created successfully.",
                )
                return response

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["page_title"] = "Create Payroll Period"

            years = list(range(date.today().year - 2, date.today().year + 2))
            months = [(i, calendar.month_name[i]) for i in range(1, 13)]

            context.update(
                {
                    "years": years,
                    "months": months,
                }
            )

            return context

    class PayrollPeriodDetailView(LoginRequiredMixin, DetailView):
        model = PayrollPeriod
        template_name = 'payroll/period_detail.html'
        context_object_name = 'period'

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            period = self.object

            payslips = Payslip.objects.filter(payroll_period=period)
            payslips_by_status = {
                'DRAFT': payslips.filter(status='DRAFT').count(),
                'CALCULATED': payslips.filter(status='CALCULATED').count(),
                'APPROVED': payslips.filter(status='APPROVED').count(),
                'PAID': payslips.filter(status='PAID').count(),
                'CANCELLED': payslips.filter(status='CANCELLED').count(),
            }

            departments = Department.objects.filter(is_active=True)
            department_summaries = {}

            for dept in departments:
                dept_payslips = payslips.filter(employee__department=dept)
                if dept_payslips.exists():
                    dept_summary, created = PayrollDepartmentSummary.objects.get_or_create(
                        payroll_period=period,
                        department=dept
                    )

                    if created or dept_summary.employee_count == 0:
                        dept_summary.calculate_summary()

                    department_summaries[dept.name] = {
                        'summary': dept_summary,
                        'payslips_count': dept_payslips.count(),
                        'calculated_count': dept_payslips.filter(status__in=['CALCULATED', 'APPROVED', 'PAID']).count(),
                        'approved_count': dept_payslips.filter(status__in=['APPROVED', 'PAID']).count(),
                    }

            roles = Role.objects.filter(is_active=True)
            role_summaries = {}

            for role in roles:
                role_payslips = payslips.filter(employee__role=role)
                if role_payslips.exists():
                    role_summaries[role.name] = {
                        'payslips_count': role_payslips.count(),
                        'calculated_count': role_payslips.filter(status__in=['CALCULATED', 'APPROVED', 'PAID']).count(),
                        'approved_count': role_payslips.filter(status__in=['APPROVED', 'PAID']).count(),
                        'total_gross': role_payslips.filter(status__in=['CALCULATED', 'APPROVED', 'PAID']).aggregate(Sum('gross_salary'))['gross_salary__sum'] or 0,
                        'total_net': role_payslips.filter(status__in=['CALCULATED', 'APPROVED', 'PAID']).aggregate(Sum('net_salary'))['net_salary__sum'] or 0,
                    }

            bank_transfers = PayrollBankTransfer.objects.filter(payroll_period=period)

            context.update({
                'page_title': f'Payroll Period: {period.period_name}',
                'payslips_count': payslips.count(),
                'payslips_by_status': payslips_by_status,
                'department_summaries': department_summaries,
                'role_summaries': role_summaries,
                'bank_transfers': bank_transfers,
                'can_process_payroll': period.status in ['DRAFT', 'PROCESSING'],
                'can_approve_payroll': period.status == 'COMPLETED',
                'can_generate_bank_file': period.status == 'APPROVED' and payslips.filter(status='APPROVED').exists(),
                'can_edit_period': period.status in ['DRAFT', 'PROCESSING'],
                'can_calculate_payslips': period.status in ['DRAFT', 'PROCESSING'],
                'can_approve_payslips': period.status in ['PROCESSING', 'COMPLETED'],
            })

            return context

    class PayrollPeriodUpdateView(LoginRequiredMixin, UpdateView):
        model = PayrollPeriod
        template_name = 'payroll/period_update.html'
        fields = ['start_date', 'end_date', 'processing_date', 'cutoff_date']

        def get_success_url(self):
            return reverse('payroll:period_detail', kwargs={'pk': self.object.pk})

        def form_valid(self, form):
            period = self.object

            if period.status not in ['DRAFT', 'PROCESSING']:
                messages.error(self.request, f"Cannot update payroll period in {period.status} status.")
                return HttpResponseRedirect(self.get_success_url())

            response = super().form_valid(form)

            log_payroll_activity(
                self.request.user,
                "PERIOD_UPDATED",
                {
                    "period_id": str(self.object.id),
                    "year": period.year,
                    "month": period.month,
                    "fields_updated": list(form.changed_data),
                },
            )

            messages.success(self.request, f"Payroll period {period.period_name} updated successfully.")
            return response

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['page_title'] = f'Update Payroll Period: {self.object.period_name}'
            return context

    class PayrollPeriodProcessView(LoginRequiredMixin, View):
        def post(self, request, pk):
            period = get_object_or_404(PayrollPeriod, pk=pk)

            if period.status not in ['DRAFT', 'PROCESSING']:
                messages.error(request, f"Cannot process payroll period in {period.status} status.")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            try:
                with transaction.atomic():
                    period.status = 'PROCESSING'
                    period.save(update_fields=['status'])

                    active_employees = CustomUser.active.filter(status="ACTIVE")

                    calculated_payslips = Payslip.objects.bulk_calculate(period, active_employees)

                    messages.success(request, f"Processed {len(calculated_payslips)} payslips successfully.")

                    log_payroll_activity(
                        request.user,
                        "PERIOD_PROCESSING",
                        {
                            "period_id": str(period.id),
                            "year": period.year,
                            "month": period.month,
                            "payslips_calculated": len(calculated_payslips),
                        },
                    )

                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            except Exception as e:
                logger.error(f"Error processing payroll period {period.id}: {str(e)}")
                messages.error(request, f"Error processing payroll: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

    class PayrollPeriodApproveView(LoginRequiredMixin, View):
        def post(self, request, pk):
            period = get_object_or_404(PayrollPeriod, pk=pk)

            if period.status != 'COMPLETED':
                messages.error(request, f"Cannot approve payroll period in {period.status} status.")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            try:
                with transaction.atomic():
                    period.status = 'APPROVED'
                    period.approved_by = request.user
                    period.approved_at = timezone.now()
                    period.save(update_fields=['status', 'approved_by', 'approved_at'])

                    period.calculate_period_totals()

                    log_payroll_activity(
                        request.user,
                        "PERIOD_APPROVED",
                        {
                            "period_id": str(period.id),
                            "year": period.year,
                            "month": period.month,
                            "total_gross": float(period.total_gross_salary),
                            "total_net": float(period.total_net_salary),
                        },
                    )

                    messages.success(request, f"Payroll period {period.period_name} approved successfully.")

                    process_monthly_advance_deductions(period.year, period.month)

                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            except Exception as e:
                logger.error(f"Error approving payroll period {period.id}: {str(e)}")
                messages.error(request, f"Error approving payroll: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

    class PayrollPeriodCompleteView(LoginRequiredMixin, View):
        def post(self, request, pk):
            period = get_object_or_404(PayrollPeriod, pk=pk)

            if period.status != 'PROCESSING':
                messages.error(request, f"Cannot complete payroll period in {period.status} status.")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            try:
                with transaction.atomic():
                    period.mark_as_completed(request.user)

                    calculated_count = Payslip.objects.filter(
                        payroll_period=period, 
                        status__in=['CALCULATED', 'APPROVED']
                    ).count()

                    total_employees = CustomUser.active.filter(status="ACTIVE").count()

                    if calculated_count < total_employees * 0.9:
                        messages.warning(
                            request, 
                            f"Only {calculated_count} out of {total_employees} employees have calculated payslips."
                        )

                    messages.success(request, f"Payroll period {period.period_name} marked as completed.")

                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            except Exception as e:
                logger.error(f"Error completing payroll period {period.id}: {str(e)}")
                messages.error(request, f"Error completing payroll: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

    class PayrollPeriodCancelView(LoginRequiredMixin, View):
        def post(self, request, pk):
            period = get_object_or_404(PayrollPeriod, pk=pk)

            if period.status in ['PAID', 'CANCELLED']:
                messages.error(request, f"Cannot cancel payroll period in {period.status} status.")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            try:
                with transaction.atomic():
                    period.status = 'CANCELLED'
                    period.save(update_fields=['status'])

                    log_payroll_activity(
                        request.user,
                        "PERIOD_CANCELLED",
                        {
                            "period_id": str(period.id),
                            "year": period.year,
                            "month": period.month,
                        },
                    )

                    messages.success(request, f"Payroll period {period.period_name} cancelled successfully.")
                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

            except Exception as e:
                logger.error(f"Error cancelling payroll period {period.id}: {str(e)}")
                messages.error(request, f"Error cancelling payroll: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.pk}))

class PayslipViews:
    class PayslipListView(LoginRequiredMixin, ListView):
        model = Payslip
        template_name = 'payroll/payslip_list.html'
        context_object_name = 'payslips'
        paginate_by = 20

        def get_queryset(self):
            queryset = Payslip.objects.all().select_related('employee', 'payroll_period')

            period_id = self.request.GET.get('period_id')
            if period_id:
                queryset = queryset.filter(payroll_period_id=period_id)

            department_id = self.request.GET.get('department_id')
            if department_id:
                queryset = queryset.filter(employee__department_id=department_id)

            role_id = self.request.GET.get('role_id')
            if role_id:
                queryset = queryset.filter(employee__role_id=role_id)

            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            search_query = self.request.GET.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(employee__first_name__icontains=search_query) |
                    Q(employee__last_name__icontains=search_query) |
                    Q(employee__employee_code__icontains=search_query) |
                    Q(reference_number__icontains=search_query)
                )

            sort_by = self.request.GET.get('sort_by')
            if not sort_by:
                queryset = queryset.order_by('-payroll_period__year', '-payroll_period__month')
            else:
                sort_fields = sort_by.split(',')
                queryset = queryset.order_by(*sort_fields)

            return queryset

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            payslips = context['payslips']
            for payslip in payslips:
                profile = EmployeeDataManager.get_employee_profile(payslip.employee)
                payslip.employee_profile_id = profile.id
 
            periods = PayrollPeriod.objects.all().order_by('-year', '-month')
            departments = Department.objects.filter(is_active=True)
            roles = Role.objects.filter(is_active=True)
            statuses = [status[0] for status in Payslip.STATUS_CHOICES]

            context.update({
                'page_title': 'Payslips',
                'periods': periods,
                'departments': departments,
                'roles': roles,
                'statuses': statuses,
                'period_id': self.request.GET.get('period_id', ''),
                'department_id': self.request.GET.get('department_id', ''),
                'role_id': self.request.GET.get('role_id', ''),
                'status_filter': self.request.GET.get('status', ''),
                'search_query': self.request.GET.get('search', ''),
                'sort_by': self.request.GET.get('sort_by', '-payroll_period__year,-payroll_period__month'),
                'can_calculate_payslips': True,
                'can_approve_payslips': True,
            })

            return context

    class PayslipDetailView(LoginRequiredMixin, DetailView):
        model = Payslip
        template_name = 'payroll/payslip_detail.html'
        context_object_name = 'payslip'

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            payslip = self.object

            employee = payslip.employee
            profile = EmployeeDataManager.get_employee_profile(employee)
            monthly_summary = payslip.monthly_summary
            

            attendance_data = {}
            if monthly_summary:
                attendance_data = {
                    'working_days': monthly_summary.working_days,
                    'attended_days': monthly_summary.attended_days,
                    'absent_days': monthly_summary.absent_days,
                    'leave_days': monthly_summary.leave_days,
                    'late_arrivals': monthly_summary.late_days,
                    'early_departures': monthly_summary.early_days,
                    'overtime_hours': monthly_summary.total_overtime,
                    'attendance_percentage': monthly_summary.attendance_percentage,
                    'punctuality_score': monthly_summary.punctuality_score,
                }

            payslip_items = []

            earnings = [
                {"name": "Basic Salary", "amount": payslip.basic_salary},
                {"name": "Bonus 1", "amount": payslip.bonus_1},
                {"name": "Bonus 2", "amount": payslip.bonus_2},
                {"name": "Transport Allowance", "amount": payslip.transport_allowance},
                {"name": "Telephone Allowance", "amount": payslip.telephone_allowance},
                {"name": "Fuel Allowance", "amount": payslip.fuel_allowance},
                {"name": "Meal Allowance", "amount": payslip.meal_allowance},
                {"name": "Attendance Bonus", "amount": payslip.attendance_bonus},
                {"name": "Performance Bonus", "amount": payslip.performance_bonus},
                {"name": "Interim Allowance", "amount": payslip.interim_allowance},
                {"name": "Education Allowance", "amount": payslip.education_allowance},
                {"name": "Regular Overtime", "amount": payslip.regular_overtime},
                {"name": "Friday Overtime", "amount": payslip.friday_overtime},
                {"name": "Religious Pay", "amount": payslip.religious_pay},
                {"name": "Friday Salary", "amount": payslip.friday_salary},
                {"name": "Expense Reimbursements", "amount": payslip.expense_additions},
            ]

            deductions = [
                {'name': 'EPF Employee Contribution', 'amount': payslip.employee_epf_contribution},
                {'name': 'Leave Deduction', 'amount': payslip.leave_deduction},
                {'name': 'Late Penalty', 'amount': payslip.late_penalty},
                {'name': 'Lunch Violation Penalty', 'amount': payslip.lunch_violation_penalty},
                {'name': 'Advance Deduction', 'amount': payslip.advance_deduction},
                {'name': 'Income Tax', 'amount': payslip.income_tax},
                {'name': 'Expense Deductions', 'amount': payslip.expense_deductions},
            ]

            employer_contributions = [
                {'name': 'EPF Employer Contribution', 'amount': payslip.employer_epf_contribution},
                {'name': 'ETF Contribution', 'amount': payslip.etf_contribution},
            ]

            active_advances = SalaryAdvance.objects.filter(
                employee=employee, 
                status='ACTIVE',
                outstanding_amount__gt=0
            )

            context.update({
                'page_title': f'Payslip: {payslip.reference_number}',
                'employee': employee,
                'profile': profile,
                'attendance_data': attendance_data,
                'earnings': [e for e in earnings if e['amount'] > 0],
                'deductions': [d for d in deductions if d['amount'] > 0],
                'employer_contributions': employer_contributions,
                'active_advances': active_advances,
                'can_calculate': payslip.status == 'DRAFT',
                'can_approve': payslip.status == 'CALCULATED',
                'can_print': payslip.status in ['CALCULATED', 'APPROVED', 'PAID'],
                'can_email': payslip.status in ['APPROVED', 'PAID'],
            })

            return context

    class PayslipCalculateView(LoginRequiredMixin, View):
        def post(self, request, pk):
            payslip = get_object_or_404(Payslip, pk=pk)

            if payslip.status not in ['DRAFT']:
                messages.error(request, f"Cannot calculate payslip in {payslip.status} status.")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

            try:
                payslip.calculated_by = request.user
                payslip.calculate_payroll()

                messages.success(request, f"Payslip for {payslip.employee.get_full_name()} calculated successfully.")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

            except Exception as e:
                logger.error(f"Error calculating payslip {payslip.id}: {str(e)}")
                messages.error(request, f"Error calculating payslip: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

    class PayslipApproveView(LoginRequiredMixin, View):
        def post(self, request, pk):
            payslip = get_object_or_404(Payslip, pk=pk)

            if payslip.status != 'CALCULATED':
                messages.error(request, f"Cannot approve payslip in {payslip.status} status.")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

            try:
                payslip.approve(request.user)

                messages.success(request, f"Payslip for {payslip.employee.get_full_name()} approved successfully.")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

            except Exception as e:
                logger.error(f"Error approving payslip {payslip.id}: {str(e)}")
                messages.error(request, f"Error approving payslip: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:payslip_detail', kwargs={'pk': payslip.pk}))

    class BulkPayslipCalculateView(LoginRequiredMixin, View):
        def get(self, request):
            periods = PayrollPeriod.objects.filter(status__in=['DRAFT', 'PROCESSING']).order_by('-year', '-month')
            departments = Department.objects.filter(is_active=True)
            roles = Role.objects.filter(is_active=True)

            context = {
                'page_title': 'Bulk Calculate Payslips',
                'periods': periods,
                'departments': departments,
                'roles': roles,
            }

            return render(request, 'payroll/bulk_calculate.html', context)

        def post(self, request):
            period_id = request.POST.get('period_id')
            department_id = request.POST.get('department_id')
            role_id = request.POST.get('role_id')

            if not period_id:
                messages.error(request, "Payroll period is required.")
                return HttpResponseRedirect(reverse('payroll:bulk_calculate'))

            try:
                period = PayrollPeriod.objects.get(pk=period_id)

                if period.status not in ['DRAFT', 'PROCESSING']:
                    messages.error(request, f"Cannot calculate payslips for period in {period.status} status.")
                    return HttpResponseRedirect(reverse('payroll:bulk_calculate'))

                employees = CustomUser.active.filter(status="ACTIVE")

                if department_id:
                    employees = employees.filter(department_id=department_id)

                if role_id:
                    employees = employees.filter(role_id=role_id)

                with transaction.atomic():
                    calculated_payslips = Payslip.objects.bulk_calculate(period, employees)

                    log_payroll_activity(
                        request.user,
                        "BULK_PAYROLL_CALCULATED",
                        {
                            "period_id": str(period.id),
                            "total_employees": len(employees),
                            "calculated_count": len(calculated_payslips),
                        },
                    )

                    messages.success(request, f"Calculated {len(calculated_payslips)} payslips successfully.")

                    if period.status == 'DRAFT' and len(calculated_payslips) > 0:
                        period.status = 'PROCESSING'
                        period.save(update_fields=['status'])

                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.id}))

            except PayrollPeriod.DoesNotExist:
                messages.error(request, "Invalid payroll period.")
                return HttpResponseRedirect(reverse('payroll:bulk_calculate'))

            except Exception as e:
                logger.error(f"Error in bulk calculate: {str(e)}")
                messages.error(request, f"Error calculating payslips: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bulk_calculate'))

    class BulkPayslipApproveView(LoginRequiredMixin, View):
        def get(self, request):
            periods = PayrollPeriod.objects.filter(status__in=['PROCESSING', 'COMPLETED']).order_by('-year', '-month')
            departments = Department.objects.filter(is_active=True)
            roles = Role.objects.filter(is_active=True)

            context = {
                'page_title': 'Bulk Approve Payslips',
                'periods': periods,
                'departments': departments,
                'roles': roles,
            }

            return render(request, 'payroll/bulk_approve.html', context)

        def post(self, request):
            period_id = request.POST.get('period_id')
            department_id = request.POST.get('department_id')
            role_id = request.POST.get('role_id')

            if not period_id:
                messages.error(request, "Payroll period is required.")
                return HttpResponseRedirect(reverse('payroll:bulk_approve'))

            try:
                period = PayrollPeriod.objects.get(pk=period_id)

                if period.status not in ['PROCESSING', 'COMPLETED']:
                    messages.error(request, f"Cannot approve payslips for period in {period.status} status.")
                    return HttpResponseRedirect(reverse('payroll:bulk_approve'))

                employees = None

                if department_id or role_id:
                    employees = CustomUser.active.filter(status="ACTIVE")

                    if department_id:
                        employees = employees.filter(department_id=department_id)

                    if role_id:
                        employees = employees.filter(role_id=role_id)

                with transaction.atomic():
                    approved_count, failed_approvals = Payslip.objects.bulk_approve(period, request.user, employees)

                    if failed_approvals:
                        for failure in failed_approvals[:5]:
                            messages.warning(request, failure)

                        if len(failed_approvals) > 5:
                            messages.warning(request, f"... and {len(failed_approvals) - 5} more failures.")

                    messages.success(request, f"Approved {approved_count} payslips successfully.")

                    if period.status == 'PROCESSING' and approved_count > 0:
                        calculated_count = Payslip.objects.filter(
                            payroll_period=period, 
                            status='CALCULATED'
                        ).count()

                        if calculated_count == 0:
                            period.mark_as_completed(request.user)
                            messages.success(request, f"Payroll period {period.period_name} marked as completed.")

                    return HttpResponseRedirect(reverse('payroll:period_detail', kwargs={'pk': period.id}))

            except PayrollPeriod.DoesNotExist:
                messages.error(request, "Invalid payroll period.")
                return HttpResponseRedirect(reverse('payroll:bulk_approve'))

            except Exception as e:
                logger.error(f"Error in bulk approve: {str(e)}")
                messages.error(request, f"Error approving payslips: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bulk_approve'))

    class EmployeePayslipHistoryView(LoginRequiredMixin, ListView):
        model = Payslip
        template_name = 'payroll/employee_payslip_history.html'
        context_object_name = 'payslips'
        paginate_by = 12

        def get_queryset(self):
            employee_id = self.kwargs.get('employee_id')
            employee = get_object_or_404(CustomUser, pk=employee_id)

            queryset = Payslip.objects.filter(employee=employee).select_related('payroll_period')

            year = self.request.GET.get('year')
            if year and year.isdigit():
                queryset = queryset.filter(payroll_period__year=int(year))

            status = self.request.GET.get('status')
            if status:
                queryset = queryset.filter(status=status)

            return queryset.order_by('-payroll_period__year', '-payroll_period__month')

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)

            employee_id = self.kwargs.get('employee_id')
            employee = get_object_or_404(CustomUser, pk=employee_id)
            profile = EmployeeDataManager.get_employee_profile(employee)

            years = Payslip.objects.filter(employee=employee).values_list(
                'payroll_period__year', flat=True
            ).distinct().order_by('-payroll_period__year')

            statuses = [status[0] for status in Payslip.STATUS_CHOICES]

            ytd_data = None
            current_year = datetime.now().year

            if years and current_year in years:
                ytd_result = calculate_employee_year_to_date(employee.id, current_year)
                if ytd_result['status'] == 'success':
                    ytd_data = ytd_result['ytd_data']

            active_advances = SalaryAdvance.objects.filter(
                employee=employee, 
                status='ACTIVE',
                outstanding_amount__gt=0
            )

            context.update({
                'page_title': f'Payslip History: {employee.get_full_name()}',
                'employee': employee,
                'profile': profile,
                'years': years,
                'statuses': statuses,
                'year_filter': self.request.GET.get('year', ''),
                'status_filter': self.request.GET.get('status', ''),
                'ytd_data': ytd_data,
                'active_advances': active_advances,
                'can_view_detail': True,
                'can_print_payslip': True,
            })

            return context

    class EmployeePayslipSelectView(LoginRequiredMixin, TemplateView):
        template_name = 'payroll/employee_payslip_select.html'

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context['employees'] = CustomUser.active.filter(status="ACTIVE").order_by('first_name', 'last_name')
            return context

        def post(self, request):
            employee_id = request.POST.get('employee_id')
            if employee_id:
                try:
                    uuid_obj = uuid.UUID(employee_id)
                    return HttpResponseRedirect(reverse('payroll:employee_payslip_history', kwargs={'employee_id': employee_id}))
                except ValueError:
                    messages.error(request, "Invalid employee ID format.")
                    return self.get(request)
            messages.error(request, "Please select an employee.")
            return self.get(request)

    class PrintPayslipView(LoginRequiredMixin, DetailView):
        model = Payslip
        template_name = 'payroll/print_payslip.html'
        context_object_name = 'payslip'

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            payslip = self.object

            employee = payslip.employee
            profile = EmployeeDataManager.get_employee_profile(employee)

            earnings = [
                {"name": "Basic Salary", "amount": payslip.basic_salary},
                {"name": "Bonus 1", "amount": payslip.bonus_1},
                {"name": "Bonus 2", "amount": payslip.bonus_2},
                {"name": "Transport Allowance", "amount": payslip.transport_allowance},
                {"name": "Telephone Allowance", "amount": payslip.telephone_allowance},
                {"name": "Fuel Allowance", "amount": payslip.fuel_allowance},
                {"name": "Meal Allowance", "amount": payslip.meal_allowance},
                {"name": "Attendance Bonus", "amount": payslip.attendance_bonus},
                {"name": "Performance Bonus", "amount": payslip.performance_bonus},
                {"name": "Interim Allowance", "amount": payslip.interim_allowance},
                {"name": "Education Allowance", "amount": payslip.education_allowance},
                {"name": "Regular Overtime", "amount": payslip.regular_overtime},
                {"name": "Friday Overtime", "amount": payslip.friday_overtime},
                {"name": "Religious Pay", "amount": payslip.religious_pay},
                {"name": "Friday Salary", "amount": payslip.friday_salary},
                {"name": "Expense Reimbursements", "amount": payslip.expense_additions},
            ]

            deductions = [
                {
                    "name": "EPF Employee Contribution",
                    "amount": payslip.employee_epf_contribution,
                },
                {"name": "Leave Deduction", "amount": payslip.leave_deduction},
                {"name": "Late Penalty", "amount": payslip.late_penalty},
                {
                    "name": "Lunch Violation Penalty",
                    "amount": payslip.lunch_violation_penalty,
                },
                {"name": "Advance Deduction", "amount": payslip.advance_deduction},
                {"name": "Income Tax", "amount": payslip.income_tax},
                {"name": "Expense Deductions", "amount": payslip.expense_deductions},
            ]

            context.update({
                'page_title': f'Print Payslip: {payslip.reference_number}',
                'employee': employee,
                'profile': profile,
                'earnings': [e for e in earnings if e['amount'] > 0],
                'deductions': [d for d in deductions if d['amount'] > 0],
                'company_name': SystemConfiguration.get_setting('COMPANY_NAME', 'Company Name'),
                'company_address': SystemConfiguration.get_setting('COMPANY_ADDRESS', 'Company Address'),
                'company_phone': SystemConfiguration.get_setting('COMPANY_PHONE', 'Company Phone'),
                'company_email': SystemConfiguration.get_setting('COMPANY_EMAIL', 'Company Email'),
                'print_date': timezone.now().date(),
            })

            return context

class SalaryAdvanceViews:
    class SalaryAdvanceListView(LoginRequiredMixin, ListView):
        model = SalaryAdvance
        template_name = 'payroll/advance_list.html'
        context_object_name = 'advances'
        paginate_by = 20
        
        def get_queryset(self):
            queryset = SalaryAdvance.objects.all().select_related('employee', 'requested_by', 'approved_by')
            
            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            department_id = self.request.GET.get('department_id')
            if department_id:
                queryset = queryset.filter(employee__department_id=department_id)
            
            advance_type = self.request.GET.get('advance_type')
            if advance_type:
                queryset = queryset.filter(advance_type=advance_type)
            
            date_from = self.request.GET.get('date_from')
            if date_from:
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(requested_date__gte=date_from)
                except ValueError:
                    pass
            
            date_to = self.request.GET.get('date_to')
            if date_to:
                try:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(requested_date__lte=date_to)
                except ValueError:
                    pass
            
            search_query = self.request.GET.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(employee__first_name__icontains=search_query) |
                    Q(employee__last_name__icontains=search_query) |
                    Q(employee__employee_code__icontains=search_query) |
                    Q(reference_number__icontains=search_query)
                )
            
            sort_by = self.request.GET.get('sort_by', '-requested_date')
            queryset = queryset.order_by(sort_by)
            
            return queryset
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            
            departments = Department.objects.filter(is_active=True)
            statuses = [status[0] for status in SalaryAdvance.STATUS_CHOICES]
            advance_types = [advance_type[0] for advance_type in SalaryAdvance.ADVANCE_TYPES]
            
            pending_count = SalaryAdvance.objects.filter(status='PENDING').count()
            active_count = SalaryAdvance.objects.filter(status='ACTIVE').count()
            completed_count = SalaryAdvance.objects.filter(status='COMPLETED').count()
            
            context.update({
                'page_title': 'Salary Advances',
                'departments': departments,
                'statuses': statuses,
                'advance_types': advance_types,
                'status_filter': self.request.GET.get('status', ''),
                'department_id': self.request.GET.get('department_id', ''),
                'advance_type': self.request.GET.get('advance_type', ''),
                'date_from': self.request.GET.get('date_from', ''),
                'date_to': self.request.GET.get('date_to', ''),
                'search_query': self.request.GET.get('search', ''),
                'sort_by': self.request.GET.get('sort_by', '-requested_date'),
                'pending_count': pending_count,
                'active_count': active_count,
                'completed_count': completed_count,
                'can_create_advance': True,
                'can_approve_advance': True,
                'can_bulk_approve': pending_count > 0,
            })
            
            return context
    
    class SalaryAdvanceCreateView(LoginRequiredMixin, CreateView):
        model = SalaryAdvance
        template_name = 'payroll/advance_create.html'
        fields = ['employee', 'advance_type', 'amount', 'installments', 'reason', 'purpose_details']
        
        def get_form(self, form_class=None):
            form = super().get_form(form_class)
            form.fields['employee'].queryset = CustomUser.active.filter(status='ACTIVE')
            form.fields['purpose_details'].widget = forms.Textarea(attrs={'rows': 3})
            form.fields['purpose_details'].required = False
            return form
        
        def form_valid(self, form):
            employee = form.cleaned_data['employee']
            amount = form.cleaned_data['amount']
            
            advance_data = PayrollAdvanceCalculator.calculate_available_advance_amount(employee)
            
            if amount > advance_data['available_amount']:
                form.add_error('amount', f"Amount exceeds available limit of LKR {advance_data['available_amount']}")
                return self.form_invalid(form)
            
            max_advances_per_year = SystemConfiguration.get_int_setting('MAX_ADVANCES_PER_YEAR', 10)
            if advance_data['advance_count_this_year'] >= max_advances_per_year:
                form.add_error(None, f"Maximum {max_advances_per_year} advances per year exceeded")
                return self.form_invalid(form)
            
            form.instance.requested_by = self.request.user
            form.instance.employee_basic_salary = advance_data['basic_salary']
            form.instance.max_allowed_percentage = advance_data['max_percentage']
            form.instance.advance_count_this_year = advance_data['advance_count_this_year']
            
            response = super().form_valid(form)
            
            log_payroll_activity(
                self.request.user,
                "ADVANCE_REQUESTED",
                {
                    "advance_id": str(self.object.id),
                    "employee_code": employee.employee_code,
                    "amount": float(amount),
                    "installments": form.cleaned_data['installments'],
                },
            )
            
            messages.success(self.request, f"Salary advance request for {employee.get_full_name()} created successfully.")
            return response
        
        def get_success_url(self):
            return reverse('payroll:advance_detail', kwargs={'pk': self.object.pk})
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            
            context.update({
                'page_title': 'Create Salary Advance',
                'advance_types': SalaryAdvance.ADVANCE_TYPES,
                'max_installments': 12,
                'min_amount': 100,
            })
            
            return context
    
    class SalaryAdvanceDetailView(LoginRequiredMixin, DetailView):
        model = SalaryAdvance
        template_name = 'payroll/advance_detail.html'
        context_object_name = 'advance'
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            advance = self.object
            
            employee = advance.employee
            profile = EmployeeDataManager.get_employee_profile(employee)
            
            other_active_advances = SalaryAdvance.objects.filter(
                employee=employee,
                status='ACTIVE',
                outstanding_amount__gt=0
            ).exclude(pk=advance.pk)
            
            advance_history = SalaryAdvance.objects.filter(
                employee=employee
            ).exclude(pk=advance.pk).order_by('-requested_date')[:5]
            
            context.update({
                'page_title': f'Salary Advance: {advance.reference_number}',
                'employee': employee,
                'profile': profile,
                'other_active_advances': other_active_advances,
                'advance_history': advance_history,
                'can_approve': advance.status == 'PENDING',
                'can_activate': advance.status == 'APPROVED',
                'can_cancel': advance.status in ['PENDING', 'APPROVED'],
            })
            
            return context
    
    class SalaryAdvanceApproveView(LoginRequiredMixin, View):
        def post(self, request, pk):
            advance = get_object_or_404(SalaryAdvance, pk=pk)
            
            if advance.status != 'PENDING':
                messages.error(request, f"Cannot approve advance in {advance.status} status.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            try:
                advance.approve(request.user)
                
                messages.success(request, f"Salary advance for {advance.employee.get_full_name()} approved successfully.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            except Exception as e:
                logger.error(f"Error approving advance {advance.id}: {str(e)}")
                messages.error(request, f"Error approving advance: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
    
    class SalaryAdvanceActivateView(LoginRequiredMixin, View):
        def post(self, request, pk):
            advance = get_object_or_404(SalaryAdvance, pk=pk)
            
            if advance.status != 'APPROVED':
                messages.error(request, f"Cannot activate advance in {advance.status} status.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            try:
                advance.activate(request.user)
                
                messages.success(request, f"Salary advance for {advance.employee.get_full_name()} activated successfully.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            except Exception as e:
                logger.error(f"Error activating advance {advance.id}: {str(e)}")
                messages.error(request, f"Error activating advance: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
    
    class BulkSalaryAdvanceApproveView(LoginRequiredMixin, View):
        def get(self, request):
            pending_advances = SalaryAdvance.objects.filter(status='PENDING').select_related('employee')
            
            departments = Department.objects.filter(is_active=True)
            advance_types = [advance_type[0] for advance_type in SalaryAdvance.ADVANCE_TYPES]
            
            context = {
                'page_title': 'Bulk Approve Salary Advances',
                'pending_advances': pending_advances,
                'departments': departments,
                'advance_types': advance_types,
                'can_approve': pending_advances.exists(),
            }
            
            return render(request, 'payroll/bulk_advance_approve.html', context)
        
        def post(self, request):
            advance_ids = request.POST.getlist('advance_ids')
            
            if not advance_ids:
                messages.error(request, "No advances selected for approval.")
                return HttpResponseRedirect(reverse('payroll:bulk_advance_approve'))
            
            try:
                approved_count, failed_approvals = SalaryAdvance.objects.bulk_approve(advance_ids, request.user)
                
                if failed_approvals:
                    for failure in failed_approvals[:5]:
                        messages.warning(request, failure)
                    
                    if len(failed_approvals) > 5:
                        messages.warning(request, f"... and {len(failed_approvals) - 5} more failures.")
                
                messages.success(request, f"Approved {approved_count} salary advances successfully.")
                return HttpResponseRedirect(reverse('payroll:advance_list'))
            
            except Exception as e:
                logger.error(f"Error in bulk approve advances: {str(e)}")
                messages.error(request, f"Error approving advances: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bulk_advance_approve'))
    
    class SalaryAdvanceCancelView(LoginRequiredMixin, View):
        def post(self, request, pk):
            advance = get_object_or_404(SalaryAdvance, pk=pk)
            
            if advance.status not in ['PENDING', 'APPROVED']:
                messages.error(request, f"Cannot cancel advance in {advance.status} status.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            try:
                advance.status = 'CANCELLED'
                advance.save(update_fields=['status'])
                
                log_payroll_activity(
                    request.user,
                    "ADVANCE_CANCELLED",
                    {
                        "advance_id": str(advance.id),
                        "employee_code": advance.employee.employee_code,
                        "amount": float(advance.amount),
                    },
                )
                
                messages.success(request, f"Salary advance for {advance.employee.get_full_name()} cancelled successfully.")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))
            
            except Exception as e:
                logger.error(f"Error cancelling advance {advance.id}: {str(e)}")
                messages.error(request, f"Error cancelling advance: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:advance_detail', kwargs={'pk': advance.pk}))

class BankTransferViews:
    class BankTransferListView(LoginRequiredMixin, ListView):
        model = PayrollBankTransfer
        template_name = 'payroll/bank_transfer_list.html'
        context_object_name = 'transfers'
        paginate_by = 20
        
        def get_queryset(self):
            queryset = PayrollBankTransfer.objects.all().select_related('payroll_period', 'created_by')
            
            status_filter = self.request.GET.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            period_id = self.request.GET.get('period_id')
            if period_id:
                queryset = queryset.filter(payroll_period_id=period_id)
            
            date_from = self.request.GET.get('date_from')
            if date_from:
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__gte=date_from)
                except ValueError:
                    pass
            
            date_to = self.request.GET.get('date_to')
            if date_to:
                try:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__lte=date_to)
                except ValueError:
                    pass
            
            search_query = self.request.GET.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(batch_reference__icontains=search_query) |
                    Q(payroll_period__period_name__icontains=search_query)
                )
            
            sort_by = self.request.GET.get('sort_by', '-created_at')
            queryset = queryset.order_by(sort_by)
            
            return queryset
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            
            periods = PayrollPeriod.objects.filter(status__in=['APPROVED', 'PAID']).order_by('-year', '-month')
            statuses = [status[0] for status in PayrollBankTransfer.STATUS_CHOICES]
            
            pending_count = PayrollBankTransfer.objects.filter(status='PENDING').count()
            generated_count = PayrollBankTransfer.objects.filter(status='GENERATED').count()
            sent_count = PayrollBankTransfer.objects.filter(status='SENT').count()
            
            context.update({
                'page_title': 'Bank Transfers',
                'periods': periods,
                'statuses': statuses,
                'status_filter': self.request.GET.get('status', ''),
                'period_id': self.request.GET.get('period_id', ''),
                'date_from': self.request.GET.get('date_from', ''),
                'date_to': self.request.GET.get('date_to', ''),
                'search_query': self.request.GET.get('search', ''),
                'sort_by': self.request.GET.get('sort_by', '-created_at'),
                'pending_count': pending_count,
                'generated_count': generated_count,
                'sent_count': sent_count,
                'can_create_transfer': True,
            })
            
            return context
    
    class BankTransferCreateView(LoginRequiredMixin, CreateView):
        model = PayrollBankTransfer
        template_name = 'payroll/bank_transfer_create.html'
        fields = ['payroll_period', 'bank_file_format']
        
        def get_form(self, form_class=None):
            form = super().get_form(form_class)
            form.fields['payroll_period'].queryset = PayrollPeriod.objects.filter(
                status='APPROVED'
            ).exclude(
                id__in=PayrollBankTransfer.objects.filter(
                    status__in=['PENDING', 'GENERATED', 'SENT', 'PROCESSED']
                ).values_list('payroll_period_id', flat=True)
            )
            
            form.fields['bank_file_format'].initial = SystemConfiguration.get_setting('BANK_FILE_FORMAT', 'CSV')
            form.fields['bank_file_format'].widget = forms.Select(choices=[('CSV', 'CSV'), ('XML', 'XML')])
            
            return form
        
        def form_valid(self, form):
            period = form.cleaned_data['payroll_period']
            
            approved_payslips = Payslip.objects.filter(
                payroll_period=period,
                status='APPROVED',
                net_salary__gt=0
            )
            
            if not approved_payslips.exists():
                form.add_error('payroll_period', "No approved payslips with positive net salary found for this period.")
                return self.form_invalid(form)
            
            form.instance.created_by = self.request.user
            
            response = super().form_valid(form)
            
            log_payroll_activity(
                self.request.user,
                "BANK_TRANSFER_CREATED",
                {
                    "transfer_id": str(self.object.id),
                    "batch_reference": self.object.batch_reference,
                    "period_id": str(period.id),
                    "period_name": period.period_name,
                },
            )
            
            messages.success(self.request, f"Bank transfer for {period.period_name} created successfully.")
            return response
        
        def get_success_url(self):
            return reverse('payroll:bank_transfer_detail', kwargs={'pk': self.object.pk})
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            
            context.update({
                'page_title': 'Create Bank Transfer',
                'file_formats': [('CSV', 'CSV'), ('XML', 'XML')],
            })
            
            return context
        
    class BankTransferDetailView(LoginRequiredMixin, DetailView):
        model = PayrollBankTransfer
        template_name = 'payroll/bank_transfer_detail.html'
        context_object_name = 'transfer'
        
        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            transfer = self.object
            period = transfer.payroll_period
            
            payslips = Payslip.objects.filter(
                payroll_period=period,
                status='APPROVED',
                net_salary__gt=0
            ).select_related('employee')
            
            employees_with_issues = []
            for payslip in payslips:
                profile = EmployeeDataManager.get_employee_profile(payslip.employee)
                if not profile or not profile.bank_account_number or not profile.bank_code:
                    employees_with_issues.append({
                        'employee_code': payslip.employee.employee_code,
                        'employee_name': payslip.employee.get_full_name(),
                        'issues': []
                    })
                    
                    if not profile:
                        employees_with_issues[-1]['issues'].append('No employee profile')
                    elif not profile.bank_account_number:
                        employees_with_issues[-1]['issues'].append('No bank account number')
                    elif not profile.bank_code:
                        employees_with_issues[-1]['issues'].append('No bank code')
            
            context.update({
                'page_title': f'Bank Transfer: {transfer.batch_reference}',
                'period': period,
                'payslips_count': payslips.count(),
                'total_amount': payslips.aggregate(Sum('net_salary'))['net_salary__sum'] or 0,
                'employees_with_issues': employees_with_issues,
                'can_generate_file': transfer.status == 'PENDING' and not employees_with_issues,
                'can_mark_as_sent': transfer.status == 'GENERATED',
                'can_mark_as_processed': transfer.status == 'SENT',
                'can_download_file': transfer.status in ['GENERATED', 'SENT', 'PROCESSED'] and transfer.bank_file_path,
            })
            
            return context
    
    class BankTransferGenerateFileView(LoginRequiredMixin, View):
        def post(self, request, pk):
            transfer = get_object_or_404(PayrollBankTransfer, pk=pk)
            
            if transfer.status != 'PENDING':
                messages.error(request, f"Cannot generate file for transfer in {transfer.status} status.")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            try:
                file_path = transfer.generate_bank_file()
                
                if not file_path:
                    messages.error(request, "Failed to generate bank file. Check error details.")
                    return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
                
                messages.success(request, f"Bank file generated successfully at {file_path}")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            except Exception as e:
                logger.error(f"Error generating bank file for transfer {transfer.id}: {str(e)}")
                messages.error(request, f"Error generating bank file: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
    
    class BankTransferMarkAsSentView(LoginRequiredMixin, View):
        def post(self, request, pk):
            transfer = get_object_or_404(PayrollBankTransfer, pk=pk)
            
            if transfer.status != 'GENERATED':
                messages.error(request, f"Cannot mark transfer in {transfer.status} status as sent.")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            try:
                transfer.status = 'SENT'
                transfer.sent_at = timezone.now()
                transfer.save(update_fields=['status', 'sent_at'])
                
                log_payroll_activity(
                    request.user,
                    "BANK_TRANSFER_SENT",
                    {
                        "transfer_id": str(transfer.id),
                        "batch_reference": transfer.batch_reference,
                        "period_id": str(transfer.payroll_period.id),
                        "period_name": transfer.payroll_period.period_name,
                    },
                )
                
                messages.success(request, f"Bank transfer {transfer.batch_reference} marked as sent to bank.")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            except Exception as e:
                logger.error(f"Error marking transfer {transfer.id} as sent: {str(e)}")
                messages.error(request, f"Error marking transfer as sent: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
    
    class BankTransferMarkAsProcessedView(LoginRequiredMixin, View):
        def post(self, request, pk):
            transfer = get_object_or_404(PayrollBankTransfer, pk=pk)
            
            if transfer.status != 'SENT':
                messages.error(request, f"Cannot mark transfer in {transfer.status} status as processed.")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            try:
                with transaction.atomic():
                    transfer.status = 'PROCESSED'
                    transfer.processed_at = timezone.now()
                    transfer.save(update_fields=['status', 'processed_at'])
                    
                    period = transfer.payroll_period
                    period.status = 'PAID'
                    period.save(update_fields=['status'])
                    
                    payslips = Payslip.objects.filter(
                        payroll_period=period,
                        status='APPROVED'
                    )
                    
                    for payslip in payslips:
                        payslip.status = 'PAID'
                        payslip.save(update_fields=['status'])
                    
                    log_payroll_activity(
                        request.user,
                        "BANK_TRANSFER_PROCESSED",
                        {
                            "transfer_id": str(transfer.id),
                            "batch_reference": transfer.batch_reference,
                            "period_id": str(period.id),
                            "period_name": period.period_name,
                            "payslips_count": payslips.count(),
                        },
                    )
                    
                    messages.success(request, f"Bank transfer {transfer.batch_reference} marked as processed and payroll period marked as paid.")
                    return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            except Exception as e:
                logger.error(f"Error marking transfer {transfer.id} as processed: {str(e)}")
                messages.error(request, f"Error marking transfer as processed: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
    
    class BankTransferDownloadFileView(LoginRequiredMixin, View):
        def get(self, request, pk):
            transfer = get_object_or_404(PayrollBankTransfer, pk=pk)
            
            if not transfer.bank_file_path or transfer.status not in ['GENERATED', 'SENT', 'PROCESSED', 'COMPLETED']:
                messages.error(request, "Bank file not available for download.")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
            
            try:
                import os
                from django.http import FileResponse
                
                file_path = transfer.bank_file_path
                
                if not os.path.exists(file_path):
                    messages.error(request, "Bank file not found on server.")
                    return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))
                
                file_name = os.path.basename(file_path)
                
                response = FileResponse(open(file_path, 'rb'))
                response['Content-Disposition'] = f'attachment; filename="{file_name}"'
                
                if file_path.endswith('.csv'):
                    response['Content-Type'] = 'text/csv'
                elif file_path.endswith('.xml'):
                    response['Content-Type'] = 'application/xml'
                else:
                    response['Content-Type'] = 'application/octet-stream'
                
                log_payroll_activity(
                    request.user,
                    "BANK_FILE_DOWNLOADED",
                    {
                        "transfer_id": str(transfer.id),
                        "batch_reference": transfer.batch_reference,
                        "file_name": file_name,
                    },
                )
                
                return response
            
            except Exception as e:
                logger.error(f"Error downloading bank file for transfer {transfer.id}: {str(e)}")
                messages.error(request, f"Error downloading bank file: {str(e)}")
                return HttpResponseRedirect(reverse('payroll:bank_transfer_detail', kwargs={'pk': transfer.pk}))

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        current_year, current_month = PayrollUtilityHelper.get_current_payroll_period()

        current_period = PayrollPeriod.objects.filter(year=current_year, month=current_month).first()
        recent_periods = PayrollPeriod.objects.all().order_by('-year', '-month')[:5]

        total_employees = CustomUser.active.filter(status="ACTIVE").count()

        payroll_stats = {
            'total_employees': total_employees,
            'total_departments': Department.objects.filter(is_active=True).count(),
            'total_roles': Role.objects.filter(is_active=True).count(),
        }

        current_period_stats = {}
        if current_period:
            calculated_payslips = Payslip.objects.filter(
                payroll_period=current_period,
                status__in=['CALCULATED', 'APPROVED', 'PAID']
            )

            current_period_stats = {
                'period_name': current_period.period_name,
                'status': current_period.status,
                'total_gross': float(current_period.total_gross_salary),
                'total_net': float(current_period.total_net_salary),
                'total_deductions': float(current_period.total_deductions),
                'calculated_count': calculated_payslips.count(),
                'approved_count': calculated_payslips.filter(status__in=['APPROVED', 'PAID']).count(),
                'completion_percentage': (calculated_payslips.count() / total_employees * 100) if total_employees > 0 else 0,
            }

        departments = Department.objects.filter(is_active=True)
        department_stats = {}

        for dept in departments:
            dept_employees = CustomUser.active.filter(department=dept, status="ACTIVE")

            if current_period:
                dept_payslips = Payslip.objects.filter(
                    payroll_period=current_period,
                    employee__department=dept,
                    status__in=['CALCULATED', 'APPROVED', 'PAID']
                )

                dept_summary, created = PayrollDepartmentSummary.objects.get_or_create(
                    payroll_period=current_period,
                    department=dept
                )

                if created or dept_summary.employee_count == 0:
                    dept_summary.calculate_summary()

                department_stats[dept.name] = {
                    'employee_count': dept_employees.count(),
                    'calculated_count': dept_payslips.count(),
                    'total_gross': float(dept_summary.total_gross_salary),
                    'total_net': float(dept_summary.total_net_salary),
                    'budget_utilization': float(dept_summary.budget_utilization_percentage),
                    'efficiency_score': dept_summary.performance_metrics.get('department_efficiency_score', 0),
                }
            else:
                department_stats[dept.name] = {
                    'employee_count': dept_employees.count(),
                    'calculated_count': 0,
                    'total_gross': 0,
                    'total_net': 0,
                    'budget_utilization': 0,
                    'efficiency_score': 0,
                }

        advance_stats = {
            'pending_count': SalaryAdvance.objects.filter(status='PENDING').count(),
            'active_count': SalaryAdvance.objects.filter(status='ACTIVE').count(),
            'total_outstanding': float(SalaryAdvance.objects.filter(status='ACTIVE').aggregate(Sum('outstanding_amount'))['outstanding_amount__sum'] or 0),
            'recent_advances': SalaryAdvance.objects.all().order_by('-requested_date')[:5],
        }

        bank_transfer_stats = {
            'pending_count': PayrollBankTransfer.objects.filter(status='PENDING').count(),
            'generated_count': PayrollBankTransfer.objects.filter(status='GENERATED').count(),
            'sent_count': PayrollBankTransfer.objects.filter(status='SENT').count(),
            'recent_transfers': PayrollBankTransfer.objects.all().order_by('-created_at')[:5],
        }

        system_validation = validate_payroll_system_integrity()

        context = {
            'page_title': 'Payroll Dashboard',
            'current_year': current_year,
            'current_month': current_month,
            'current_period': current_period,
            'recent_periods': recent_periods,
            'payroll_stats': payroll_stats,
            'current_period_stats': current_period_stats,
            'department_stats': department_stats,
            'advance_stats': advance_stats,
            'bank_transfer_stats': bank_transfer_stats,
            'system_validation': system_validation,
            'can_create_period': True,
            'can_process_payroll': current_period and current_period.status in ['DRAFT', 'PROCESSING'],
            'can_view_reports': True,
        }

        return render(request, 'payroll/dashboard.html', context)

    def get_department_summary_report(self, request):
        period_id = request.GET.get('period_id')

        if not period_id:
            periods = PayrollPeriod.objects.filter(status__in=['COMPLETED', 'APPROVED', 'PAID']).order_by('-year', '-month')

            context = {
                'page_title': 'Department Summary Report',
                'periods': periods,
                'report_generated': False,
            }

            return render(request, 'payroll/reports/department_summary.html', context)

        try:
            period = PayrollPeriod.objects.get(pk=period_id)
            departments = Department.objects.filter(is_active=True)

            department_summaries = {}
            for dept in departments:
                dept_summary, created = PayrollDepartmentSummary.objects.get_or_create(
                    payroll_period=period,
                    department=dept
                )

                if created or dept_summary.employee_count == 0:
                    dept_payslips = Payslip.objects.filter(
                        payroll_period=period,
                        employee__department=dept,
                        status__in=['CALCULATED', 'APPROVED', 'PAID']
                    )

                    if dept_payslips.exists():
                        dept_summary.calculate_summary()

                if dept_summary.employee_count > 0:
                    department_summaries[dept.name] = dept_summary

            context = {
                'page_title': f'Department Summary Report: {period.period_name}',
                'period': period,
                'periods': PayrollPeriod.objects.filter(status__in=['COMPLETED', 'APPROVED', 'PAID']).order_by('-year', '-month'),
                'department_summaries': department_summaries,
                'report_generated': True,
                'can_export_pdf': True,
                'can_export_excel': True,
            }

            return render(request, 'payroll/reports/department_summary.html', context)

        except PayrollPeriod.DoesNotExist:
            messages.error(request, "Invalid payroll period selected.")
            return HttpResponseRedirect(reverse('payroll:department_summary_report'))

        except Exception as e:
            logger.error(f"Error generating department summary report: {str(e)}")
            messages.error(request, f"Error generating report: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:department_summary_report'))

    def get_tax_report(self, request):
        year = request.GET.get('year')
        report_type = request.GET.get('report_type', 'annual')

        if not year or not year.isdigit():
            current_year = datetime.now().year
            years = [(str(year), str(year)) for year in range(current_year - 5, current_year + 1)]

            context = {
                'page_title': 'Tax Report',
                'years': years,
                'current_year': current_year,
                'report_types': [('annual', 'Annual')],
                'report_generated': False,
            }

            return render(request, 'payroll/reports/tax_report.html', context)

        try:
            year = int(year)
            report_result = generate_tax_report(year, report_type)

            if report_result['status'] != 'success':
                messages.error(request, f"Error generating tax report: {report_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:tax_report'))

            tax_report = report_result['tax_report']

            current_year = datetime.now().year
            years = [(str(year), str(year)) for year in range(current_year - 5, current_year + 1)]

            context = {
                'page_title': f'Tax Report: {year}',
                'years': years,
                'current_year': current_year,
                'selected_year': str(year),
                'report_types': [('annual', 'Annual')],
                'selected_report_type': report_type,
                'tax_report': tax_report,
                'report_generated': True,
                'can_export_pdf': True,
                'can_export_excel': True,
            }

            return render(request, 'payroll/reports/tax_report.html', context)

        except Exception as e:
            logger.error(f"Error generating tax report: {str(e)}")
            messages.error(request, f"Error generating report: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:tax_report'))

    def get_year_to_date_report(self, request):
        employee_id = request.GET.get('employee_id')
        year = request.GET.get('year')

        if not employee_id or not year or not year.isdigit():
            employees = CustomUser.active.filter(status="ACTIVE").order_by('first_name', 'last_name')
            current_year = datetime.now().year
            years = [(str(year), str(year)) for year in range(current_year - 5, current_year + 1)]

            context = {
                'page_title': 'Year to Date Report',
                'employees': employees,
                'years': years,
                'current_year': current_year,
                'report_generated': False,
            }

            return render(request, 'payroll/reports/year_to_date.html', context)

        try:
            employee = CustomUser.objects.get(pk=employee_id)
            year = int(year)

            ytd_result = calculate_employee_year_to_date(employee_id, year)

            if ytd_result['status'] != 'success':
                messages.error(request, f"Error generating YTD report: {ytd_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:year_to_date_report'))

            ytd_data = ytd_result['ytd_data']

            employees = CustomUser.active.filter(status="ACTIVE").order_by('first_name', 'last_name')
            current_year = datetime.now().year
            years = [(str(year), str(year)) for year in range(current_year - 5, current_year + 1)]

            context = {
                'page_title': f'Year to Date Report: {employee.get_full_name()} - {year}',
                'employees': employees,
                'years': years,
                'current_year': current_year,
                'selected_year': str(year),
                'selected_employee': employee,
                'ytd_data': ytd_data,
                'report_generated': True,
                'can_export_pdf': True,
                'can_export_excel': True,
            }

            return render(request, 'payroll/reports/year_to_date.html', context)

        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid employee selected.")
            return HttpResponseRedirect(reverse('payroll:year_to_date_report'))

        except Exception as e:
            logger.error(f"Error generating YTD report: {str(e)}")
            messages.error(request, f"Error generating report: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:year_to_date_report'))

    def get_payroll_comparison_report(self, request):
        period1_id = request.GET.get('period1_id')
        period2_id = request.GET.get('period2_id')

        if not period1_id or not period2_id:
            periods = PayrollPeriod.objects.filter(status__in=['COMPLETED', 'APPROVED', 'PAID']).order_by('-year', '-month')

            context = {
                'page_title': 'Payroll Comparison Report',
                'periods': periods,
                'report_generated': False,
            }

            return render(request, 'payroll/reports/payroll_comparison.html', context)

        try:
            period1 = PayrollPeriod.objects.get(pk=period1_id)
            period2 = PayrollPeriod.objects.get(pk=period2_id)

            if period1.id == period2.id:
                messages.error(request, "Please select two different payroll periods for comparison.")
                return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

            comparison_result = generate_payroll_comparison_report(period1.year, period1.month, period2.year, period2.month)

            if comparison_result['status'] != 'success':
                messages.error(request, f"Error generating comparison report: {comparison_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

            comparison_data = comparison_result['comparison']

            periods = PayrollPeriod.objects.filter(status__in=['COMPLETED', 'APPROVED', 'PAID']).order_by('-year', '-month')

            context = {
                'page_title': 'Payroll Comparison Report',
                'periods': periods,
                'period1': period1,
                'period2': period2,
                'comparison_data': comparison_data,
                'report_generated': True,
                'can_export_pdf': True,
                'can_export_excel': True,
            }

            return render(request, 'payroll/reports/payroll_comparison.html', context)

        except PayrollPeriod.DoesNotExist:
            messages.error(request, "Invalid payroll period selected.")
            return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

        except Exception as e:
            logger.error(f"Error generating comparison report: {str(e)}")
            messages.error(request, f"Error generating report: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

    def export_department_summary_pdf(self, request, period_id):
        try:
            period = PayrollPeriod.objects.get(pk=period_id)
            departments = Department.objects.filter(is_active=True)

            department_summaries = {}
            for dept in departments:
                dept_summary = PayrollDepartmentSummary.objects.filter(
                    payroll_period=period,
                    department=dept
                ).first()

                if dept_summary and dept_summary.employee_count > 0:
                    department_summaries[dept.name] = dept_summary

            template = get_template('payroll/reports/pdf/department_summary_pdf.html')
            context = {
                'period': period,
                'department_summaries': department_summaries,
                'company_name': SystemConfiguration.get_setting('COMPANY_NAME', 'Company Name'),
                'generated_date': timezone.now().date(),
            }

            html = template.render(context)
            result = io.BytesIO()

            pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="department_summary_{period.year}_{period.month}.pdf"'
                return response

            return HttpResponse("Error generating PDF", status=400)

        except Exception as e:
            logger.error(f"Error exporting department summary PDF: {str(e)}")
            messages.error(request, f"Error exporting PDF: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:department_summary_report') + f'?period_id={period_id}')

    def export_department_summary_excel(self, request, period_id):
        try:

            period = PayrollPeriod.objects.get(pk=period_id)
            departments = Department.objects.filter(is_active=True)

            department_summaries = {}
            for dept in departments:
                dept_summary = PayrollDepartmentSummary.objects.filter(
                    payroll_period=period,
                    department=dept
                ).first()

                if dept_summary and dept_summary.employee_count > 0:
                    department_summaries[dept.name] = dept_summary

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Department Summary')

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F0F0',
                'border': 1
            })

            money_format = workbook.add_format({'num_format': '#,##0.00'})
            percent_format = workbook.add_format({'num_format': '0.00%'})

            headers = [
                'Department', 'Employees', 'Total Basic Salary', 'Total Allowances',
                'Total Overtime', 'Total Gross', 'Total Deductions', 'Total Net',
                'EPF Employee', 'EPF Employer', 'ETF', 'Budget Utilization'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            row = 1
            for dept_name, summary in department_summaries.items():
                worksheet.write(row, 0, dept_name)
                worksheet.write(row, 1, summary.employee_count)
                worksheet.write(row, 2, float(summary.total_basic_salary), money_format)
                worksheet.write(row, 3, float(summary.total_allowances), money_format)
                worksheet.write(row, 4, float(summary.total_overtime_pay), money_format)
                worksheet.write(row, 5, float(summary.total_gross_salary), money_format)
                worksheet.write(row, 6, float(summary.total_deductions), money_format)
                worksheet.write(row, 7, float(summary.total_net_salary), money_format)
                worksheet.write(row, 8, float(summary.total_epf_employee), money_format)
                worksheet.write(row, 9, float(summary.total_epf_employer), money_format)
                worksheet.write(row, 10, float(summary.total_etf_contribution), money_format)
                worksheet.write(row, 11, float(summary.budget_utilization_percentage) / 100, percent_format)
                row += 1

            worksheet.set_column(0, 0, 20)
            worksheet.set_column(1, 11, 15)

            workbook.close()
            output.seek(0)

            response = HttpResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="department_summary_{period.year}_{period.month}.xlsx"'

            return response

        except Exception as e:
            logger.error(f"Error exporting department summary Excel: {str(e)}")
            messages.error(request, f"Error exporting Excel: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:department_summary_report') + f'?period_id={period_id}')

    def export_tax_report_pdf(self, request, year, report_type):
        try:  
            report_result = generate_tax_report(int(year), report_type)

            if report_result['status'] != 'success':
                messages.error(request, f"Error generating tax report: {report_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:tax_report'))

            tax_report = report_result['tax_report']

            template = get_template('payroll/reports/pdf/tax_report_pdf.html')
            context = {
                'tax_report': tax_report,
                'year': year,
                'report_type': report_type,
                'company_name': SystemConfiguration.get_setting('COMPANY_NAME', 'Company Name'),
                'generated_date': timezone.now().date(),
            }

            html = template.render(context)
            result = io.BytesIO()

            pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="tax_report_{year}_{report_type}.pdf"'
                return response

            return HttpResponse("Error generating PDF", status=400)

        except Exception as e:
            logger.error(f"Error exporting tax report PDF: {str(e)}")
            messages.error(request, f"Error exporting PDF: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:tax_report') + f'?year={year}&report_type={report_type}')

    def export_tax_report_excel(self, request, year, report_type):
        try:
            report_result = generate_tax_report(int(year), report_type)

            if report_result['status'] != 'success':
                messages.error(request, f"Error generating tax report: {report_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:tax_report'))

            tax_report = report_result['tax_report']

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Tax Report')

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F0F0',
                'border': 1
            })

            money_format = workbook.add_format({'num_format': '#,##0.00'})

            worksheet.write(0, 0, f"Tax Report - {year}", header_format)
            worksheet.write(1, 0, f"Total Employees: {tax_report['total_employees']}")
            worksheet.write(2, 0, f"Total Gross Salary: {tax_report['total_gross_salary']}", money_format)
            worksheet.write(3, 0, f"Total EPF Employee: {tax_report['total_epf_employee']}", money_format)
            worksheet.write(4, 0, f"Total EPF Employer: {tax_report['total_epf_employer']}", money_format)
            worksheet.write(5, 0, f"Total ETF: {tax_report['total_etf']}", money_format)
            worksheet.write(6, 0, f"Total Income Tax: {tax_report['total_income_tax']}", money_format)

            headers = [
                'Employee Code', 'Employee Name', 'Annual Gross', 'EPF Employee',
                'EPF Employer', 'ETF', 'Income Tax'
            ]

            for col, header in enumerate(headers):
                worksheet.write(8, col, header, header_format)

            row = 9
            for employee_data in tax_report['employee_breakdown']:
                worksheet.write(row, 0, employee_data['employee_code'])
                worksheet.write(row, 1, employee_data['employee_name'])
                worksheet.write(row, 2, employee_data['annual_gross'], money_format)
                worksheet.write(row, 3, employee_data['annual_epf_employee'], money_format)
                worksheet.write(row, 4, employee_data['annual_epf_employer'], money_format)
                worksheet.write(row, 5, employee_data['annual_etf'], money_format)
                worksheet.write(row, 6, employee_data['annual_income_tax'], money_format)
                row += 1

            worksheet.set_column(0, 0, 15)
            worksheet.set_column(1, 1, 30)
            worksheet.set_column(2, 6, 15)

            workbook.close()
            output.seek(0)

            response = HttpResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="tax_report_{year}_{report_type}.xlsx"'

            return response

        except Exception as e:
            logger.error(f"Error exporting tax report Excel: {str(e)}")
            messages.error(request, f"Error exporting Excel: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:tax_report') + f'?year={year}&report_type={report_type}')

    def export_ytd_report_pdf(self, request, employee_id, year):
        try:
            employee = CustomUser.objects.get(pk=employee_id)
            ytd_result = calculate_employee_year_to_date(employee_id, int(year))

            if ytd_result['status'] != 'success':
                messages.error(request, f"Error generating YTD report: {ytd_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:year_to_date_report'))

            ytd_data = ytd_result['ytd_data']

            template = get_template('payroll/reports/pdf/ytd_report_pdf.html')
            context = {
                'employee': employee,
                'ytd_data': ytd_data,
                'year': year,
                'company_name': SystemConfiguration.get_setting('COMPANY_NAME', 'Company Name'),
                'generated_date': timezone.now().date(),
            }

            html = template.render(context)
            result = io.BytesIO()

            pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="ytd_report_{employee.employee_code}_{year}.pdf"'
                return response

            return HttpResponse("Error generating PDF", status=400)

        except Exception as e:
            logger.error(f"Error exporting YTD report PDF: {str(e)}")
            messages.error(request, f"Error exporting PDF: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:year_to_date_report') + f'?employee_id={employee_id}&year={year}')

    def export_ytd_report_excel(self, request, employee_id, year):
        try:
            employee = CustomUser.objects.get(pk=employee_id)
            ytd_result = calculate_employee_year_to_date(employee_id, int(year))

            if ytd_result['status'] != 'success':
                messages.error(request, f"Error generating YTD report: {ytd_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:year_to_date_report'))

            ytd_data = ytd_result['ytd_data']

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('YTD Report')

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F0F0',
                'border': 1
            })

            money_format = workbook.add_format({'num_format': '#,##0.00'})

            worksheet.write(0, 0, f"Year to Date Report - {year}", header_format)
            worksheet.write(1, 0, f"Employee: {ytd_data['employee_name']} ({ytd_data['employee_code']})")
            worksheet.write(2, 0, f"Total Months: {ytd_data['total_months']}")

            row = 4
            worksheet.write(row, 0, "Category", header_format)
            worksheet.write(row, 1, "Amount", header_format)

            row += 1
            worksheet.write(row, 0, "Total Gross Salary")
            worksheet.write(row, 1, ytd_data['total_gross_salary'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Basic Salary")
            worksheet.write(row, 1, ytd_data['total_basic_salary'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Allowances")
            worksheet.write(row, 1, ytd_data['total_allowances'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Overtime Pay")
            worksheet.write(row, 1, ytd_data['total_overtime_pay'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Deductions")
            worksheet.write(row, 1, ytd_data['total_deductions'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Net Salary")
            worksheet.write(row, 1, ytd_data['total_net_salary'], money_format)

            row += 1
            worksheet.write(row, 0, "Total EPF Employee")
            worksheet.write(row, 1, ytd_data['total_epf_employee'], money_format)

            row += 1
            worksheet.write(row, 0, "Total EPF Employer")
            worksheet.write(row, 1, ytd_data['total_epf_employer'], money_format)

            row += 1
            worksheet.write(row, 0, "Total ETF")
            worksheet.write(row, 1, ytd_data['total_etf'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Late Penalties")
            worksheet.write(row, 1, ytd_data['total_late_penalties'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Lunch Violations")
            worksheet.write(row, 1, ytd_data['total_lunch_violations'], money_format)

            row += 1
            worksheet.write(row, 0, "Total Advance Deductions")
            worksheet.write(row, 1, ytd_data['total_advance_deductions'], money_format)

            row += 1
            worksheet.write(row, 0, "Average Monthly Gross")
            worksheet.write(row, 1, ytd_data['average_monthly_gross'], money_format)

            row += 1
            worksheet.write(row, 0, "Average Monthly Net")
            worksheet.write(row, 1, ytd_data['average_monthly_net'], money_format)

            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 1, 15)

            workbook.close()
            output.seek(0)

            response = HttpResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="ytd_report_{employee.employee_code}_{year}.xlsx"'

            return response

        except Exception as e:
            logger.error(f"Error exporting YTD report Excel: {str(e)}")
            messages.error(request, f"Error exporting Excel: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:year_to_date_report') + f'?employee_id={employee_id}&year={year}')

    def export_comparison_report_pdf(self, request, period1_id, period2_id):
        try:
            period1 = PayrollPeriod.objects.get(pk=period1_id)
            period2 = PayrollPeriod.objects.get(pk=period2_id)

            comparison_result = generate_payroll_comparison_report(period1.year, period1.month, period2.year, period2.month)

            if comparison_result['status'] != 'success':
                messages.error(request, f"Error generating comparison report: {comparison_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

            comparison_data = comparison_result['comparison']

            template = get_template('payroll/reports/pdf/comparison_report_pdf.html')
            context = {
                'period1': period1,
                'period2': period2,
                'comparison_data': comparison_data,
                'company_name': SystemConfiguration.get_setting('COMPANY_NAME', 'Company Name'),
                'generated_date': timezone.now().date(),
            }

            html = template.render(context)
            result = io.BytesIO()

            pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
            if not pdf.err:
                response = HttpResponse(result.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="comparison_report_{period1.year}_{period1.month}_vs_{period2.year}_{period2.month}.pdf"'
                return response

            return HttpResponse("Error generating PDF", status=400)

        except Exception as e:
            logger.error(f"Error exporting comparison report PDF: {str(e)}")
            messages.error(request, f"Error exporting PDF: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:payroll_comparison_report') + f'?period1_id={period1_id}&period2_id={period2_id}')

    def export_comparison_report_excel(self, request, period1_id, period2_id):
        try:
            period1 = PayrollPeriod.objects.get(pk=period1_id)
            period2 = PayrollPeriod.objects.get(pk=period2_id)

            comparison_result = generate_payroll_comparison_report(period1.year, period1.month, period2.year, period2.month)

            if comparison_result['status'] != 'success':
                messages.error(request, f"Error generating comparison report: {comparison_result.get('error', 'Unknown error')}")
                return HttpResponseRedirect(reverse('payroll:payroll_comparison_report'))

            comparison_data = comparison_result['comparison']

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet('Comparison Report')

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F0F0',
                'border': 1
            })

            money_format = workbook.add_format({'num_format': '#,##0.00'})
            percent_format = workbook.add_format({'num_format': '0.00%'})

            worksheet.write(0, 0, f"Payroll Comparison Report", header_format)
            worksheet.write(1, 0, f"Period 1: {period1.period_name}")
            worksheet.write(2, 0, f"Period 2: {period2.period_name}")

            row = 4
            worksheet.write(row, 0, "Category", header_format)
            worksheet.write(row, 1, period1.period_name, header_format)
            worksheet.write(row, 2, period2.period_name, header_format)
            worksheet.write(row, 3, "Change", header_format)
            worksheet.write(row, 4, "% Change", header_format)

            row += 1
            worksheet.write(row, 0, "Total Employees")
            worksheet.write(row, 1, comparison_data['period1_data']['total_employees'])
            worksheet.write(row, 2, comparison_data['period2_data']['total_employees'])
            worksheet.write(row, 3, comparison_data['changes']['employee_change'])

            row += 1
            worksheet.write(row, 0, "Total Gross Salary")
            worksheet.write(row, 1, comparison_data['period1_data']['total_gross'], money_format)
            worksheet.write(row, 2, comparison_data['period2_data']['total_gross'], money_format)
            worksheet.write(row, 3, comparison_data['changes']['gross_change'], money_format)
            if 'gross_percentage' in comparison_data['changes']:
                worksheet.write(row, 4, comparison_data['changes']['gross_percentage'] / 100, percent_format)

            row += 1
            worksheet.write(row, 0, "Total Net Salary")
            worksheet.write(row, 1, comparison_data['period1_data']['total_net'], money_format)
            worksheet.write(row, 2, comparison_data['period2_data']['total_net'], money_format)
            worksheet.write(row, 3, comparison_data['changes']['net_change'], money_format)
            if 'net_percentage' in comparison_data['changes']:
                worksheet.write(row, 4, comparison_data['changes']['net_percentage'] / 100, percent_format)

            row += 1
            worksheet.write(row, 0, "Total Deductions")
            worksheet.write(row, 1, comparison_data['period1_data']['total_deductions'], money_format)
            worksheet.write(row, 2, comparison_data['period2_data']['total_deductions'], money_format)
            worksheet.write(row, 3, comparison_data['changes']['deduction_change'], money_format)

            worksheet.set_column(0, 0, 25)
            worksheet.set_column(1, 4, 15)

            workbook.close()
            output.seek(0)

            response = HttpResponse(
                output,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="comparison_report_{period1.year}_{period1.month}_vs_{period2.year}_{period2.month}.xlsx"'

            return response

        except Exception as e:
            logger.error(f"Error exporting comparison report Excel: {str(e)}")
            messages.error(request, f"Error exporting Excel: {str(e)}")
            return HttpResponseRedirect(reverse('payroll:payroll_comparison_report') + f'?period1_id={period1_id}&period2_id={period2_id}')

class PayrollSystemConfigurationView(LoginRequiredMixin, View):
    def get(self, request):
        payroll_settings = SystemConfiguration.objects.filter(
            setting_type="PAYROLL"
        ).order_by("key")

        settings_by_group = {
            "allowances": [],
            "bonuses": [],
            "deductions": [],
            "tax": [],
            "general": [],
        }

        for setting in payroll_settings:
            if "ALLOWANCE" in setting.key:
                settings_by_group["allowances"].append(setting)
            elif "BONUS" in setting.key:
                settings_by_group["bonuses"].append(setting)
            elif any(term in setting.key for term in ["DEDUCTION", "PENALTY"]):
                settings_by_group["deductions"].append(setting)
            elif any(term in setting.key for term in ["EPF", "ETF", "TAX"]):
                settings_by_group["tax"].append(setting)
            else:
                settings_by_group["general"].append(setting)

        system_validation = validate_payroll_system_integrity()

        context = {
            "page_title": "Payroll System Configuration",
            "settings_by_group": settings_by_group,
            "system_validation": system_validation,
            "can_edit_settings": True,
        }

        return render(request, "payroll/system_configuration.html", context)

    def post(self, request):
        setting_keys = request.POST.getlist("setting_key")
        setting_values = request.POST.getlist("setting_value")

        if len(setting_keys) != len(setting_values):
            messages.error(request, "Invalid form submission.")
            return HttpResponseRedirect(reverse("payroll:system_configuration"))

        updated_count = 0

        for i in range(len(setting_keys)):
            key = setting_keys[i]
            value = setting_values[i]

            try:
                setting = SystemConfiguration.objects.get(key=key)

                if setting.setting_type == "DECIMAL":
                    try:
                        value = Decimal(value)
                    except:
                        messages.warning(
                            request, f"Invalid decimal value for {key}. Skipping."
                        )
                        continue

                setting.value = str(value)
                setting.save()
                updated_count += 1

            except SystemConfiguration.DoesNotExist:
                messages.warning(request, f"Setting {key} not found. Skipping.")
                continue

        if updated_count > 0:
            messages.success(
                request, f"Updated {updated_count} configuration settings successfully."
            )

            PayrollCacheManager.clear_all_caches()

            log_payroll_activity(
                request.user,
                "SYSTEM_CONFIGURATION_UPDATED",
                {
                    "updated_count": updated_count,
                    "updated_keys": setting_keys,
                },
            )

        return HttpResponseRedirect(reverse("payroll:system_configuration"))

    def add_configuration(self, request):
        key = request.POST.get("key", "").strip().upper()
        value = request.POST.get("value", "").strip()
        description = request.POST.get("description", "").strip()
        setting_type = request.POST.get("setting_type", "TEXT")

        if not key or not value:
            messages.error(request, "Key and value are required.")
            return HttpResponseRedirect(reverse("payroll:system_configuration"))

        if SystemConfiguration.objects.filter(key=key).exists():
            messages.error(request, f"Configuration with key {key} already exists.")
            return HttpResponseRedirect(reverse("payroll:system_configuration"))

        if setting_type == "DECIMAL":
            try:
                Decimal(value)
            except:
                messages.error(request, "Invalid decimal value.")
                return HttpResponseRedirect(reverse("payroll:system_configuration"))

        SystemConfiguration.objects.create(
            key=key,
            value=value,
            description=description,
            setting_type="PAYROLL",
        )

        messages.success(
            request, f"Added new configuration setting {key} successfully."
        )

        log_payroll_activity(
            request.user,
            "SYSTEM_CONFIGURATION_ADDED",
            {
                "key": key,
                "value": value,
                "setting_type": setting_type,
            },
        )

        return HttpResponseRedirect(reverse("payroll:system_configuration"))

    def initialize_system(self, request):
        try:
            result = initialize_payroll_system()

            if result["status"] == "success":
                messages.success(
                    request,
                    f"Payroll system initialized successfully. Created {result.get('settings_created', 0)} new settings.",
                )
            else:
                messages.error(
                    request,
                    f"Error initializing payroll system: {result.get('error', 'Unknown error')}",
                )

            log_payroll_activity(
                request.user,
                "SYSTEM_INITIALIZED",
                {
                    "result": result,
                },
            )

            return HttpResponseRedirect(reverse("payroll:system_configuration"))

        except Exception as e:
            logger.error(f"Error initializing payroll system: {str(e)}")
            messages.error(request, f"Error initializing payroll system: {str(e)}")
            return HttpResponseRedirect(reverse("payroll:system_configuration"))
