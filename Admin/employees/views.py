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
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
import json
from datetime import datetime, timedelta
from decimal import Decimal

from accounts.models import CustomUser, Department, Role, SystemConfiguration
from .models import EmployeeProfile, Education, Contract
from .forms import (
    EmployeeProfileForm,
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
        template_name = "dashboard-analytics.html"

        employee_stats = EmployeeUtils.get_employee_summary_stats()
        contract_stats = ContractUtils.get_contract_summary_stats()

        probation_ending = EmployeeProfile.objects.filter(
            employment_status="PROBATION",
            probation_end_date__lte=timezone.now().date() + timedelta(days=30),
            is_active=True,
        ).count()

        contracts_expiring = ContractUtils.get_expiring_contracts(30).count()

        recent_employees = (
            EmployeeProfile.objects.filter(is_active=True)
            .select_related("user", "user__department")
            .order_by("-created_at")[:5]
        )

        context = {
            "employee_stats": employee_stats,
            "contract_stats": contract_stats,
            "probation_ending": probation_ending,
            "contracts_expiring": contracts_expiring,
            "recent_employees": recent_employees,
            "total_departments": Department.active.count(),
            "total_roles": Role.active.count(),
        }
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

    return render(request, "dashboard-analytics.html", context)


class EmployeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = EmployeeProfile
    template_name = "apps-school-students.html"
    context_object_name = "employees"
    paginate_by = 25

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_queryset(self):
        queryset = EmployeeProfile.active.select_related(
            "user", "user__department", "user__role"
        ).order_by("user__employee_code")

        search_query = self.request.GET.get("search")
        department = self.request.GET.get("department")
        employment_status = self.request.GET.get("employment_status")
        grade_level = self.request.GET.get("grade_level")

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

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = EmployeeSearchForm(self.request.GET)
        context["departments"] = Department.active.all()
        context["employment_statuses"] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        context["grade_levels"] = EmployeeProfile.GRADE_LEVELS
        context["total_employees"] = self.get_queryset().count()
        return context


class EmployeeDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = EmployeeProfile
    template_name = "apps-school-parents.html"
    context_object_name = "employee"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(
            EmployeeProfile.active.select_related(
                "user", "user__department", "user__role", "user__manager"
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object

        context["education_records"] = Education.active.filter(
            employee=employee.user
        ).order_by("-completion_year")

        context["contracts"] = Contract.active.filter(employee=employee.user).order_by(
            "-start_date"
        )

        context["years_of_service"] = employee.years_of_service
        context["probation_days_remaining"] = (
            CalculationUtils.calculate_probation_days_remaining(
                employee.probation_end_date
            )
            if employee.probation_end_date
            else None
        )

        context["age"] = CalculationUtils.calculate_age(employee.date_of_birth)

        return context


class EmployeeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = EmployeeProfile
    form_class = EmployeeProfileForm
    template_name = "apps-school-admission-form.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Employee profile created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employee:employee_detail", kwargs={"pk": self.object.pk})


class EmployeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = EmployeeProfile
    form_class = EmployeeProfileForm
    template_name = "apps-school-admission-form.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(EmployeeProfile.active, pk=self.kwargs["pk"])

    def form_valid(self, form):
        messages.success(self.request, "Employee profile updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employee:employee_detail", kwargs={"pk": self.object.pk})


class DepartmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Department
    template_name = "apps-school-courses.html"
    context_object_name = "departments"
    paginate_by = 20

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_queryset(self):
        return Department.active.annotate(
            employee_count=Count(
                "customuser__employee_profile",
                filter=Q(customuser__employee_profile__is_active=True),
            )
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_departments"] = self.get_queryset().count()
        return context


class DepartmentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Department
    template_name = "apps-school-courses.html"
    context_object_name = "department"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(Department.active, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object

        context["employees"] = (
            EmployeeProfile.active.filter(user__department=department)
            .select_related("user")
            .order_by("user__employee_code")
        )

        context["employee_count"] = context["employees"].count()
        context["avg_salary"] = (
            context["employees"].aggregate(avg=Avg("basic_salary"))["avg"] or 0
        )

        return context


class RoleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Role
    template_name = "apps-teacher.html"
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
    template_name = "apps-teacher.html"
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
    template_name = "ui-tables-datatables.html"
    context_object_name = "contracts"
    paginate_by = 25

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_queryset(self):
        queryset = Contract.active.select_related("employee", "department").order_by(
            "-start_date"
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
    template_name = "ui-tables-datatables.html"
    context_object_name = "contract"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(
            Contract.active.select_related(
                "employee", "department", "reporting_manager"
            ),
            pk=self.kwargs["pk"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contract = self.object

        context["days_remaining"] = contract.days_remaining
        context["contract_duration"] = contract.contract_duration_days
        context["is_expired"] = contract.is_expired

        return context


class ContractCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "ui-form-elements.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Contract created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employee:contract_detail", kwargs={"pk": self.object.pk})


class ContractUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = "ui-form-elements.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_object(self):
        return get_object_or_404(Contract.active, pk=self.kwargs["pk"])

    def form_valid(self, form):
        messages.success(self.request, "Contract updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employee:contract_detail", kwargs={"pk": self.object.pk})


class ContractRenewalView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Contract
    form_class = ContractRenewalForm
    template_name = "ui-form-elements.html"

    def test_func(self):
        return is_hr_staff(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.original_contract = get_object_or_404(
            Contract.active, pk=self.kwargs["pk"]
        )
        kwargs["original_contract"] = self.original_contract
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        with transaction.atomic():
            new_contract = form.save()
            self.original_contract.status = "RENEWED"
            self.original_contract.save(update_fields=["status"])

        messages.success(self.request, "Contract renewed successfully.")
        return redirect("employee:contract_detail", pk=new_contract.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["original_contract"] = self.original_contract
        context["is_renewal"] = True
        return context


class EducationCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Education
    form_class = EducationForm
    template_name = "ui-form-elements.html"

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
    template_name = "ui-form-elements.html"

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


class BulkEmployeeUploadView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "ui-form-file-uploads.html"

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

    return render(request, "apps-school-students.html", context)


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

    return render(request, "ui-treeview.html", context)


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

    return render(request, "apps-email.html", context)


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
    return render(request, "ui-tables-datatables.html", context)


@login_required
@user_passes_test(is_admin_user)
def user_activity_log_view(request):
    context = {
        "recent_activities": EmployeeProfile.objects.filter(is_active=True)
        .select_related("user", "created_by")
        .order_by("-updated_at")[:50],
    }
    return render(request, "ui-tables-datatables.html", context)


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
    return render(request, "ui-tables-datatables.html", context)


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
    return render(request, "ui-tables-datatables.html", context)


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
@require_http_methods(["POST"])
@user_passes_test(is_hr_staff)
def activate_contract(request, pk):
    contract = get_object_or_404(Contract.active, pk=pk)

    try:
        contract.activate_contract()
        messages.success(
            request, f"Contract {contract.contract_number} activated successfully."
        )
    except Exception as e:
        messages.error(request, f"Error activating contract: {str(e)}")

    return redirect("employee:contract_detail", pk=pk)


@login_required
@require_http_methods(["POST"])
@user_passes_test(is_hr_staff)
def terminate_contract(request, pk):
    contract = get_object_or_404(Contract.active, pk=pk)
    termination_reason = request.POST.get("termination_reason", "")

    try:
        contract.terminate_contract(request.user, termination_reason)
        messages.success(
            request, f"Contract {contract.contract_number} terminated successfully."
        )
    except Exception as e:
        messages.error(request, f"Error terminating contract: {str(e)}")

    return redirect("employee:contract_detail", pk=pk)


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

    return render(request, "ui-tables-datatables.html", context)


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

    return render(request, "ui-tables-datatables.html", context)


@login_required
@user_passes_test(is_admin_user)
def salary_analysis_report_view(request):
    salary_analysis = ReportUtils.generate_salary_analysis_report()

    context = {
        "salary_analysis": salary_analysis,
        "report_date": timezone.now().date(),
    }

    return render(request, "ui-tables-datatables.html", context)
