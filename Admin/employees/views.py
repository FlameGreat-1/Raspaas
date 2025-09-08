from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.conf import settings
import json
import csv
from datetime import datetime, date, timedelta
from decimal import Decimal
import calendar
from attendance.models import Attendance, MonthlyAttendanceSummary
from payroll.models import PayrollPeriod

from accounts.models import CustomUser, Department, Role, SystemConfiguration
from accounts.utils import log_user_activity
from .models import EmployeeProfile, Education, Contract
from .forms import (
    DepartmentForm,
    EducationForm,
    ContractForm,
    BulkEmployeeImportForm,
    EmployeeSearchForm,
    ContractRenewalForm,
)
from .utils import (
    EmployeeUtils,
    ContractUtils,
    ValidationUtils,
    ExportUtils,
    ImportUtils,
    ReportUtils,
    NotificationUtils,
    BulkOperationUtils,
    CalculationUtils,
)
from accounts.analytics import UnifiedAnalytics
from accounts.utils import UserUtilities, log_user_activity, ExcelUtilities
User = get_user_model()


def is_hr_staff(user):
    return (
        user.is_authenticated
        and user.role
        and user.role.name
        in ["SUPER_ADMIN", "HR_MANAGER", "HR_ADMIN", "DEPARTMENT_MANAGER"]
    )


def is_admin_user(user):
    return (
        user.is_authenticated
        and user.role
        and user.role.name in ["SUPER_ADMIN", "HR_MANAGER"]
    )


@login_required
def dashboard_view(request):
    if is_admin_user(request.user):
        template_name = "employee/employees-analytics.html"
        context = UnifiedAnalytics.get_complete_dashboard_data()
    else:
        template_name = "index.html"
        if hasattr(request.user, "employee_profile"):
            profile = request.user.employee_profile
            context = {
                "employee_profile": profile,
                "years_of_service": profile.years_of_service,
                "probation_days_remaining": (
                    CalculationUtils.calculate_probation_days_remaining(
                        profile.probation_end_date
                    )
                    if profile.probation_end_date
                    else None
                ),
            }
        else:
            context = {}

    return render(request, template_name, context)

@login_required
@user_passes_test(is_admin_user)
def system_statistics_view(request):
    employee_stats = EmployeeUtils.get_employee_summary_stats()
    contract_stats = ContractUtils.get_contract_summary_stats()
    salary_analysis = ReportUtils.generate_salary_analysis_report()

    context = {
        "employee_stats": employee_stats,
        "contract_stats": contract_stats,
        "salary_analysis": salary_analysis,
        "probation_notifications": NotificationUtils.get_probation_notifications(),
        "contract_notifications": NotificationUtils.get_contract_expiry_notifications(),
        "birthday_notifications": NotificationUtils.get_birthday_notifications(),
    }

    return render(request, "employee/employees-analytics.html", context)

class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = "employee/department-list.html"
    context_object_name = "departments"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_departments"
        ) and not UserUtilities.check_user_permission(request.user, "view_departments") and not is_hr_staff(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            Department.objects.select_related("manager", "parent_department")
            .filter(is_active=True)
            .annotate(
                employee_count=Count(
                    "employees",
                    filter=Q(employees__is_active=True),
                ),
                avg_salary=Avg(
                    "employees__employee_profile__basic_salary",
                    filter=Q(employees__is_active=True),
                ),
            )
        )

        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(code__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Department Management"
        context["can_add_department"] = UserUtilities.check_user_permission(
            self.request.user, "manage_departments"
        )
        context["can_export"] = UserUtilities.check_user_permission(
            self.request.user, "manage_departments"
        )
        context["search_query"] = self.request.GET.get("search", "")

        departments = self.get_queryset()
        context["total_departments"] = departments.count()
        context["total_employees"] = sum(dept.employee_count for dept in departments)
        context["departments_with_managers"] = departments.exclude(manager=None).count()

        if context["total_departments"] > 0:
            context["average_employees_per_dept"] = (
                context["total_employees"] / context["total_departments"]
            )
        else:
            context["average_employees_per_dept"] = 0

        return context


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "employee/department-detail.html"
    context_object_name = "department"
    pk_url_kwarg = "pk"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "view_departments") and not is_hr_staff(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        return get_object_or_404(Department.active, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object
        context["page_title"] = f"Department - {department.name}"
        context["can_edit"] = UserUtilities.check_user_permission(
            self.request.user, "manage_departments"
        )
        
        employees = (
            EmployeeProfile.active.filter(user__department=department)
            .select_related("user")
            .order_by("user__employee_code")
        )
        
        context["employees"] = employees
        context["sub_departments"] = department.sub_departments.filter(is_active=True)
        context["employee_count"] = employees.count()
        context["annual_budget"] = department.budget
        context["avg_salary"] = (
            employees.aggregate(avg=Avg("basic_salary"))["avg"] or 0
        )
        
        male_count = sum(1 for emp in employees if emp.user.gender == 'MALE')
        female_count = sum(1 for emp in employees if emp.user.gender == 'FEMALE')
        context["male_count"] = male_count
        context["female_count"] = female_count
        
        if context["employee_count"] > 0:
            context["male_percentage"] = (male_count / context["employee_count"]) * 100
            context["female_percentage"] = (female_count / context["employee_count"]) * 100
        else:
            context["male_percentage"] = 0
            context["female_percentage"] = 0
        
        context["confirmed_count"] = sum(1 for emp in employees if emp.employment_status == 'CONFIRMED')
        context["probation_count"] = sum(1 for emp in employees if emp.employment_status == 'PROBATION')
        context["contract_count"] = sum(1 for emp in employees if emp.employment_status == 'CONTRACT')
        context["active_employee_count"] = (
            employees.filter(user__is_active=True).count()
        )
        
        return context

class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "employee/department-create.html"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_departments"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add New Department"
        context["form_title"] = "Department Information"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            department = form.save(commit=False)
            department.created_by = self.request.user
            department.save()

            log_user_activity(
                user=self.request.user,
                action="CREATE",
                description=f"Created new department: {department.name}",
                request=self.request,
                additional_data={
                    "department_code": department.code,
                    "department_id": department.id,
                },
            )

            messages.success(
                self.request, f'Department "{department.name}" created successfully.'
            )
            return redirect("employee:department_detail", pk=department.id)

class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "employee/department-update.html"
    pk_url_kwarg = "pk"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_departments"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Department - {self.object.name}"
        context["form_title"] = "Update Department Information"
        context["is_update"] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            old_department = Department.objects.get(pk=self.object.pk)
            department = form.save()

            changes = {}
            for field in form.changed_data:
                old_value = getattr(old_department, field, None)
                new_value = getattr(department, field, None)
                changes[field] = {
                    "old": str(old_value) if old_value else None,
                    "new": str(new_value) if new_value else None,
                }

            log_user_activity(
                user=self.request.user,
                action="UPDATE",
                description=f"Updated department: {department.name}",
                request=self.request,
                additional_data={
                    "department_code": department.code,
                    "department_id": department.id,
                    "changes": changes,
                },
            )

            messages.success(
                self.request, f'Department "{department.name}" updated successfully.'
            )
            return redirect("employee:department_detail", pk=department.id)


@login_required
@require_POST
def department_delete_view(request, pk):
    if not UserUtilities.check_user_permission(request.user, "manage_departments"):
        raise PermissionDenied

    department = get_object_or_404(Department, id=pk)

    if department.employees.filter(is_active=True).exists():
        messages.error(
            request,
            "Cannot delete department with active employees. Please reassign employees first.",
        )
        return redirect("employee:department_detail", pk=pk)

    if department.sub_departments.filter(is_active=True).exists():
        messages.error(request, "Cannot delete department with active sub-departments.")
        return redirect("employee:department_detail", pk=pk)

    with transaction.atomic():
        department_name = department.name
        department.soft_delete()

        log_user_activity(
            user=request.user,
            action="DELETE",
            description=f"Deleted department: {department_name}",
            request=request,
            additional_data={
                "department_code": department.code,
                "department_id": pk,
            },
        )

        messages.success(
            request,
            f'Department "{department_name}" has been deactivated successfully.',
        )

    return redirect("employee:department_list")


@login_required
def department_export_view(request):
    if not UserUtilities.check_user_permission(request.user, "manage_departments"):
        raise PermissionDenied

    departments = Department.objects.select_related(
        "manager", "parent_department"
    ).filter(is_active=True)
    excel_data = ExcelUtilities.export_departments_to_excel(departments)

    response = HttpResponse(
        excel_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="departments_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )

    log_user_activity(
        user=request.user,
        action="EXPORT",
        description=f"Exported {departments.count()} departments to Excel",
        request=request,
    )

    return response

class RoleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Role
    template_name = "employee/roles-list.html"
    context_object_name = "roles"
    paginate_by = 20

    def test_func(self):
        return is_admin_user(self.request.user)

    def get_queryset(self):
        return Role.active.annotate(
            user_count=Count("customuser", filter=Q(customuser__is_active=True))
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_roles"] = self.get_queryset().count()
        return context


class RoleDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Role
    template_name = "employee/roles-detail.html"
    context_object_name = "role"

    def test_func(self):
        return is_admin_user(self.request.user)

    def get_object(self):
        return get_object_or_404(Role.active, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.object

        context["users"] = (
            CustomUser.active.filter(role=role)
            .select_related("department", "employee_profile")
            .order_by("employee_code")
        )

        context["user_count"] = context["users"].count()
        return context

class ContractListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Contract
    template_name = "employee/contract-list.html"
    context_object_name = "contracts"
    paginate_by = 25

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_queryset(self):
        queryset = Contract.objects.select_related("employee", "department", "reporting_manager").order_by("-start_date")  # ← FIXED

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(contract_number__icontains=search) |
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search) |
                Q(employee__employee_code__icontains=search) |
                Q(job_title__icontains=search)
            )

        status = self.request.GET.get("status")
        contract_type = self.request.GET.get("contract_type")
        department = self.request.GET.get("department")

        if status:
            queryset = queryset.filter(status=status)
        if contract_type:
            queryset = queryset.filter(contract_type=contract_type)
        if department:
            queryset = queryset.filter(department_id=department)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contract_statuses"] = Contract.CONTRACT_STATUS
        context["contract_types"] = Contract.CONTRACT_TYPES
        context["departments"] = Department.active.all()
        context["expiring_contracts"] = ContractUtils.get_expiring_contracts(30).count()
        return context

class ContractDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Contract
    template_name = "employee/contract-detail.html"
    context_object_name = "contract"

    def test_func(self):
        return is_hr_staff(self.request.user)
    
    def get_object(self):
        return get_object_or_404(
            Contract.objects.select_related(
                "employee", "department", "reporting_manager", "created_by", "terminated_by"
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self.object

        context["days_remaining"] = contract.days_remaining
        context["contract_duration"] = contract.contract_duration_days
        context["is_expired"] = contract.is_expired
        context["can_edit"] = is_hr_staff(self.request.user)
        context["can_delete"] = is_hr_staff(self.request.user)

        context["recent_activities"] = []

        return context

class ContractCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "employee/contract-create.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create New Contract"
        context["employees"] = (
            CustomUser.active.filter(employee_profile__isnull=False)
            .select_related("employee_profile")
            .order_by("first_name", "last_name")
        )
        context["departments"] = Department.active.all().order_by("name")

        context["managers"] = CustomUser.active.all().order_by(
            "first_name", "last_name"
        )

        context["contract_types"] = (
            Contract.CONTRACT_TYPES
        )  
        context["contract_statuses"] = (
            Contract.CONTRACT_STATUS
        )  

        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        if not form.instance.contract_number:
            form.instance.contract_number = self.generate_contract_number()

        breakdown_keys = self.request.POST.getlist("breakdown_key[]")
        breakdown_values = self.request.POST.getlist("breakdown_value[]")

        salary_breakdown = {}
        for key, value in zip(breakdown_keys, breakdown_values):
            if key.strip() and value.strip():
                try:
                    salary_breakdown[key.strip()] = float(value)
                except ValueError:
                    pass

        if salary_breakdown:
            form.instance.salary_breakdown = salary_breakdown

        messages.success(self.request, "Contract created successfully.")
        return super().form_valid(form)

    def generate_contract_number(self):
        """Generate unique contract number"""
        import datetime

        year = datetime.datetime.now().year
        count = Contract.objects.filter(created_at__year=year).count() + 1
        return f"CON-{year}-{count:04d}"

    def get_success_url(self):
        return reverse("employee:contract_detail", kwargs={"pk": self.object.pk})

class ContractUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "employee/contract-create.html"

    def test_func(self):
        return is_hr_staff(self.request.user)
    
    def get_object(self):
        return get_object_or_404(Contract.objects, pk=self.kwargs["pk"])  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Update Contract"
        context["contract"] = self.object
        context["employees"] = CustomUser.active.filter(
            employee_profile__isnull=False
        ).select_related("employee_profile").order_by("first_name", "last_name")
        context["departments"] = Department.active.all().order_by("name")
        context["managers"] = CustomUser.active.filter(
            role__name__in=["MANAGER", "HR_MANAGER", "ADMIN"]
        ).order_by("first_name", "last_name")
        context["contract_types"] = Contract.CONTRACT_TYPES
        context["contract_statuses"] = Contract.CONTRACT_STATUS
        return context

    def form_valid(self, form):
        # Handle salary breakdown
        breakdown_keys = self.request.POST.getlist('breakdown_key[]')
        breakdown_values = self.request.POST.getlist('breakdown_value[]')
        
        salary_breakdown = {}
        for key, value in zip(breakdown_keys, breakdown_values):
            if key.strip() and value.strip():
                try:
                    salary_breakdown[key.strip()] = float(value)
                except ValueError:
                    pass
        
        form.instance.salary_breakdown = salary_breakdown

        messages.success(self.request, "Contract updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employee:contract_detail", kwargs={"pk": self.object.pk})


class ContractRenewalView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Contract
    form_class = ContractRenewalForm
    template_name = "employee/contract-create.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.original_contract = get_object_or_404(
            Contract.active, pk=self.kwargs["pk"]
        )
        kwargs["original_contract"] = self.original_contract
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Renew Contract"
        context["original_contract"] = self.original_contract
        context["is_renewal"] = True
        context["employees"] = CustomUser.active.filter(
            employee_profile__isnull=False
        ).select_related("employee_profile").order_by("first_name", "last_name")
        context["departments"] = Department.active.all().order_by("name")
        context["managers"] = CustomUser.active.filter(
            role__name__in=["MANAGER", "HR_MANAGER", "ADMIN"]
        ).order_by("first_name", "last_name")
        context["contract_types"] = Contract.CONTRACT_TYPES
        context["contract_statuses"] = Contract.CONTRACT_STATUS
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        with transaction.atomic():
            new_contract = form.save()
            self.original_contract.status = "RENEWED"
            self.original_contract.save(update_fields=["status"])

        messages.success(self.request, "Contract renewed successfully.")
        return redirect("employee:contract_detail", pk=new_contract.pk)

class EducationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Education
    form_class = EducationForm
    template_name = "employee/education-create.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        employee_id = self.kwargs.get("employee_id")
        if employee_id:
            initial["employee"] = get_object_or_404(CustomUser.active, pk=employee_id)
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Education record added successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "employee:employee_detail",
            kwargs={"pk": self.object.employee.employee_profile.pk},
        )


class EducationUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Education
    form_class = EducationForm
    template_name = "employee/education-update.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(Education.active, pk=self.kwargs["pk"])

    def form_valid(self, form):
        messages.success(self.request, "Education record updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "employee:employee_detail",
            kwargs={"pk": self.object.employee.employee_profile.pk},
        )

class EducationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Education
    template_name = "employee/education-list.html"
    context_object_name = "education_records"
    paginate_by = 25

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_queryset(self):
        queryset = Education.objects.select_related(
            "employee", "employee__department", "verified_by"
        ).order_by("-completion_year", "employee__first_name")

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search) |
                Q(employee__employee_code__icontains=search) |
                Q(qualification__icontains=search) |
                Q(institution__icontains=search)
            )

        education_level = self.request.GET.get("education_level")
        is_verified = self.request.GET.get("is_verified")

        if education_level:
            queryset = queryset.filter(education_level=education_level)
        if is_verified == "true":
            queryset = queryset.filter(is_verified=True)
        elif is_verified == "false":
            queryset = queryset.filter(is_verified=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["education_levels"] = Education.EDUCATION_LEVELS
        context["total_records"] = self.get_queryset().count()
        context["verified_count"] = self.get_queryset().filter(is_verified=True).count()
        context["unverified_count"] = self.get_queryset().filter(is_verified=False).count()
        return context

class EducationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Education
    template_name = "employee/education-detail.html"
    context_object_name = "education"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(
            Education.active.select_related(
                "employee", "employee__department", "verified_by", "created_by"
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        education = self.object

        context["can_verify"] = not education.is_verified and is_hr_staff(
            self.request.user
        )
        context["can_edit"] = is_hr_staff(self.request.user)

        return context


class BulkEmployeeUploadView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "employee/bulk-upload.html"

    def test_func(self):
        return is_admin_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = BulkEmployeeImportForm()
        return context

    def post(self, request, *args, **kwargs):
        form = BulkEmployeeImportForm(request.POST, request.FILES)

        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            update_existing = form.cleaned_data["update_existing"]

            try:
                results = ImportUtils.process_employee_csv(csv_file, update_existing)

                if results["success"] > 0:
                    messages.success(
                        request,
                        f"Successfully processed {results['success']} employees.",
                    )

                if results["errors"] > 0:
                    messages.warning(
                        request, f"{results['errors']} errors occurred during import."
                    )

                    for error in results["error_details"][:5]:
                        messages.error(request, error)

                return redirect("employee:employee_list")

            except Exception as e:
                messages.error(request, f"Import failed: {str(e)}")

        return self.render_to_response({"form": form})


@login_required
@user_passes_test(is_hr_staff)
def advanced_search_view(request):
    form = EmployeeSearchForm(request.GET)
    employees = []

    if form.is_valid():
        search_query = form.cleaned_data.get("search_query")
        department = form.cleaned_data.get("department")
        employment_status = form.cleaned_data.get("employment_status")
        grade_level = form.cleaned_data.get("grade_level")
        hire_date_from = form.cleaned_data.get("hire_date_from")
        hire_date_to = form.cleaned_data.get("hire_date_to")
        is_active = form.cleaned_data.get("is_active")

        queryset = EmployeeProfile.objects.all()

        if search_query:
            queryset = EmployeeUtils.search_employees(
                search_query, department, employment_status, grade_level
            )
        else:
            if department:
                queryset = queryset.filter(user__department=department)
            if employment_status:
                queryset = queryset.filter(employment_status=employment_status)
            if grade_level:
                queryset = queryset.filter(grade_level=grade_level)

        if hire_date_from:
            queryset = queryset.filter(user__hire_date__gte=hire_date_from)
        if hire_date_to:
            queryset = queryset.filter(user__hire_date__lte=hire_date_to)

        if is_active == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active == "false":
            queryset = queryset.filter(is_active=False)

        employees = queryset.select_related(
            "user", "user__department", "user__role"
        ).order_by("user__employee_code")

    paginator = Paginator(employees, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "form": form,
        "employees": page_obj,
        "total_results": len(employees) if employees else 0,
    }

    return render(request, "employee/employee-list.html", context)


@login_required
@user_passes_test(is_hr_staff)
def employee_hierarchy_view(request):
    departments = Department.active.prefetch_related(
        "customuser_set__employee_profile"
    ).order_by("name")

    hierarchy_data = []
    for dept in departments:
        dept_employees = dept.customuser_set.filter(
            is_active=True, employee_profile__is_active=True
        ).select_related("employee_profile", "manager")

        managers = dept_employees.filter(manager__isnull=True)

        dept_data = {
            "department": dept,
            "managers": [],
            "total_employees": dept_employees.count(),
        }

        for manager in managers:
            subordinates = dept_employees.filter(manager=manager)
            dept_data["managers"].append(
                {"manager": manager, "subordinates": subordinates}
            )

        hierarchy_data.append(dept_data)

    context = {
        "hierarchy_data": hierarchy_data,
        "total_departments": departments.count(),
        "total_employees": EmployeeProfile.active.count(),
    }

    return render(request, "employee/employee-hierarchy.html", context)


@login_required
@user_passes_test(is_hr_staff)
def export_employees_csv(request):
    queryset = EmployeeProfile.active.select_related(
        "user", "user__department"
    ).order_by("user__employee_code")

    search_query = request.GET.get("search")
    department = request.GET.get("department")
    employment_status = request.GET.get("employment_status")
    grade_level = request.GET.get("grade_level")

    if search_query:
        queryset = EmployeeUtils.search_employees(
            search_query, department, employment_status, grade_level
        )
    else:
        if department:
            queryset = queryset.filter(user__department_id=department)
        if employment_status:
            queryset = queryset.filter(employment_status=employment_status)
        if grade_level:
            queryset = queryset.filter(grade_level=grade_level)

    return ExportUtils.export_employees_to_csv(queryset)


@login_required
@user_passes_test(is_hr_staff)
def export_employees_excel(request):
    queryset = EmployeeProfile.active.select_related(
        "user", "user__department"
    ).order_by("user__employee_code")

    search_query = request.GET.get("search")
    department = request.GET.get("department")
    employment_status = request.GET.get("employment_status")
    grade_level = request.GET.get("grade_level")

    if search_query:
        queryset = EmployeeUtils.search_employees(
            search_query, department, employment_status, grade_level
        )
    else:
        if department:
            queryset = queryset.filter(user__department_id=department)
        if employment_status:
            queryset = queryset.filter(employment_status=employment_status)
        if grade_level:
            queryset = queryset.filter(grade_level=grade_level)

    return ExportUtils.export_employees_to_excel(queryset)


@login_required
@user_passes_test(is_hr_staff)
def export_contracts_csv(request):
    queryset = Contract.active.select_related("employee", "department").order_by(
        "-start_date"
    )

    status = request.GET.get("status")
    contract_type = request.GET.get("contract_type")
    department = request.GET.get("department")

    if status:
        queryset = queryset.filter(status=status)
    if contract_type:
        queryset = queryset.filter(contract_type=contract_type)
    if department:
        queryset = queryset.filter(department_id=department)

    return ExportUtils.export_contracts_to_csv(queryset)


@login_required
@user_passes_test(is_admin_user)
def bulk_notification_view(request):
    if request.method == "POST":
        recipient_type = request.POST.get("recipient_type")
        subject = request.POST.get("subject")
        message = request.POST.get("message")

        recipients = []

        if recipient_type == "all_employees":
            recipients = CustomUser.active.filter(
                employee_profile__is_active=True
            ).values_list("email", flat=True)
        elif recipient_type == "probation_employees":
            recipients = CustomUser.active.filter(
                employee_profile__employment_status="PROBATION",
                employee_profile__is_active=True,
            ).values_list("email", flat=True)
        elif recipient_type == "department":
            department_id = request.POST.get("department_id")
            if department_id:
                recipients = CustomUser.active.filter(
                    department_id=department_id, employee_profile__is_active=True
                ).values_list("email", flat=True)

        if recipients:
            messages.success(
                request, f"Notification sent to {len(recipients)} recipients."
            )
        else:
            messages.warning(request, "No recipients found.")

        return redirect("employee:bulk_notification")

    context = {
        "departments": Department.active.all(),
        "probation_count": EmployeeProfile.active.filter(
            employment_status="PROBATION"
        ).count(),
        "total_employees": EmployeeProfile.active.count(),
    }
    return render(request, "employee/bulk-notification.html", context)


@login_required
@user_passes_test(is_admin_user)
def user_sessions_view(request):
    context = {
        "active_sessions": CustomUser.active.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        )
        .select_related("employee_profile")
        .order_by("-last_login"),
    }
    return render(request, "employee/user-sessions.html", context)


@login_required
@user_passes_test(is_admin_user)
def user_activity_log_view(request):
    context = {
        "recent_activities": EmployeeProfile.objects.filter(is_active=True)
        .select_related("user", "created_by")
        .order_by("-updated_at")[:50],
    }
    return render(request, "employee/activity-log.html", context)


@login_required
@user_passes_test(is_admin_user)
def audit_log_view(request):
    context = {
        "employee_changes": EmployeeProfile.objects.select_related(
            "user", "created_by"
        ).order_by("-updated_at")[:100],
        "contract_changes": Contract.objects.select_related(
            "employee", "created_by"
        ).order_by("-updated_at")[:100],
    }
    return render(request, "employee/audit-log.html", context)

@login_required
@user_passes_test(is_admin_user)
def session_management_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")

        if action == "terminate_session" and user_id:
            try:
                user = CustomUser.objects.get(pk=user_id)
                messages.success(
                    request, f"Session terminated for {user.get_full_name()}"
                )
            except CustomUser.DoesNotExist:
                messages.error(request, "User not found")

        return redirect("employee:session_management")

    context = {
        "active_users": CustomUser.active.filter(
            last_login__gte=timezone.now() - timedelta(hours=24)
        )
        .select_related("employee_profile")
        .order_by("-last_login"),
    }
    return render(request, "employee/session-management.html", context)


@login_required
@require_http_methods(["POST"])
@user_passes_test(is_admin_user)
def bulk_salary_update(request):
    employee_ids = request.POST.getlist("employee_ids")
    percentage_increase = request.POST.get("percentage_increase")

    try:
        percentage = float(percentage_increase)
        updated_count = BulkOperationUtils.bulk_update_salaries(
            employee_ids, percentage
        )
        messages.success(request, f"Updated salaries for {updated_count} employees.")
    except (ValueError, TypeError):
        messages.error(request, "Invalid percentage value.")
    except Exception as e:
        messages.error(request, f"Error updating salaries: {str(e)}")

    return redirect("employee:employee_list")


@login_required
@require_http_methods(["POST"])
@user_passes_test(is_admin_user)
def bulk_confirm_employees(request):
    employee_ids = request.POST.getlist("employee_ids")

    try:
        updated_count = BulkOperationUtils.bulk_confirm_employees(employee_ids)
        messages.success(request, f"Confirmed {updated_count} employees.")
    except Exception as e:
        messages.error(request, f"Error confirming employees: {str(e)}")

    return redirect("employee:employee_list")


@login_required
@require_http_methods(["POST"])
@user_passes_test(is_admin_user)
def bulk_deactivate_employees(request):
    employee_ids = request.POST.getlist("employee_ids")

    try:
        updated_count = BulkOperationUtils.bulk_deactivate_employees(employee_ids)
        messages.success(request, f"Deactivated {updated_count} employees.")
    except Exception as e:
        messages.error(request, f"Error deactivating employees: {str(e)}")

    return redirect("employee:employee_list")


@login_required
@user_passes_test(is_hr_staff)
def activate_contract(request, pk):
    contract = get_object_or_404(Contract.active, pk=pk)

    if contract.status != "DRAFT":
        messages.error(request, "Only draft contracts can be activated.")
        return redirect("employee:contract_detail", pk=pk)

    if request.method == "POST":
        try:
            contract.activate_contract()
            messages.success(
                request,
                f"Contract {contract.contract_number} has been activated successfully.",
            )
        except Exception as e:
            messages.error(request, f"Error activating contract: {str(e)}")

    return redirect("employee:contract_detail", pk=pk)


@login_required
@user_passes_test(is_hr_staff)
def terminate_contract(request, pk):
    contract = get_object_or_404(Contract.active, pk=pk)

    if contract.status != "ACTIVE":
        messages.error(request, "Only active contracts can be terminated.")
        return redirect("employee:contract_detail", pk=pk)

    if request.method == "POST":
        termination_reason = request.POST.get("termination_reason", "").strip()

        if not termination_reason:
            messages.error(request, "Termination reason is required.")
            return redirect("employee:contract_detail", pk=pk)

        try:
            contract.terminate_contract(
                terminated_by=request.user, reason=termination_reason
            )
            messages.success(
                request,
                f"Contract {contract.contract_number} has been terminated successfully.",
            )
        except Exception as e:
            messages.error(request, f"Error terminating contract: {str(e)}")

    return redirect("employee:contract_detail", pk=pk)


@login_required
@user_passes_test(is_hr_staff)
def export_contracts_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="contracts_export.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Contract Number",
            "Employee Name",
            "Employee Code",
            "Contract Type",
            "Status",
            "Job Title",
            "Department",
            "Start Date",
            "End Date",
            "Basic Salary",
            "Working Hours",
            "Created Date",
        ]
    )

    contracts = Contract.active.select_related("employee", "department").order_by(
        "-created_at"
    )

    for contract in contracts:
        writer.writerow(
            [
                contract.contract_number,
                contract.employee.get_full_name(),
                contract.employee.employee_code,
                contract.get_contract_type_display(),
                contract.get_status_display(),
                contract.job_title,
                contract.department.name if contract.department else "",
                contract.start_date.strftime("%Y-%m-%d") if contract.start_date else "",
                contract.end_date.strftime("%Y-%m-%d") if contract.end_date else "",
                str(contract.basic_salary),
                str(contract.working_hours),
                contract.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    return response

@login_required
@require_http_methods(["POST"])
@user_passes_test(is_hr_staff)
def verify_education(request, pk):
    education = get_object_or_404(Education.active, pk=pk)

    try:
        education.verify_education(request.user)
        messages.success(request, "Education record verified successfully.")
    except Exception as e:
        messages.error(request, f"Error verifying education: {str(e)}")

    return redirect(
        "employee:employee_detail", pk=education.employee.employee_profile.pk
    )


@login_required
def dashboard_widgets_ajax(request):
    if not is_admin_user(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    widget_type = request.GET.get("widget")

    if widget_type == "employee_stats":
        data = EmployeeUtils.get_employee_summary_stats()
    elif widget_type == "contract_stats":
        data = ContractUtils.get_contract_summary_stats()
    elif widget_type == "probation_alerts":
        data = {
            "count": NotificationUtils.get_probation_notifications().count(),
            "employees": list(
                NotificationUtils.get_probation_notifications().values(
                    "user__first_name", "user__last_name", "probation_end_date"
                )
            ),
        }
    elif widget_type == "contract_alerts":
        data = {
            "count": NotificationUtils.get_contract_expiry_notifications().count(),
            "contracts": list(
                NotificationUtils.get_contract_expiry_notifications().values(
                    "contract_number",
                    "employee__first_name",
                    "employee__last_name",
                    "end_date",
                )
            ),
        }
    else:
        return JsonResponse({"error": "Invalid widget type"}, status=400)

    return JsonResponse(data)


@login_required
def quick_stats_ajax(request):
    if not is_hr_staff(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    stats = {
        "total_employees": EmployeeProfile.active.count(),
        "total_departments": Department.active.count(),
        "probation_employees": EmployeeProfile.active.filter(
            employment_status="PROBATION"
        ).count(),
        "active_contracts": Contract.active.filter(status="ACTIVE").count(),
        "expiring_contracts": ContractUtils.get_expiring_contracts(30).count(),
    }

    return JsonResponse(stats)


@login_required
def employee_autocomplete_ajax(request):
    if not is_hr_staff(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    query = request.GET.get("q", "")

    if len(query) < 2:
        return JsonResponse({"results": []})

    employees = CustomUser.active.filter(
        Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(employee_code__icontains=query)
        | Q(email__icontains=query)
    ).select_related("employee_profile")[:10]

    results = []
    for emp in employees:
        results.append(
            {
                "id": emp.pk,
                "text": f"{emp.employee_code} - {emp.get_full_name()}",
                "email": emp.email,
                "department": emp.department.name if emp.department else "",
            }
        )

    return JsonResponse({"results": results})


@login_required
def validate_employee_code_ajax(request):
    if not is_hr_staff(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    employee_code = request.GET.get("employee_code", "")
    exclude_id = request.GET.get("exclude_id")

    if not employee_code:
        return JsonResponse({"valid": False, "message": "Employee code is required"})

    queryset = CustomUser.objects.filter(employee_code=employee_code)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    exists = queryset.exists()

    return JsonResponse(
        {
            "valid": not exists,
            "message": (
                "Employee code already exists"
                if exists
                else "Employee code is available"
            ),
        }
    )


@login_required
def validate_email_ajax(request):
    if not is_hr_staff(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    email = request.GET.get("email", "")
    exclude_id = request.GET.get("exclude_id")

    if not email:
        return JsonResponse({"valid": False, "message": "Email is required"})

    queryset = CustomUser.objects.filter(email=email)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    exists = queryset.exists()

    return JsonResponse(
        {
            "valid": not exists,
            "message": "Email already exists" if exists else "Email is available",
        }
    )


@login_required
def health_check_view(request):
    if not is_admin_user(request.user):
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        db_status = "OK"
        EmployeeProfile.objects.first()
    except Exception as e:
        db_status = f"ERROR: {str(e)}"

    health_data = {
        "status": "OK" if db_status == "OK" else "ERROR",
        "timestamp": timezone.now().isoformat(),
        "database": db_status,
        "total_employees": EmployeeProfile.active.count() if db_status == "OK" else 0,
        "total_contracts": Contract.active.count() if db_status == "OK" else 0,
    }

    return JsonResponse(health_data)


@login_required
@user_passes_test(is_hr_staff)
def probation_report_view(request):
    probation_employees = ReportUtils.generate_probation_report()

    context = {
        "probation_employees": probation_employees,
        "total_count": probation_employees.count(),
        "report_date": timezone.now().date(),
    }
    return render(request, "employee/probation-report.html", context)


@login_required
@user_passes_test(is_hr_staff)
def contract_expiry_report_view(request):
    days = int(request.GET.get("days", 30))
    expiring_contracts = ReportUtils.generate_contract_expiry_report(days)

    context = {
        "expiring_contracts": expiring_contracts,
        "total_count": expiring_contracts.count(),
        "days": days,
        "report_date": timezone.now().date(),
    }

    return render(request, "employee/contract-expiry-report.html", context)


@login_required
@user_passes_test(is_admin_user)
def salary_analysis_report_view(request):
    salary_analysis = ReportUtils.generate_salary_analysis_report()

    context = {
        "salary_analysis": salary_analysis,
        "report_date": timezone.now().date(),
    }

    return render(request, "employee/salary-analysis-report.html", context)


@login_required
def employee_calendar(request):
    now = datetime.now()
    year_param = request.GET.get("year", str(now.year))
    year = int(year_param.replace(",", ""))
    month = int(request.GET.get("month", now.month))

    User = get_user_model()
    employee_id = request.GET.get("employee_id")
    if request.user.is_staff and employee_id:
        try:
            employee = User.objects.get(id=employee_id)
        except User.DoesNotExist:
            employee = request.user
    else:
        employee = request.user

    start_date = (now - timedelta(days=30)).replace(day=1)
    end_date = (now + timedelta(days=60)).replace(day=28)

    attendance_records = Attendance.objects.filter(
        employee=employee, date__gte=start_date, date__lte=end_date
    )

    payroll_periods = PayrollPeriod.objects.filter(
        start_date__lte=end_date, end_date__gte=start_date
    )

    attendance_events = []
    for record in attendance_records:
        color_class = "bg-success-subtle"
        if record.status == "ABSENT":
            color_class = "bg-danger-subtle"
        elif record.status == "LATE":
            color_class = "bg-warning-subtle"
        elif record.status == "HALF_DAY":
            color_class = "bg-info-subtle"
        elif record.status == "LEAVE":
            color_class = "bg-secondary-subtle"
        elif record.status == "HOLIDAY":
            color_class = "bg-primary-subtle"

        event = {
            "id": f"attendance-{record.id}",
            "title": f"Attendance: {record.get_status_display()}",
            "start": record.date.strftime("%Y-%m-%d"),
            "className": color_class,
            "borderColor": color_class.replace("-subtle", ""),
            "description": f"Work time: {record.formatted_work_time}",
            "type": "attendance",
            "extendedProps": {
                "attendance_id": str(record.id),
                "status": record.status,
                "first_in": (
                    record.first_in_time.strftime("%H:%M")
                    if record.first_in_time
                    else "N/A"
                ),
                "last_out": (
                    record.last_out_time.strftime("%H:%M")
                    if record.last_out_time
                    else "N/A"
                ),
                "work_time": record.formatted_work_time,
                "performance": f"{record.performance_score}%",
                "punctuality": f"{record.punctuality_score}%",
            },
        }
        attendance_events.append(event)

    payroll_events = []
    for period in payroll_periods:
        if period.processing_date:
            event = {
                "id": f"payroll-processing-{period.id}",
                "title": f"Payroll Processing: {period.period_name}",
                "start": period.processing_date.strftime("%Y-%m-%d"),
                "className": "bg-info-subtle",
                "borderColor": "bg-info",
                "description": f"Processing date for {period.period_name}",
                "type": "payroll",
                "extendedProps": {
                    "payroll_id": str(period.id),
                    "period_name": period.period_name,
                    "status": period.status,
                    "event_type": "processing",
                },
            }
            payroll_events.append(event)

        if period.cutoff_date:
            event = {
                "id": f"payroll-cutoff-{period.id}",
                "title": f"Payroll Cutoff: {period.period_name}",
                "start": period.cutoff_date.strftime("%Y-%m-%d"),
                "className": "bg-warning-subtle",
                "borderColor": "bg-warning",
                "description": f"Cutoff date for {period.period_name}",
                "type": "payroll",
                "extendedProps": {
                    "payroll_id": str(period.id),
                    "period_name": period.period_name,
                    "status": period.status,
                    "event_type": "cutoff",
                },
            }
            payroll_events.append(event)

    monthly_summary = MonthlyAttendanceSummary.objects.filter(
        employee=employee, year=year, month=month
    ).first()

    if not monthly_summary:
        _, num_days = calendar.monthrange(year, month)
        working_days = 0
        for day in range(1, num_days + 1):
            weekday = calendar.weekday(year, month, day)
            if weekday < 5:
                working_days += 1

        class DefaultSummary:
            def __init__(self):
                self.working_days = working_days
                self.attended_days = 0
                self.late_days = 0
                self.absent_days = 0
                self.attendance_percentage = 0
                self.punctuality_score = 0
                self.efficiency_score = 0

        monthly_summary = DefaultSummary()

    all_events = attendance_events + payroll_events

    month_name = calendar.month_name[month]

    context = {
        "employee": employee,
        "events_json": json.dumps(all_events),
        "monthly_summary": monthly_summary,
        "year": year,
        "month": month,
        "month_name": month_name,
    }

    all_employees = User.objects.filter(is_active=True).order_by("first_name")
    context["all_employees"] = all_employees

    return render(request, "employee/calendar.html", context)
