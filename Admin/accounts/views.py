import pandas as pd
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.views import View
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.urls import reverse_lazy, reverse
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
import hashlib
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetView,
    PasswordResetConfirmView,
)
import json
from datetime import datetime, timedelta
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str

from .models import (
    CustomUser,
    Department,
    Role,
    AuditLog,
    SystemConfiguration,
    UserSession,
    PasswordResetToken,
    APIKey,
)
from employees.models import EmployeeProfile

from .analytics import UnifiedAnalytics
from .forms import (
    CustomLoginForm,
    EmployeeRegistrationForm,
    EmployeeUpdateForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    DepartmentForm,
    RoleForm,
    ProfileUpdateForm,
    BulkEmployeeUploadForm,
    UserSearchForm,
    AdvancedUserFilterForm,
    SystemConfigurationForm,
)
from .utils import (
    generate_employee_code,
    generate_secure_password,
    validate_password_strength,
    log_user_activity,
    create_user_session,
    terminate_user_sessions,
    create_password_reset_token,
    send_password_reset_email,
    send_welcome_email,
    validate_employee_data,
    search_users,
    get_user_dashboard_data,
    UserUtilities,
    ExcelUtilities,
    SystemUtilities,
    get_client_ip,
    get_user_agent,
)
from .permissions import EmployeeAccessMixin

User = get_user_model()

class CustomLoginView(TemplateView):
    template_name = "accounts/auth-signin.html"
    form_class = CustomLoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = self.form_class()
        context["page_title"] = "Sign In"
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            if user.must_change_password:
                request.session["temp_user_id"] = user.id
                messages.warning(
                    request, "You must change your password before continuing."
                )
                return redirect("accounts:force_password_change")

            login(request, user, backend='accounts.manager.MultiFieldAuthBackend')

            user_session = create_user_session(user, request)

            log_user_activity(
                user=user,
                action="LOGIN",
                description=f"User logged in successfully from {get_client_ip(request)}",
                request=request,
            )

            remember_me = form.cleaned_data.get("remember_me")
            if remember_me:
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            else:
                request.session.set_expiry(0)

            next_url = request.GET.get("next", "accounts:dashboard")
            return redirect(next_url)

        context = self.get_context_data()
        context["form"] = form
        return render(request, self.template_name, context)


@login_required
def logout_view(request):
    user = request.user

    log_user_activity(
        user=user,
        action="LOGOUT",
        description=f"User logged out from {get_client_ip(request)}",
        request=request,
    )

    session_key = request.session.session_key
    if session_key:
        try:
            user_session = UserSession.objects.get(
                user=user,
                session_key_hash=hashlib.sha256(session_key.encode()).hexdigest(),
                is_active=True,
            )
            user_session.terminate()
        except UserSession.DoesNotExist:
            pass

    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")

@login_required
def dashboard_view(request):
    dashboard_data = get_user_dashboard_data(request.user)
    navigation_menu = UserUtilities.get_navigation_menu(request.user)

    context = {
        "page_title": "Dashboard",
        "dashboard_data": dashboard_data,
        "navigation_menu": navigation_menu,
        "user_permissions": UserUtilities.get_user_permissions_list(request.user),
        **UnifiedAnalytics.get_complete_dashboard_data(),
    }

    if request.user.is_superuser or (
        request.user.role and request.user.role.name in ["SUPER_ADMIN"]
    ):
        context["system_stats"] = SystemUtilities.get_system_statistics()
        template_name = "employee/employees-analytics.html"
    else:
        template_name = "index.html"

    return render(request, template_name, context)

class ForcePasswordChangeView(TemplateView):
    template_name = "accounts/auth-reset-password.html"
    form_class = CustomPasswordChangeForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("temp_user_id"): 
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.session.get("temp_user_id")
        user = get_object_or_404(User, id=user_id)
        context["form"] = self.form_class(user=user, force_change=True)
        context["page_title"] = "Change Password"
        context["force_change"] = True
        return context

    def post(self, request, *args, **kwargs):
        user_id = request.session.get("temp_user_id")
        user = get_object_or_404(User, id=user_id)
        form = self.form_class(user=user, force_change=True, data=request.POST)

        if form.is_valid():
            form.save()
            del request.session["temp_user_id"]

            login(request, user, backend='accounts.manager.MultiFieldAuthBackend')
            create_user_session(user, request)

            log_user_activity(
                user=user,
                action="PASSWORD_CHANGE",
                description="Password changed during forced password change",
                request=request,
            )

            messages.success(request, "Password changed successfully.")
            return redirect("accounts:dashboard")

        context = self.get_context_data()
        context["form"] = form
        return render(request, self.template_name, context)

class CustomPasswordResetView(PasswordResetView):
    template_name = "accounts/auth-forgot-password.html"
    form_class = CustomPasswordResetForm
    email_template_name = "accounts/emails/password_reset.html"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        try:
            user = User.objects.get(email=email, is_active=True)
            token = create_password_reset_token(user, self.request)

            if send_password_reset_email(user, token, self.request):
                messages.success(
                    self.request, "Password reset email sent successfully."
                )
            else:
                messages.error(
                    self.request,
                    "Failed to send password reset email. Please try again.",
                )

        except User.DoesNotExist:
            pass

        return redirect(self.success_url)


def password_reset_done_view(request):
    return render(
        request,
        "accounts/emails/auth-email-verify.html",  
        {
            "page_title": "Password Reset Sent",
            "message": "We have sent you an email with instructions to reset your password.",
        },
    )


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/auth-reset-password.html"
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")

    def dispatch(self, request, *args, **kwargs):
        token = kwargs.get("token")
        uidb64 = kwargs.get("uidb64")

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            reset_token = PasswordResetToken.objects.get(token=token, user=user)

            if not reset_token.is_valid():
                messages.error(request, "Invalid or expired password reset token.")
                return redirect("accounts:password_reset")

            self.reset_token = reset_token
            self.validlink = True
            self.user = user
            self.user_cache = user

            kwargs["uidb64"] = uidb64
            kwargs["token"] = token

        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
            PasswordResetToken.DoesNotExist,
        ):
            messages.error(request, "Invalid password reset token.")
            return redirect("accounts:password_reset")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["force_change"] = True
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.user
        return kwargs

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(**self.get_form_kwargs())

    def form_valid(self, form):
        user = form.save()
        self.reset_token.use_token()

        log_user_activity(
            user=user,
            action="PASSWORD_CHANGE",
            description="Password reset via email token",
            request=self.request,
        )

        messages.success(self.request, "Password reset successfully.")
        return redirect(self.success_url)


def password_reset_complete_view(request):
    return render(
        request,
        "accounts/auth-signin.html",
        {
            "page_title": "Password Reset Complete",
            "success_message": "Your password has been reset successfully. You can now log in.",
        },
    )

class EmployeeListView(LoginRequiredMixin, ListView):
    model = EmployeeProfile  
    template_name = "employee/employee-list.html"
    context_object_name = "employees"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_employees"
        ) and not UserUtilities.check_user_permission(
            request.user, "view_department_employees"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = EmployeeProfile.objects.select_related(
            "user", "user__department", "user__role", "user__manager"
        ).filter(is_active=True, user__is_active=True)

        if not self.request.user.is_superuser:
            access_mixin = EmployeeAccessMixin()
            accessible_employees = access_mixin.get_accessible_employees(
                self.request.user
            )
            queryset = queryset.filter(
                user__id__in=accessible_employees.values_list("id", flat=True)
            )

        search_query = self.request.GET.get('search')
        department = self.request.GET.get('department')
        employment_status = self.request.GET.get('employment_status')

        if search_query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__employee_code__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(user__job_title__icontains=search_query)
                | Q(user__department__name__icontains=search_query)
                | Q(user__role__display_name__icontains=search_query)
            )

        if department:
            queryset = queryset.filter(user__department_id=department)

        if employment_status:
            queryset = queryset.filter(employment_status=employment_status)

        return queryset.order_by("user__employee_code")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Employee Directory"
        context["can_add_employee"] = UserUtilities.check_user_permission(
            self.request.user, "manage_employees"
        )
        context["can_export"] = UserUtilities.check_user_permission(
            self.request.user, "manage_employees"
        )
        context["total_employees"] = self.get_queryset().count()
        context["departments"] = Department.active.all()
        context["employment_statuses"] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        return context

class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = EmployeeProfile  
    template_name = "employee/employee-detail.html"
    context_object_name = "employee"
    pk_url_kwarg = "employee_id"

    def dispatch(self, request, *args, **kwargs):
        employee_profile = self.get_object()
        employee_user = employee_profile.user
        if not request.user.can_manage_user(employee_user) and employee_user != request.user:
            if not UserUtilities.check_user_permission(
                request.user, "view_department_employees"
            ):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return EmployeeProfile.objects.select_related(
            "user", "user__department", "user__role", "user__manager"
        ).filter(is_active=True, user__is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_profile = self.object
        employee_user = employee_profile.user
        
        context["page_title"] = f"Employee Details - {employee_user.get_full_name()}"
        context["can_edit"] = self.request.user.can_manage_user(employee_user)
        context["can_delete"] = UserUtilities.check_user_permission(
            self.request.user, "manage_employees"
        )
        context["subordinates"] = employee_user.get_subordinates()
        context["recent_activities"] = AuditLog.objects.filter(user=employee_user).order_by(
            "-timestamp"
        )[:10]
        context["active_sessions"] = UserSession.objects.filter(
            user=employee_user, is_active=True
        )

        context["education_records"] = employee_user.education_records.filter(is_active=True)
        context["contracts"] = employee_user.contracts.filter(is_active=True).order_by('-start_date')
        context["employment_statuses"] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        context["grade_levels"] = EmployeeProfile.GRADE_LEVELS
        context["marital_statuses"] = EmployeeProfile.MARITAL_STATUS_CHOICES
        
        return context

class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = CustomUser
    form_class = EmployeeRegistrationForm
    template_name = "accounts/employee_registration.html"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_employees"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add New Employee"
        context["form_title"] = "Employee Registration"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            employee = form.save(commit=False)
            employee.created_by = self.request.user

            if not employee.employee_code:
                department_code = (
                    employee.department.code if employee.department else None
                )
                employee.employee_code = generate_employee_code(department_code)

            employee.username = employee.employee_code
            employee.save()

            temp_password = generate_secure_password()
            employee.set_password(temp_password)
            employee.must_change_password = True
            employee.password_changed_at = timezone.now()
            employee.save()

            employee_profile = EmployeeProfile.objects.create(
                user=employee,
                basic_salary=form.cleaned_data.get('basic_salary'),
                employment_status='PROBATION',
                probation_end_date=timezone.now().date() + timedelta(days=90),  
                grade_level='ENTRY',
                created_by=self.request.user
            )

            send_welcome_email(employee, temp_password, self.request)

            log_user_activity(
                user=self.request.user,
                action="CREATE",
                description=f"Created new employee: {employee.get_display_name()}",
                request=self.request,
                additional_data={
                    "employee_code": employee.employee_code,
                    "employee_id": employee.id,
                    "profile_id": employee_profile.id,
                },
            )

            messages.success(
                self.request,
                f"Employee {employee.get_display_name()} created successfully. Welcome email sent.",
            )
            return redirect("accounts:employee_detail", employee_id=employee_profile.id)

class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = EmployeeUpdateForm
    template_name = "employee/employee-update.html"
    pk_url_kwarg = "employee_id"

    def dispatch(self, request, *args, **kwargs):
        employee = self.get_object()
        if not request.user.can_manage_user(employee):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        employee_profile_id = self.kwargs.get("employee_id")
        try:
            employee_profile = EmployeeProfile.objects.select_related("user").get(
                pk=employee_profile_id
            )
            return employee_profile.user
        except EmployeeProfile.DoesNotExist:
            raise Http404("Employee not found")

    def get_queryset(self):
        return CustomUser.objects.select_related(
            "department", "role", "manager", "employee_profile"
        ).filter(is_active=True, employee_profile__is_active=True)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Employee - {self.object.get_full_name()}"
        context["form_title"] = "Update Employee Information"
        context["is_update"] = True
        context["departments"] = Department.active.all()
        context["roles"] = Role.active.all()
        context["managers"] = CustomUser.active.exclude(id=self.object.id)
        # REMOVE: These aren't used in our updated template
        # context["employment_statuses"] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        # context["grade_levels"] = EmployeeProfile.GRADE_LEVELS
        # context["marital_statuses"] = EmployeeProfile.MARITAL_STATUS_CHOICES
        return context

    def form_valid(self, form):
        with transaction.atomic():
            old_employee = CustomUser.objects.select_related("employee_profile").get(
                pk=self.object.pk
            )
            employee = form.save(commit=False)
            employee.updated_by = self.request.user  
            employee.save()

            employee_profile = employee.employee_profile
            employee_profile.basic_salary = form.cleaned_data.get('basic_salary')
            employee_profile.updated_by = self.request.user
            employee_profile.save()

            log_user_activity(
                user=self.request.user,
                action="UPDATE",
                description=f"Updated employee: {employee.get_full_name()}",
                request=self.request,
                additional_data={
                    "employee_code": employee.employee_code,
                    "employee_id": employee.id,
                    "profile_id": employee.employee_profile.id,
                },
            )

            messages.success(
                self.request,
                f"Employee {employee.get_full_name()} updated successfully.",
            )
            return redirect(
                "accounts:employee_detail", employee_id=employee.employee_profile.pk
            )


@login_required
@require_POST
def employee_delete_view(request, employee_id):
    if not UserUtilities.check_user_permission(request.user, "manage_employees"):
        raise PermissionDenied

    employee = get_object_or_404(CustomUser, id=employee_id)

    if employee == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect("accounts:employee_detail", employee_id=employee_id)

    with transaction.atomic():
        employee_name = employee.get_display_name()
        employee_code = employee.employee_code

        employee.soft_delete()

        terminate_user_sessions(employee)

        log_user_activity(
            user=request.user,
            action="DELETE",
            description=f"Deleted employee: {employee_name}",
            request=request,
            additional_data={
                "employee_code": employee_code,
                "employee_id": employee_id,
            },
        )

        messages.success(
            request, f"Employee {employee_name} has been deactivated successfully."
        )

    return redirect("accounts:employee_list")


@login_required
def employee_search_ajax(request):
    if not UserUtilities.check_user_permission(
        request.user, "view_department_employees"
    ):
        return JsonResponse({"error": "Permission denied"}, status=403)

    query = request.GET.get("q", "")
    department_id = request.GET.get("department")
    role_id = request.GET.get("role")
    status = request.GET.get("status")

    employees = search_users(
        query=query,
        department_id=department_id,
        role_id=role_id,
        status=status,
        current_user=request.user,
    )[:20]

    results = []
    for employee in employees:
        results.append(
            {
                "id": employee.id,
                "employee_code": employee.employee_code,
                "name": employee.get_full_name(),
                "email": employee.email,
                "department": employee.department.name if employee.department else "",
                "role": employee.role.display_name if employee.role else "",
                "status": employee.get_status_display(),
                "avatar_url": (
                    employee.get_avatar_url()
                    if hasattr(employee, "get_avatar_url")
                    else None
                ),
            }
        )

    return JsonResponse({"results": results})

@login_required
def employee_export_view(request):
    if not UserUtilities.check_user_permission(request.user, "manage_employees"):
        raise PermissionDenied

    queryset = User.objects.select_related("department", "role", "manager").filter(
        is_active=True
    )

    if not request.user.is_superuser:
        access_mixin = EmployeeAccessMixin()
        accessible_employees = access_mixin.get_accessible_employees(request.user)
        queryset = queryset.filter(
            id__in=accessible_employees.values_list("id", flat=True)
        )

    excel_data = ExcelUtilities.export_users_to_excel(queryset)

    response = HttpResponse(
        excel_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="employees_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )

    log_user_activity(
        user=request.user,
        action="EXPORT",
        description=f"Exported {queryset.count()} employees to Excel",
        request=request,
    )

    return response
class BulkEmployeeUploadView(LoginRequiredMixin, TemplateView):
    template_name = 'ui-form-file-uploads.html'
    form_class = BulkEmployeeUploadForm

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Bulk Employee Upload'
        context['form'] = self.form_class()
        context['upload_template_url'] = reverse('accounts:employee_template_download')
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST, request.FILES)
        
        if form.is_valid():
            file = form.cleaned_data['file']
            
            try:
                file_content = file.read()
                created_count, error_count, errors = ExcelUtilities.import_users_from_excel(
                    file_content, request.user
                )
                
                if created_count > 0:
                    messages.success(
                        request, 
                        f'Successfully created {created_count} employees.'
                    )
                
                if error_count > 0:
                    error_message = f'{error_count} errors occurred during import:'
                    for error in errors[:10]:
                        error_message += f'\n• {error}'
                    if len(errors) > 10:
                        error_message += f'\n... and {len(errors) - 10} more errors'
                    messages.error(request, error_message)
                
                log_user_activity(
                    user=request.user,
                    action='BULK_IMPORT',
                    description=f'Bulk imported employees: {created_count} created, {error_count} errors',
                    request=request,
                    additional_data={
                        'created_count': created_count,
                        'error_count': error_count,
                        'filename': file.name
                    }
                )
                
                if created_count > 0:
                    return redirect('accounts:employee_list')
                
            except Exception as e:
                messages.error(request, f'File processing error: {str(e)}')
        
        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)

@login_required
def employee_template_download(request):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        raise PermissionDenied
    
    template_data = [{
        'employee_code': 'EMP001',
        'first_name': 'John',
        'last_name': 'Doe',
        'middle_name': 'Smith',
        'email': 'john.doe@company.com',
        'phone_number': '+1234567890',
        'date_of_birth': '1990-01-15',
        'gender': 'M',
        'job_title': 'Software Developer',
        'hire_date': '2024-01-01',
        'department_code': 'IT',
        'role_name': 'OTHER_STAFF',
        'manager_employee_code': 'MGR001'
    }]
    
    df = pd.DataFrame(template_data)
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Employee Template', index=False)
        
        worksheet = writer.sheets['Employee Template']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="employee_import_template.xlsx"'
    
    return response

@login_required
@require_POST
def bulk_employee_action(request):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    action = request.POST.get('action')
    employee_ids = request.POST.getlist('employee_ids')
    
    if not action or not employee_ids:
        return JsonResponse({'error': 'Missing action or employee IDs'}, status=400)
    
    employees = CustomUser.objects.filter(id__in=employee_ids, is_active=True)
    
    if not request.user.is_superuser:
        access_mixin = EmployeeAccessMixin()
        accessible_employees = access_mixin.get_accessible_employees(request.user)
        employees = employees.filter(id__in=accessible_employees.values_list('id', flat=True))
    
    success_count = 0
    error_count = 0
    
    with transaction.atomic():
        for employee in employees:
            try:
                if action == 'activate':
                    if employee.status != 'ACTIVE':
                        employee.status = 'ACTIVE'
                        employee.is_active = True
                        employee.save()
                        success_count += 1
                
                elif action == 'deactivate':
                    if employee.status == 'ACTIVE':
                        employee.status = 'INACTIVE'
                        employee.save()
                        success_count += 1
                
                elif action == 'suspend':
                    if employee.status != 'SUSPENDED':
                        employee.status = 'SUSPENDED'
                        employee.save()
                        terminate_user_sessions(employee)
                        success_count += 1
                
                elif action == 'unlock':
                    if employee.is_account_locked():
                        employee.unlock_account()
                        success_count += 1
                
                elif action == 'reset_password':
                    temp_password = generate_secure_password()
                    employee.set_password(temp_password)
                    employee.must_change_password = True
                    employee.password_changed_at = timezone.now()
                    employee.save()
                    
                    send_welcome_email(employee, temp_password, request)
                    success_count += 1
                
                elif action == 'delete':
                    if employee != request.user:
                        employee.soft_delete()
                        terminate_user_sessions(employee)
                        success_count += 1
                    else:
                        error_count += 1
                
            except Exception as e:
                error_count += 1
        
        log_user_activity(
            user=request.user,
            action='BULK_ACTION',
            description=f'Bulk {action} on {success_count} employees',
            request=request,
            additional_data={
                'action': action,
                'success_count': success_count,
                'error_count': error_count,
                'employee_ids': employee_ids
            }
        )
    
    return JsonResponse({
        'success': True,
        'message': f'Action completed: {success_count} successful, {error_count} errors',
        'success_count': success_count,
        'error_count': error_count
    })

@login_required
def bulk_notification_view(request):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        raise PermissionDenied
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        recipient_type = request.POST.get('recipient_type', 'all')
        department_id = request.POST.get('department_id')
        role_id = request.POST.get('role_id')
        
        if not subject or not message:
            messages.error(request, 'Subject and message are required.')
            return redirect('accounts:bulk_notification')
        
        recipients = User.objects.filter(is_active=True, status='ACTIVE')
        
        if recipient_type == 'department' and department_id:
            recipients = recipients.filter(department_id=department_id)
        elif recipient_type == 'role' and role_id:
            recipients = recipients.filter(role_id=role_id)
        
        success, count = SystemUtilities.send_bulk_notification(
            recipients, subject, message, request.user
        )
        
        if success:
            messages.success(request, f'Notification sent to {count} employees successfully.')
        else:
            messages.error(request, 'Failed to send notifications. Please try again.')
        
        return redirect('accounts:bulk_notification')
    
    context = {
        'page_title': 'Send Bulk Notification',
        'departments': Department.active.all(),
        'roles': Role.active.all()
    }
    
    return render(request, 'apps-email.html', context)

@login_required
def employee_import_status(request, task_id):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        if result.ready():
            if result.successful():
                return JsonResponse({
                    'status': 'completed',
                    'result': result.result
                })
            else:
                return JsonResponse({
                    'status': 'failed',
                    'error': str(result.result)
                })
        else:
            return JsonResponse({
                'status': 'processing',
                'progress': result.info.get('progress', 0) if result.info else 0
            })
    except ImportError:
        return JsonResponse({'error': 'Celery not available'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = "accounts/department-list.html"
    context_object_name = "departments"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_departments"
        ) and not UserUtilities.check_user_permission(request.user, "view_departments"):
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
        context["total_departments"] = Department.objects.filter(is_active=True).count()
        context["total_employees"] = sum(dept.employee_count for dept in departments)
        context["departments_with_managers"] = (
            Department.objects.filter(is_active=True).exclude(manager=None).count()
        )

        if context["total_departments"] > 0:
            context["average_employees_per_dept"] = (
                context["total_employees"] / context["total_departments"]
            )
        else:
            context["average_employees_per_dept"] = 0

        return context

class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "accounts/department-detail.html"
    context_object_name = "department"
    pk_url_kwarg = "department_id"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "view_departments"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object
        context["page_title"] = f"Department - {department.name}"
        context["can_edit"] = UserUtilities.check_user_permission(
            self.request.user, "manage_departments"
        )
        context["employees"] = department.get_all_employees()
        context["sub_departments"] = department.sub_departments.filter(is_active=True)
        context["employee_count"] = context["employees"].count()
        context["active_employee_count"] = (
            context["employees"].filter(status="ACTIVE").count()
        )

        context["annual_budget"] = department.budget

        return context


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "accounts/department-create.html"

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
            return redirect("accounts:department_detail", department_id=department.id)

class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "accounts/department-update.html"
    pk_url_kwarg = "department_id"

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
            return redirect("accounts:department_detail", department_id=department.id)


@login_required
@require_POST
def department_delete_view(request, department_id):
    if not UserUtilities.check_user_permission(request.user, "manage_departments"):
        raise PermissionDenied

    department = get_object_or_404(Department, id=department_id)

    if department.employees.filter(is_active=True).exists():
        messages.error(
            request,
            "Cannot delete department with active employees. Please reassign employees first.",
        )
        return redirect("accounts:department_detail", department_id=department_id)

    if department.sub_departments.filter(is_active=True).exists():
        messages.error(request, "Cannot delete department with active sub-departments.")
        return redirect("accounts:department_detail", department_id=department_id)

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
                "department_id": department_id,
            },
        )

        messages.success(
            request,
            f'Department "{department_name}" has been deactivated successfully.',
        )

    return redirect("accounts:department_list")


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


class RoleListView(LoginRequiredMixin, ListView):
    model = Role
    template_name = "accounts/roles-list.html"
    context_object_name = "roles"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_roles"
        ) and not UserUtilities.check_user_permission(request.user, "view_roles"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Role.objects.prefetch_related("permissions").filter(is_active=True)

        search_query = self.request.GET.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(display_name__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset.order_by("level", "display_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Role Management"
        context["can_add_role"] = UserUtilities.check_user_permission(
            self.request.user, "manage_roles"
        )
        context["can_export"] = UserUtilities.check_user_permission(
            self.request.user, "manage_roles"
        )
        context["search_query"] = self.request.GET.get("search", "")

        for role in context["roles"]:
            role.user_count = User.objects.filter(role=role, is_active=True).count()

        return context

class RoleDetailView(LoginRequiredMixin, DetailView):
    model = Role
    template_name = "accounts/roles-detail.html"
    context_object_name = "role"
    pk_url_kwarg = "role_id"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "view_roles"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = self.object
        context["page_title"] = f"Role - {role.display_name}"
        context["can_edit"] = UserUtilities.check_user_permission(
            self.request.user, "manage_roles"
        )
        context["users"] = User.objects.filter(role=role, is_active=True)
        context["user_count"] = context["users"].count()
        context["permissions"] = role.permissions.all()
        return context
class RoleCreateView(LoginRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/roles-create.html"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_roles"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Add New Role"
        context["form_title"] = "Role Information"
        return context

    def form_valid(self, form):
        with transaction.atomic():
            role = form.save(commit=False)
            role.created_by = self.request.user
            role.save()
            form.save_m2m()

            log_user_activity(
                user=self.request.user,
                action="CREATE",
                description=f"Created new role: {role.display_name}",
                request=self.request,
                additional_data={"role_name": role.name, "role_id": role.id},
            )

            messages.success(
                self.request, f'Role "{role.display_name}" created successfully.'
            )
            return redirect("accounts:role_detail", role_id=role.id)


class RoleUpdateView(LoginRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/roles-update.html"
    pk_url_kwarg = "role_id"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_roles"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Edit Role - {self.object.display_name}"
        context["form_title"] = "Update Role Information"
        context["is_update"] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            old_role = Role.objects.get(pk=self.object.pk)
            role = form.save()

            changes = {}
            for field in form.changed_data:
                if field != "permissions":
                    old_value = getattr(old_role, field, None)
                    new_value = getattr(role, field, None)
                    changes[field] = {
                        "old": str(old_value) if old_value else None,
                        "new": str(new_value) if new_value else None,
                    }

            log_user_activity(
                user=self.request.user,
                action="UPDATE",
                description=f"Updated role: {role.display_name}",
                request=self.request,
                additional_data={
                    "role_name": role.name,
                    "role_id": role.id,
                    "changes": changes,
                },
            )

            messages.success(
                self.request, f'Role "{role.display_name}" updated successfully.'
            )
            return redirect("accounts:role_detail", role_id=role.id)


@login_required
@require_POST
def role_delete_view(request, role_id):
    if not UserUtilities.check_user_permission(request.user, "manage_roles"):
        raise PermissionDenied

    role = get_object_or_404(Role, id=role_id)

    if User.objects.filter(role=role, is_active=True).exists():
        messages.error(
            request,
            "Cannot delete role with active users. Please reassign users first.",
        )
        return redirect("accounts:role_detail", role_id=role_id)

    with transaction.atomic():
        role_name = role.display_name
        role.soft_delete()

        log_user_activity(
            user=request.user,
            action="DELETE",
            description=f"Deleted role: {role_name}",
            request=request,
            additional_data={"role_name": role.name, "role_id": role_id},
        )

        messages.success(
            request, f'Role "{role_name}" has been deactivated successfully.'
        )

    return redirect("accounts:role_list")


@login_required
def role_export_view(request):
    if not UserUtilities.check_user_permission(request.user, "manage_roles"):
        raise PermissionDenied

    roles = Role.objects.prefetch_related("permissions").filter(is_active=True)
    excel_data = ExcelUtilities.export_roles_to_excel(roles)

    response = HttpResponse(
        excel_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="roles_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )

    log_user_activity(
        user=request.user,
        action="EXPORT",
        description=f"Exported {roles.count()} roles to Excel",
        request=request,
    )

    return response

class ProfileView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'pages-profile.html'
    context_object_name = 'profile_user'

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        context['page_title'] = 'My Profile'
        context['can_edit_profile'] = True
        context['recent_activities'] = AuditLog.objects.filter(user=user).order_by('-timestamp')[:10]
        context['active_sessions'] = UserSession.objects.filter(user=user, is_active=True)
        context['password_expired'] = user.is_password_expired()
        context['must_change_password'] = user.must_change_password
        context['account_locked'] = user.is_account_locked()
        context['subordinates_count'] = user.get_subordinates().count()
        context['is_manager'] = user.is_manager
        return context

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'ui-form-elements.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Update Profile'
        context['form_title'] = 'Personal Information'
        context['is_profile_update'] = True
        return context

    def form_valid(self, form):
        with transaction.atomic():
            old_user = CustomUser.objects.get(pk=self.object.pk)
            user = form.save()
            
            changes = {}
            for field in form.changed_data:
                old_value = getattr(old_user, field, None)
                new_value = getattr(user, field, None)
                changes[field] = {
                    'old': str(old_value) if old_value else None,
                    'new': str(new_value) if new_value else None
                }
            
            log_user_activity(
                user=self.request.user,
                action='UPDATE',
                description='Updated personal profile information',
                request=self.request,
                additional_data={'changes': changes}
            )
            
            messages.success(self.request, 'Profile updated successfully.')
            return redirect(self.success_url)

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'accounts/auth-reset-password.html'
    success_url = reverse_lazy('accounts:password_change_done')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Change Password'
        context['form_title'] = 'Update Your Password'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        
        log_user_activity(
            user=self.request.user,
            action='PASSWORD_CHANGE',
            description='Password changed successfully',
            request=self.request
        )
        
        messages.success(self.request, 'Password changed successfully.')
        return response

@login_required
def password_change_done_view(request):
    return render(
        request,
        "accounts/auth-signin.html",
        {
            "page_title": "Password Changed",
            "success_message": "Your password has been changed successfully.",
        },
    )

@login_required
def user_sessions_view(request):
    sessions = UserSession.objects.filter(user=request.user).order_by('-login_time')
    
    paginator = Paginator(sessions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_title': 'My Sessions',
        'sessions': page_obj,
        'active_sessions_count': sessions.filter(is_active=True).count(),
        'total_sessions_count': sessions.count()
    }
    
    return render(request, 'ui-tables-datatables.html', context)

@login_required
@require_POST
def terminate_session_view(request, session_id):
    try:
        session = UserSession.objects.get(id=session_id, user=request.user)
        
        if session.session_key_hash == hashlib.sha256(request.session.session_key.encode()).hexdigest():
            messages.error(request, 'Cannot terminate your current session.')
        else:
            session.terminate()
            messages.success(request, 'Session terminated successfully.')
            
            log_user_activity(
                user=request.user,
                action='SESSION_TERMINATE',
                description=f'Terminated session from {session.ip_address}',
                request=request,
                additional_data={'terminated_session_id': str(session_id)}
            )
            
    except UserSession.DoesNotExist:
        messages.error(request, 'Session not found.')
    
    return redirect('accounts:user_sessions')

@login_required
@require_POST
def terminate_all_sessions_view(request):
    current_session_key = request.session.session_key
    terminated_count = 0
    
    sessions = UserSession.objects.filter(user=request.user, is_active=True)
    current_session_hash = hashlib.sha256(current_session_key.encode()).hexdigest()
    
    for session in sessions:
        if session.session_key_hash != current_session_hash:
            session.terminate()
            terminated_count += 1
    
    log_user_activity(
        user=request.user,
        action='SESSION_TERMINATE_ALL',
        description=f'Terminated {terminated_count} sessions',
        request=request,
        additional_data={'terminated_count': terminated_count}
    )
    
    messages.success(request, f'Terminated {terminated_count} other sessions successfully.')
    return redirect('accounts:user_sessions')

@login_required
def account_security_view(request):
    user = request.user
    
    context = {
        'page_title': 'Account Security',
        'password_expired': user.is_password_expired(),
        'must_change_password': user.must_change_password,
        'account_locked': user.is_account_locked(),
        'failed_login_attempts': user.failed_login_attempts,
        'last_password_change': user.password_changed_at,
        'password_expiry_days': SystemConfiguration.get_int_setting('PASSWORD_EXPIRY_DAYS', 90),
        'active_sessions_count': UserSession.objects.filter(user=user, is_active=True).count(),
        'recent_login_attempts': AuditLog.objects.filter(
            user=user,
            action='LOGIN'
        ).order_by('-timestamp')[:10]
    }
    
    return render(request, 'pages-profile.html', context)

@login_required
@require_POST
def unlock_account_view(request, user_id):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        if not request.user.can_manage_user(user):
            return JsonResponse({'error': 'Cannot manage this user'}, status=403)
        
        if user.is_account_locked():
            user.unlock_account()
            
            log_user_activity(
                user=request.user,
                action='ACCOUNT_UNLOCK',
                description=f'Unlocked account for {user.get_display_name()}',
                request=request,
                additional_data={'unlocked_user_id': user_id}
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Account unlocked for {user.get_display_name()}'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Account is not locked'
            })
            
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@login_required
@require_POST
def reset_user_password_view(request, user_id):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        if not request.user.can_manage_user(user):
            return JsonResponse({'error': 'Cannot manage this user'}, status=403)
        
        temp_password = generate_secure_password()
        user.set_password(temp_password)
        user.must_change_password = True
        user.password_changed_at = timezone.now()
        user.save()
        
        if send_welcome_email(user, temp_password, request):
            log_user_activity(
                user=request.user,
                action='PASSWORD_RESET',
                description=f'Reset password for {user.get_display_name()}',
                request=request,
                additional_data={'reset_user_id': user_id}
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Password reset for {user.get_display_name()}. Email sent with new password.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Password reset but failed to send email'
            })
            
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@login_required
def change_user_status_view(request, user_id):
    if not UserUtilities.check_user_permission(request.user, 'manage_employees'):
        raise PermissionDenied
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if not request.user.can_manage_user(user):
        raise PermissionDenied
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status not in dict(CustomUser.STATUS_CHOICES):
            messages.error(request, 'Invalid status selected.')
            return redirect('accounts:employee_detail', employee_id=user_id)
        
        old_status = user.status
        user.status = new_status
        
        if new_status == 'SUSPENDED':
            terminate_user_sessions(user)
        elif new_status == 'TERMINATED':
            user.soft_delete()
            terminate_user_sessions(user)
        elif new_status == 'ACTIVE':
            user.is_active = True
        
        user.save()
        
        log_user_activity(
            user=request.user,
            action='STATUS_CHANGE',
            description=f'Changed status for {user.get_display_name()} from {old_status} to {new_status}',
            request=request,
            additional_data={
                'user_id': user_id,
                'old_status': old_status,
                'new_status': new_status
            }
        )
        
        messages.success(request, f'Status changed to {user.get_status_display()} for {user.get_display_name()}.')
        return redirect('accounts:employee_detail', employee_id=user_id)
    
    context = {
        'page_title': f'Change Status - {user.get_display_name()}',
        'employee': user,
        'status_choices': CustomUser.STATUS_CHOICES
    }
    
    return render(request, 'ui-form-elements.html', context)

@login_required
def user_activity_log_view(request, user_id=None):
    if user_id:
        if not UserUtilities.check_user_permission(request.user, 'view_audit_logs'):
            raise PermissionDenied

        user = get_object_or_404(CustomUser, id=user_id)
        activities = AuditLog.objects.filter(user=user)
        page_title = f'Activity Log - {user.get_display_name()}'
    else:
        user = request.user
        activities = AuditLog.objects.filter(user=user)
        page_title = 'My Activity Log'

    activities = activities.order_by('-timestamp')

    paginator = Paginator(activities, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': page_title,
        'activities': page_obj,
        'target_user': user,
        'total_activities': activities.count()
    }

    return render(request, 'ui-tables-datatables.html', context)

class SystemConfigurationView(LoginRequiredMixin, View):
    template_name = "accounts/system_config.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(request.user, "manage_system_settings"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        action = kwargs.get('action', 'list')
        config_id = kwargs.get('config_id')
        
        if action == 'list':
            return self.list_view(request)
        elif action == 'detail' and config_id:
            return self.detail_view(request, config_id)
        elif action == 'create':
            return self.create_view(request)
        elif action == 'edit' and config_id:
            return self.edit_view(request, config_id)
        elif action == 'statistics':
            return self.statistics_view(request)
        elif action == 'maintenance':
            return self.maintenance_view(request)
        elif action == 'bulk':
            return self.bulk_view(request)
        elif action == 'export':
            return self.export_view(request)
        elif action == 'import':
            return self.import_view(request)
        else:
            return self.list_view(request)
    
    def post(self, request, *args, **kwargs):
        action = kwargs.get('action', 'list')
        config_id = kwargs.get('config_id')
        
        if action == 'create':
            return self.create_post(request)
        elif action == 'edit' and config_id:
            return self.edit_post(request, config_id)
        elif action == 'delete' and config_id:
            return self.delete_post(request, config_id)
        elif action == 'maintenance':
            return self.maintenance_post(request)
        elif action == 'bulk':
            return self.bulk_post(request)
        elif action == 'import':
            return self.import_post(request)
        elif action == 'reset_defaults':
            return self.reset_defaults_post(request)
        else:
            return self.list_view(request)
    
    def list_view(self, request):

        if not SystemConfiguration.objects.exists():
            created_count = SystemConfiguration.initialize_default_settings()
            messages.success(request, f'Initialized {created_count} default system configurations.')
        
        queryset = SystemConfiguration.objects.filter(is_active=True)
        
        setting_type = request.GET.get('type')
        if setting_type:
            queryset = queryset.filter(setting_type=setting_type)
        
        search_query = request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(key__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(value__icontains=search_query)
            )
        
        configurations = queryset.order_by('setting_type', 'key')
        
        grouped_configs = {}
        for config in configurations:
            if config.setting_type not in grouped_configs:
                grouped_configs[config.setting_type] = []
            grouped_configs[config.setting_type].append(config)
        
        context = {
            'page_title': 'System Configuration',
            'configurations': configurations,
            'grouped_configs': grouped_configs,
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'selected_type': setting_type or '',
            'search_query': search_query or '',
            'total_configs': configurations.count(),
            'can_add_setting': True,
            'can_export': True,
            'can_bulk_edit': True,
            'action': 'list'
        }
        
        return render(request, self.template_name, context)
    
    def detail_view(self, request, config_id):
        configuration = get_object_or_404(SystemConfiguration, id=config_id, is_active=True)
        
        related_configs = SystemConfiguration.objects.filter(
            setting_type=configuration.setting_type,
            is_active=True
        ).exclude(id=config_id)[:5]
        
        audit_logs = AuditLog.objects.filter(
            model_name='SystemConfiguration',
            object_id=str(config_id)
        ).order_by('-timestamp')[:10]
        
        context = {
            'page_title': f'Configuration - {configuration.key}',
            'configuration': configuration,
            'related_configs': related_configs,
            'audit_logs': audit_logs,
            'can_edit': True,
            'can_delete': True,
            'action': 'detail'
        }
        
        return render(request, self.template_name, context)
    
    def create_view(self, request):
        form = SystemConfigurationForm()
        
        context = {
            'page_title': 'Add System Configuration',
            'form_title': 'Configuration Details',
            'form': form,
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'action': 'create'
        }
        
        return render(request, self.template_name, context)
    
    def create_post(self, request):
        form = SystemConfigurationForm(request.POST)
        
        if form.is_valid():
            with transaction.atomic():
                config = form.save(commit=False)
                config.updated_by = request.user
                config.save()
                
                log_user_activity(
                    user=request.user,
                    action="CREATE",
                    description=f"Created system configuration: {config.key}",
                    request=request,
                    additional_data={
                        'config_key': config.key,
                        'config_value': config.value,
                        'config_type': config.setting_type,
                    }
                )
                
                messages.success(request, f'Configuration "{config.key}" created successfully.')
                return redirect('accounts:system_config', action='detail', config_id=config.id)
        
        context = {
            'page_title': 'Add System Configuration',
            'form_title': 'Configuration Details',
            'form': form,
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'action': 'create'
        }
        
        return render(request, self.template_name, context)
    
    def edit_view(self, request, config_id):
        configuration = get_object_or_404(SystemConfiguration, id=config_id, is_active=True)
        form = SystemConfigurationForm(instance=configuration)
        
        context = {
            'page_title': f'Edit Configuration - {configuration.key}',
            'form_title': 'Update Configuration',
            'form': form,
            'configuration': configuration,
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'is_update': True,
            'action': 'edit'
        }
        
        return render(request, self.template_name, context)
    
    def edit_post(self, request, config_id):
        configuration = get_object_or_404(SystemConfiguration, id=config_id, is_active=True)
        form = SystemConfigurationForm(request.POST, instance=configuration)
        
        if form.is_valid():
            with transaction.atomic():
                old_value = configuration.value
                config = form.save(commit=False)
                config.updated_by = request.user
                config.save()
                
                log_user_activity(
                    user=request.user,
                    action="UPDATE",
                    description=f"Updated system configuration: {config.key}",
                    request=request,
                    additional_data={
                        'config_key': config.key,
                        'old_value': old_value,
                        'new_value': config.value,
                        'config_type': config.setting_type,
                    }
                )
                
                messages.success(request, f'Configuration "{config.key}" updated successfully.')
                return redirect('accounts:system_config', action='detail', config_id=config.id)
        
        context = {
            'page_title': f'Edit Configuration - {configuration.key}',
            'form_title': 'Update Configuration',
            'form': form,
            'configuration': configuration,
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'is_update': True,
            'action': 'edit'
        }
        
        return render(request, self.template_name, context)
    
    def delete_post(self, request, config_id):
        configuration = get_object_or_404(SystemConfiguration, id=config_id, is_active=True)
        
        with transaction.atomic():
            old_key = configuration.key
            configuration.is_active = False
            configuration.save()
            
            log_user_activity(
                user=request.user,
                action="DELETE",
                description=f"Deleted system configuration: {old_key}",
                request=request,
                additional_data={
                    'config_key': old_key,
                    'config_id': config_id,
                }
            )
            
            messages.success(request, f'Configuration "{old_key}" deleted successfully.')
        
        return redirect('accounts:system_config')
    
    def statistics_view(self, request):
        if not UserUtilities.check_user_permission(request.user, "view_all_reports"):
            raise PermissionDenied
        
        stats = SystemUtilities.get_system_statistics()
        
        config_stats = {
            'total_configs': SystemConfiguration.objects.filter(is_active=True).count(),
            'by_type': {},
            'recently_updated': SystemConfiguration.objects.filter(
                is_active=True,
                updated_at__gte=timezone.now() - timedelta(days=7)
            ).count()
        }
        
        for setting_type, display_name in SystemConfiguration.SETTING_TYPES:
            config_stats['by_type'][display_name] = SystemConfiguration.objects.filter(
                setting_type=setting_type,
                is_active=True
            ).count()
        
        context = {
            'page_title': 'System Statistics',
            'stats': stats,
            'config_stats': config_stats,
            'recent_activities': AuditLog.objects.filter(
                model_name='SystemConfiguration'
            ).order_by('-timestamp')[:20],
            'active_sessions': UserSession.objects.filter(is_active=True).count(),
            'password_expiry_users': SystemUtilities.get_password_expiry_users().count(),
            'action': 'statistics'
        }
        
        return render(request, self.template_name, context)
    
    def maintenance_view(self, request):
        context = {
            'page_title': 'System Maintenance',
            'expired_sessions_count': UserSession.objects.filter(
                is_active=True,
                last_activity__lt=timezone.now() - timedelta(minutes=30)
            ).count(),
            'expired_tokens_count': PasswordResetToken.objects.filter(
                expires_at__lt=timezone.now(),
                is_used=False
            ).count(),
            'old_logs_count': AuditLog.objects.filter(
                timestamp__lt=timezone.now() - timedelta(days=365)
            ).count(),
            'password_expiry_users_count': SystemUtilities.get_password_expiry_users().count(),
            'total_configs': SystemConfiguration.objects.filter(is_active=True).count(),
            'action': 'maintenance'
        }
        
        return render(request, self.template_name, context)
    
    def maintenance_post(self, request):
        action = request.POST.get('action')
        
        if action == 'cleanup_sessions':
            count = UserSession.cleanup_expired_sessions()
            messages.success(request, f"Cleaned up {count} expired sessions.")
        
        elif action == 'cleanup_tokens':
            count = SystemUtilities.cleanup_expired_tokens()
            messages.success(request, f"Cleaned up {count} expired tokens.")
        
        elif action == 'cleanup_logs':
            days = int(request.POST.get('days', 365))
            count = AuditLog.cleanup_old_logs(days)
            messages.success(request, f"Cleaned up {count} old audit logs.")
        
        elif action == 'send_password_notifications':
            count = SystemUtilities.send_password_expiry_notifications()
            messages.success(request, f"Sent password expiry notifications to {count} users.")
        
        elif action == 'test_email':
            if SystemUtilities.test_email_connection():
                messages.success(request, "Email connection test successful.")
            else:
                messages.error(request, "Email connection test failed.")
        
        log_user_activity(
            user=request.user,
            action="SYSTEM_MAINTENANCE",
            description=f"Performed system maintenance action: {action}",
            request=request,
            additional_data={'action': action}
        )
        
        return redirect('accounts:system_config', action='maintenance')
    
    def bulk_view(self, request):
        setting_type = request.GET.get('type')
        configurations = SystemConfiguration.objects.filter(is_active=True)
        
        if setting_type:
            configurations = configurations.filter(setting_type=setting_type)
        
        context = {
            'page_title': 'Bulk Configuration Management',
            'configurations': configurations.order_by('setting_type', 'key'),
            'setting_types': SystemConfiguration.SETTING_TYPES,
            'selected_type': setting_type or '',
            'action': 'bulk'
        }
        
        return render(request, self.template_name, context)
    
    def bulk_post(self, request):
        action = request.POST.get('bulk_action')
        config_ids = request.POST.getlist('config_ids')
        
        if not config_ids:
            messages.error(request, "No configurations selected.")
            return redirect('accounts:system_config', action='bulk')
        
        with transaction.atomic():
            if action == 'delete':
                count = SystemConfiguration.objects.filter(
                    id__in=config_ids,
                    is_active=True
                ).update(is_active=False)
                
                log_user_activity(
                    user=request.user,
                    action="BULK_DELETE",
                    description=f"Bulk deleted {count} system configurations",
                    request=request,
                    additional_data={'config_ids': config_ids}
                )
                
                messages.success(request, f"Deleted {count} configurations.")
            
            elif action == 'update_type':
                new_type = request.POST.get('new_setting_type')
                if new_type:
                    count = SystemConfiguration.objects.filter(
                        id__in=config_ids,
                        is_active=True
                    ).update(setting_type=new_type, updated_by=request.user)
                    
                    log_user_activity(
                        user=request.user,
                        action="BULK_UPDATE",
                        description=f"Bulk updated setting type for {count} configurations",
                        request=request,
                        additional_data={
                            'config_ids': config_ids,
                            'new_type': new_type
                        }
                    )
                    
                    messages.success(request, f"Updated {count} configurations.")
        
        return redirect('accounts:system_config', action='bulk')
    
    def export_view(self, request):
        setting_type = request.GET.get('type')
        configurations = SystemConfiguration.objects.filter(is_active=True)
        
        if setting_type:
            configurations = configurations.filter(setting_type=setting_type)
        
        export_data = []
        for config in configurations:
            export_data.append({
                'key': config.key,
                'value': config.value,
                'setting_type': config.setting_type,
                'description': config.description,
                'is_encrypted': config.is_encrypted
            })
        
        response = JsonResponse({
            'configurations': export_data,
            'export_date': timezone.now().isoformat(),
            'total_count': len(export_data)
        })
        
        response['Content-Disposition'] = f'attachment; filename="system_config_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
        
        log_user_activity(
            user=request.user,
            action="EXPORT",
            description=f"Exported {len(export_data)} system configurations",
            request=request,
            additional_data={'setting_type': setting_type}
        )
        
        return response
    
    def import_view(self, request):
        context = {
            'page_title': 'Import System Configuration',
            'action': 'import'
        }
        
        return render(request, self.template_name, context)
    
    def import_post(self, request):
        if 'config_file' not in request.FILES:
            messages.error(request, "No file selected.")
            return redirect('accounts:system_config', action='import')
        
        try:
            config_file = request.FILES['config_file']
            data = json.loads(config_file.read().decode('utf-8'))
            
            if 'configurations' not in data:
                messages.error(request, "Invalid file format.")
                return redirect('accounts:system_config', action='import')
            
            created_count = 0
            updated_count = 0
            
            with transaction.atomic():
                for config_data in data['configurations']:
                    config, created = SystemConfiguration.objects.update_or_create(
                        key=config_data['key'],
                        defaults={
                            'value': config_data['value'],
                            'setting_type': config_data['setting_type'],
                            'description': config_data.get('description', ''),
                            'is_encrypted': config_data.get('is_encrypted', False),
                            'updated_by': request.user,
                            'is_active': True
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                
                log_user_activity(
                    user=request.user,
                    action="IMPORT",
                    description=f"Imported configurations: {created_count} created, {updated_count} updated",
                    request=request,
                    additional_data={
                        'created_count': created_count,
                        'updated_count': updated_count
                    }
                )
            
            messages.success(
                request,
                f"Import completed: {created_count} created, {updated_count} updated."
            )
            
        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON file.")
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
        
        return redirect('accounts:system_config')
    
    def reset_defaults_post(self, request):
        with transaction.atomic():
            count = SystemConfiguration.initialize_default_settings()
            
            log_user_activity(
                user=request.user,
                action="RESET_DEFAULTS",
                description=f"Reset system configurations to defaults: {count} settings initialized",
                request=request,
                additional_data={'initialized_count': count}
            )
            
            messages.success(request, f"Reset to defaults completed: {count} settings initialized.")
        
        return redirect('accounts:system_config')

@login_required
def audit_log_view(request):
    if not UserUtilities.check_user_permission(request.user, "view_audit_logs"):
        raise PermissionDenied

    logs = AuditLog.objects.select_related("user").all()

    action_filter = request.GET.get("action")
    if action_filter:
        logs = logs.filter(action=action_filter)

    user_filter = request.GET.get("user")
    if user_filter:
        logs = logs.filter(
            Q(user__employee_code__icontains=user_filter)
            | Q(user__first_name__icontains=user_filter)
            | Q(user__last_name__icontains=user_filter)
        )

    date_from = request.GET.get("date_from")
    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            logs = logs.filter(timestamp__date__gte=date_from)
        except ValueError:
            pass

    date_to = request.GET.get("date_to")
    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            logs = logs.filter(timestamp__date__lte=date_to)
        except ValueError:
            pass

    logs = logs.order_by("-timestamp")

    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_title": "Audit Logs",
        "logs": page_obj,
        "action_choices": AuditLog.ACTION_TYPES,
        "selected_action": action_filter,
        "user_filter": user_filter,
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "total_logs": logs.count(),
        "can_export": True,
    }

    return render(request, "ui-tables-datatables.html", context)


@login_required
def audit_log_export_view(request):
    if not UserUtilities.check_user_permission(request.user, "view_audit_logs"):
        raise PermissionDenied

    logs = AuditLog.objects.select_related("user").all()

    action_filter = request.GET.get("action")
    if action_filter:
        logs = logs.filter(action=action_filter)

    user_filter = request.GET.get("user")
    if user_filter:
        logs = logs.filter(
            Q(user__employee_code__icontains=user_filter)
            | Q(user__first_name__icontains=user_filter)
            | Q(user__last_name__icontains=user_filter)
        )

    date_from = request.GET.get("date_from")
    if date_from:
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            logs = logs.filter(timestamp__date__gte=date_from)
        except ValueError:
            pass

    date_to = request.GET.get("date_to")
    if date_to:
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            logs = logs.filter(timestamp__date__lte=date_to)
        except ValueError:
            pass

    excel_data = ExcelUtilities.export_audit_logs_to_excel(logs)

    response = HttpResponse(
        excel_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="audit_logs_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )

    log_user_activity(
        user=request.user,
        action="EXPORT",
        description=f"Exported {logs.count()} audit logs to Excel",
        request=request,
    )

    return response


@login_required
def session_management_view(request):
    if not UserUtilities.check_user_permission(request.user, "manage_system_settings"):
        raise PermissionDenied

    sessions = UserSession.objects.select_related("user").filter(is_active=True)

    user_filter = request.GET.get("user")
    if user_filter:
        sessions = sessions.filter(
            Q(user__employee_code__icontains=user_filter)
            | Q(user__first_name__icontains=user_filter)
            | Q(user__last_name__icontains=user_filter)
        )

    sessions = sessions.order_by("-login_time")

    paginator = Paginator(sessions, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_title": "Active Sessions",
        "sessions": page_obj,
        "user_filter": user_filter,
        "total_sessions": sessions.count(),
        "can_terminate": True,
        "can_export": True,
    }

    return render(request, "ui-tables-datatables.html", context)


@login_required
@require_POST
def terminate_user_session_view(request, session_id):
    if not UserUtilities.check_user_permission(request.user, "manage_system_settings"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        session = UserSession.objects.get(id=session_id, is_active=True)
        session.terminate()

        log_user_activity(
            user=request.user,
            action="SESSION_TERMINATE",
            description=f"Terminated session for {session.user.get_display_name()}",
            request=request,
            additional_data={
                "terminated_session_id": str(session_id),
                "terminated_user": session.user.employee_code,
            },
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"Session terminated for {session.user.get_display_name()}",
            }
        )

    except UserSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)


@login_required
def session_export_view(request):
    if not UserUtilities.check_user_permission(request.user, "manage_system_settings"):
        raise PermissionDenied

    sessions = UserSession.objects.select_related("user").filter(is_active=True)
    excel_data = ExcelUtilities.export_sessions_to_excel(sessions)

    response = HttpResponse(
        excel_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="active_sessions_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    )

    log_user_activity(
        user=request.user,
        action="EXPORT",
        description=f"Exported {sessions.count()} active sessions to Excel",
        request=request,
    )

    return response


@login_required
def system_initialization_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        from .models import initialize_system

        result = initialize_system()

        log_user_activity(
            user=request.user,
            action="SYSTEM_INITIALIZATION",
            description="Initialized system with default roles and settings",
            request=request,
            additional_data=result,
        )

        messages.success(
            request,
            f'System initialized successfully. Created {result["roles_created"]} roles and {result["settings_created"]} settings.',
        )

        return redirect("accounts:system_statistics")

    context = {
        "page_title": "System Initialization",
        "warning_message": "This will create default roles and system settings. Existing data will not be affected.",
    }

    return render(request, "ui-form-elements.html", context)


class APIKeyListView(LoginRequiredMixin, ListView):
    model = APIKey
    template_name = "ui-tables-datatables.html"
    context_object_name = "api_keys"
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_system_settings"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = APIKey.objects.select_related("user").filter(is_active=True)

        user_filter = self.request.GET.get("user")
        if user_filter:
            queryset = queryset.filter(
                Q(user__employee_code__icontains=user_filter)
                | Q(user__first_name__icontains=user_filter)
                | Q(user__last_name__icontains=user_filter)
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "API Key Management"
        context["user_filter"] = self.request.GET.get("user", "")
        context["can_create"] = True
        context["total_keys"] = self.get_queryset().count()
        context["active_keys"] = self.get_queryset().filter(is_active=True).count()
        return context


class APIKeyCreateView(LoginRequiredMixin, TemplateView):
    template_name = "ui-form-elements.html"

    def dispatch(self, request, *args, **kwargs):
        if not UserUtilities.check_user_permission(
            request.user, "manage_system_settings"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create API Key"
        context["form_title"] = "API Key Details"
        context["users"] = User.objects.filter(is_active=True).order_by("employee_code")
        return context

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name")
        user_id = request.POST.get("user_id")
        permissions = request.POST.getlist("permissions")
        expires_days = request.POST.get("expires_days")

        if not name or not user_id:
            messages.error(request, "Name and user are required.")
            return redirect("accounts:api_key_create")

        try:
            user = User.objects.get(id=user_id)
            expires_days = int(expires_days) if expires_days else None

            api_key, raw_key = APIKey.generate_key(
                user=user, name=name, permissions=permissions, expires_days=expires_days
            )

            log_user_activity(
                user=request.user,
                action="CREATE",
                description=f"Created API key: {name} for {user.get_display_name()}",
                request=request,
                additional_data={
                    "api_key_id": str(api_key.id),
                    "api_key_name": name,
                    "target_user": user.employee_code,
                },
            )

            messages.success(request, f'API key "{name}" created successfully.')

            context = self.get_context_data()
            context["created_key"] = {
                "name": name,
                "key": raw_key,
                "user": user.get_display_name(),
                "expires_at": api_key.expires_at,
            }

            return render(request, self.template_name, context)

        except User.DoesNotExist:
            messages.error(request, "Invalid user selected.")
            return redirect("accounts:api_key_create")
        except ValueError:
            messages.error(request, "Invalid expiry days.")
            return redirect("accounts:api_key_create")


@login_required
@require_POST
def api_key_revoke_view(request, key_id):
    if not UserUtilities.check_user_permission(request.user, "manage_system_settings"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        api_key = APIKey.objects.get(id=key_id)
        api_key.is_active = False
        api_key.save()

        log_user_activity(
            user=request.user,
            action="DELETE",
            description=f"Revoked API key: {api_key.name}",
            request=request,
            additional_data={"api_key_id": str(key_id), "api_key_name": api_key.name},
        )

        return JsonResponse(
            {
                "success": True,
                "message": f'API key "{api_key.name}" revoked successfully',
            }
        )

    except APIKey.DoesNotExist:
        return JsonResponse({"error": "API key not found"}, status=404)


@login_required
def advanced_search_view(request):
    if not UserUtilities.check_user_permission(
        request.user, "view_department_employees"
    ):
        raise PermissionDenied

    form = AdvancedUserFilterForm(request.GET)
    employees = User.objects.none()

    if form.is_valid():
        employees = User.objects.select_related("department", "role", "manager").filter(
            is_active=True
        )

        if not request.user.is_superuser:
            access_mixin = EmployeeAccessMixin()
            accessible_employees = access_mixin.get_accessible_employees(request.user)
            employees = employees.filter(
                id__in=accessible_employees.values_list("id", flat=True)
            )

        hire_date_from = form.cleaned_data.get("hire_date_from")
        if hire_date_from:
            employees = employees.filter(hire_date__gte=hire_date_from)

        hire_date_to = form.cleaned_data.get("hire_date_to")
        if hire_date_to:
            employees = employees.filter(hire_date__lte=hire_date_to)

        is_active = form.cleaned_data.get("is_active")
        if is_active == "true":
            employees = employees.filter(is_active=True)
        elif is_active == "false":
            employees = employees.filter(is_active=False)

        is_verified = form.cleaned_data.get("is_verified")
        if is_verified == "true":
            employees = employees.filter(is_verified=True)
        elif is_verified == "false":
            employees = employees.filter(is_verified=False)

        employees = employees.order_by("employee_code")

    paginator = Paginator(employees, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_title": "Advanced Employee Search",
        "form": form,
        "employees": page_obj,
        "total_results": employees.count() if form.is_valid() else 0,
        "can_export": UserUtilities.check_user_permission(
            request.user, "manage_employees"
        ),
    }

    return render(request, "employee/employee-list.html", context)


@login_required
def employee_hierarchy_view(request):
    if not UserUtilities.check_user_permission(
        request.user, "view_department_employees"
    ):
        raise PermissionDenied

    managers = (
        User.objects.filter(is_active=True, subordinates__isnull=False)
        .distinct()
        .select_related("department", "role")
    )

    if not request.user.is_superuser:
        access_mixin = EmployeeAccessMixin()
        accessible_employees = access_mixin.get_accessible_employees(request.user)
        managers = managers.filter(
            id__in=accessible_employees.values_list("id", flat=True)
        )

    hierarchy_data = []
    for manager in managers:
        subordinates = manager.get_subordinates()
        hierarchy_data.append(
            {
                "manager": manager,
                "subordinates": subordinates,
                "subordinate_count": subordinates.count(),
            }
        )

    context = {
        "page_title": "Employee Hierarchy",
        "hierarchy_data": hierarchy_data,
        "total_managers": len(hierarchy_data),
    }

    return render(request, "ui-treeview.html", context)


@login_required
def dashboard_widgets_ajax(request):
    widget_type = request.GET.get("widget")

    if widget_type == "recent_employees":
        if not UserUtilities.check_user_permission(
            request.user, "view_department_employees"
        ):
            return JsonResponse({"error": "Permission denied"}, status=403)

        recent_employees = User.objects.filter(
            is_active=True, created_at__gte=timezone.now() - timedelta(days=30)
        ).order_by("-created_at")[:10]

        data = []
        for emp in recent_employees:
            data.append(
                {
                    "id": emp.id,
                    "name": emp.get_full_name(),
                    "employee_code": emp.employee_code,
                    "department": emp.department.name if emp.department else "",
                    "hire_date": (
                        emp.hire_date.strftime("%Y-%m-%d") if emp.hire_date else ""
                    ),
                    "created_at": emp.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return JsonResponse({"employees": data})

    elif widget_type == "department_stats":
        if not UserUtilities.check_user_permission(request.user, "view_departments"):
            return JsonResponse({"error": "Permission denied"}, status=403)

        departments = (
            Department.objects.filter(is_active=True)
            .annotate(
                employee_count=Count("employees", filter=Q(employees__is_active=True))
            )
            .order_by("-employee_count")[:10]
        )

        data = []
        for dept in departments:
            data.append(
                {
                    "name": dept.name,
                    "code": dept.code,
                    "employee_count": dept.employee_count,
                    "manager": (
                        dept.manager.get_full_name() if dept.manager else "No Manager"
                    ),
                }
            )

        return JsonResponse({"departments": data})

    elif widget_type == "system_alerts":
        if not UserUtilities.check_user_permission(
            request.user, "manage_system_settings"
        ):
            return JsonResponse({"error": "Permission denied"}, status=403)

        alerts = []

        locked_accounts = User.objects.filter(
            is_active=True, account_locked_until__gt=timezone.now()
        ).count()

        if locked_accounts > 0:
            alerts.append(
                {
                    "type": "warning",
                    "message": f"{locked_accounts} accounts are currently locked",
                    "action_url": reverse("accounts:employee_list") + "?status=locked",
                }
            )

        password_expiry_users = SystemUtilities.get_password_expiry_users().count()
        if password_expiry_users > 0:
            alerts.append(
                {
                    "type": "info",
                    "message": f"{password_expiry_users} users have passwords expiring soon",
                    "action_url": reverse("accounts:system_maintenance"),
                }
            )

        inactive_sessions = UserSession.objects.filter(
            is_active=True, last_activity__lt=timezone.now() - timedelta(hours=24)
        ).count()

        if inactive_sessions > 0:
            alerts.append(
                {
                    "type": "info",
                    "message": f"{inactive_sessions} stale sessions detected",
                    "action_url": reverse("accounts:session_management"),
                }
            )

        return JsonResponse({"alerts": alerts})

    return JsonResponse({"error": "Invalid widget type"}, status=400)


@login_required
def quick_stats_ajax(request):
    if not UserUtilities.check_user_permission(
        request.user, "view_department_employees"
    ):
        return JsonResponse({"error": "Permission denied"}, status=403)

    stats = {}

    if request.user.is_superuser or UserUtilities.check_user_permission(
        request.user, "manage_employees"
    ):
        stats["total_employees"] = User.objects.filter(is_active=True).count()
        stats["active_employees"] = User.objects.filter(
            is_active=True, status="ACTIVE"
        ).count()
        stats["new_this_month"] = User.objects.filter(
            is_active=True, created_at__gte=timezone.now().replace(day=1)
        ).count()
    else:
        access_mixin = EmployeeAccessMixin()
        accessible_employees = access_mixin.get_accessible_employees(request.user)
        stats["total_employees"] = accessible_employees.count()
        stats["active_employees"] = accessible_employees.filter(status="ACTIVE").count()
        stats["new_this_month"] = accessible_employees.filter(
            created_at__gte=timezone.now().replace(day=1)
        ).count()

    stats["departments"] = Department.objects.filter(is_active=True).count()
    stats["roles"] = Role.objects.filter(is_active=True).count()

    return JsonResponse(stats)


@login_required
def employee_autocomplete_ajax(request):
    if not UserUtilities.check_user_permission(
        request.user, "view_department_employees"
    ):
        return JsonResponse({"error": "Permission denied"}, status=403)

    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    employees = User.objects.filter(
        Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
        | Q(employee_code__icontains=query),
        is_active=True,
    )

    if not request.user.is_superuser:
        access_mixin = EmployeeAccessMixin()
        accessible_employees = access_mixin.get_accessible_employees(request.user)
        employees = employees.filter(
            id__in=accessible_employees.values_list("id", flat=True)
        )

    employees = employees[:20]

    results = []
    for emp in employees:
        results.append(
            {
                "id": emp.id,
                "text": f"{emp.get_full_name()} ({emp.employee_code})",
                "employee_code": emp.employee_code,
                "department": emp.department.name if emp.department else "",
            }
        )

    return JsonResponse({"results": results})


@login_required
def validate_employee_code_ajax(request):
    if not UserUtilities.check_user_permission(request.user, "manage_employees"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    employee_code = request.GET.get("employee_code", "").strip().upper()
    employee_id = request.GET.get("employee_id")

    if not employee_code:
        return JsonResponse({"valid": False, "message": "Employee code is required"})

    queryset = User.objects.filter(employee_code=employee_code)
    if employee_id:
        queryset = queryset.exclude(id=employee_id)

    if queryset.exists():
        return JsonResponse({"valid": False, "message": "Employee code already exists"})

    return JsonResponse({"valid": True, "message": "Employee code is available"})


@login_required
def validate_email_ajax(request):
    if not UserUtilities.check_user_permission(request.user, "manage_employees"):
        return JsonResponse({"error": "Permission denied"}, status=403)

    email = request.GET.get("email", "").strip().lower()
    employee_id = request.GET.get("employee_id")

    if not email:
        return JsonResponse({"valid": False, "message": "Email is required"})

    queryset = User.objects.filter(email=email)
    if employee_id:
        queryset = queryset.exclude(id=employee_id)

    if queryset.exists():
        return JsonResponse({"valid": False, "message": "Email already exists"})

    return JsonResponse({"valid": True, "message": "Email is available"})


@never_cache
@login_required
def health_check_view(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Permission denied"}, status=403)

    health_data = {
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
        "database": "connected",
        "cache": "available",
        "email": (
            "configured" if SystemUtilities.test_email_connection() else "unavailable"
        ),
        "active_users": User.objects.filter(is_active=True).count(),
        "active_sessions": UserSession.objects.filter(is_active=True).count(),
    }

    return JsonResponse(health_data)
