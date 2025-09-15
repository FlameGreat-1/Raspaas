from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import (
    CustomUser, 
    Department, 
    Role, 
    UserSession, 
    SystemConfiguration, 
    PasswordResetToken
)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('employee_code', 'username', 'email', 'first_name', 'last_name', 
                   'department', 'role', 'status', 'is_active', 'is_staff')
    list_filter = ('is_active', 'status', 'department', 'role', 'is_staff', 
                  'is_superuser', 'gender', 'hire_date')
    search_fields = ('username', 'employee_code', 'email', 'first_name', 'last_name', 
                    'phone_number')
    ordering = ('employee_code',)
    
    fieldsets = (
        (None, {'fields': ('username', 'employee_code', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'middle_name', 'email', 
                                        'phone_number', 'date_of_birth', 'gender')}),
        (_('Address'), {'fields': ('address_line1', 'address_line2', 'city', 'state', 
                                  'postal_code', 'country')}),
        (_('Emergency Contact'), {'fields': ('emergency_contact_name', 'emergency_contact_phone', 
                                           'emergency_contact_relationship')}),
        (_('Employment details'), {'fields': ('department', 'role', 'job_title', 'manager', 
                                            'hire_date', 'termination_date', 'status')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 
                      'groups', 'user_permissions'),
        }),
        (_('Security'), {'fields': ('failed_login_attempts', 'account_locked_until', 
                                   'must_change_password')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'password_changed_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'employee_code', 'email', 'password1', 'password2'),
        }),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'middle_name', 
                                        'phone_number', 'gender')}),
        (_('Employment details'), {'fields': ('department', 'role', 'job_title', 
                                            'manager', 'status')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified'),
        }),
    )
    
    readonly_fields = ('password_changed_at', 'date_joined', 'last_login')
    actions = ['activate_users', 'deactivate_users', 'unlock_accounts']
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True, status='ACTIVE')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False, status='INACTIVE')
    deactivate_users.short_description = "Deactivate selected users"
    
    def unlock_accounts(self, request, queryset):
        queryset.update(account_locked_until=None, failed_login_attempts=0)
    unlock_accounts.short_description = "Unlock selected accounts"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'manager', 'parent_department', 'location', 'is_active')
    list_filter = ('is_active', 'location')
    search_fields = ('name', 'code', 'description', 'location')
    ordering = ('name',)
    
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description')}),
        (_('Hierarchy'), {'fields': ('parent_department', 'manager')}),
        (_('Details'), {'fields': ('budget', 'location', 'is_active')}),
    )
    
    actions = ['activate_departments', 'deactivate_departments']
    
    def activate_departments(self, request, queryset):
        queryset.update(is_active=True, deleted_at=None)
    activate_departments.short_description = "Activate selected departments"
    
    def deactivate_departments(self, request, queryset):
        queryset.update(is_active=False, deleted_at=timezone.now())
    deactivate_departments.short_description = "Deactivate selected departments"


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'level', 'can_manage_employees', 
                   'can_manage_payroll', 'is_active')
    list_filter = ('is_active', 'can_manage_employees', 'can_view_all_data', 
                  'can_approve_leave', 'can_manage_payroll')
    search_fields = ('name', 'display_name', 'description')
    ordering = ('display_name',)
    
    fieldsets = (
        (None, {'fields': ('name', 'display_name', 'description', 'level')}),
        (_('Permissions'), {
            'fields': ('can_manage_employees', 'can_view_all_data', 'can_approve_leave', 
                      'can_manage_payroll', 'permissions'),
        }),
        (_('Status'), {'fields': ('is_active',)}),
    )
    
    filter_horizontal = ('permissions',)
    
    actions = ['activate_roles', 'deactivate_roles']
    
    def activate_roles(self, request, queryset):
        queryset.update(is_active=True, deleted_at=None)
    activate_roles.short_description = "Activate selected roles"
    
    def deactivate_roles(self, request, queryset):
        queryset.update(is_active=False, deleted_at=timezone.now())
    deactivate_roles.short_description = "Deactivate selected roles"


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'device_type', 'login_time', 
                   'last_activity', 'is_active')
    list_filter = ('is_active', 'device_type', 'login_time')
    search_fields = ('user__username', 'user__employee_code', 'ip_address', 
                    'user_agent', 'location')
    ordering = ('-login_time',)
    
    readonly_fields = ('id', 'user', 'session_key_hash', 'ip_address', 'user_agent', 
                      'login_time', 'last_activity', 'logout_time', 'device_type', 'location')
    
    fieldsets = (
        (None, {'fields': ('id', 'user', 'is_active')}),
        (_('Session info'), {'fields': ('session_key_hash', 'ip_address', 'user_agent', 
                                      'device_type', 'location')}),
        (_('Timing'), {'fields': ('login_time', 'last_activity', 'logout_time')}),
    )
    
    actions = ['terminate_sessions']
    
    def terminate_sessions(self, request, queryset):
        for session in queryset:
            session.terminate()
    terminate_sessions.short_description = "Terminate selected sessions"
    
    def has_add_permission(self, request):
        return False


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'setting_type', 'is_active', 'updated_at')
    list_filter = ('setting_type', 'is_active', 'is_encrypted')
    search_fields = ('key', 'value', 'description')
    ordering = ('key',)
    
    fieldsets = (
        (None, {'fields': ('key', 'value', 'setting_type', 'description')}),
        (_('Status'), {'fields': ('is_active', 'is_encrypted')}),
        (_('Audit'), {'fields': ('updated_by', 'created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['activate_settings', 'deactivate_settings']
    
    def activate_settings(self, request, queryset):
        queryset.update(is_active=True)
    activate_settings.short_description = "Activate selected settings"
    
    def deactivate_settings(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_settings.short_description = "Deactivate selected settings"
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'is_used', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username', 'user__employee_code', 'user__email', 'ip_address')
    ordering = ('-created_at',)
    
    readonly_fields = ('id', 'user', 'token', 'created_at', 'expires_at', 
                      'used_at', 'is_used', 'ip_address')
    
    fieldsets = (
        (None, {'fields': ('id', 'user', 'token')}),
        (_('Status'), {'fields': ('is_used', 'ip_address')}),
        (_('Timing'), {'fields': ('created_at', 'expires_at', 'used_at')}),
    )
    
    actions = ['invalidate_tokens']
    
    def invalidate_tokens(self, request, queryset):
        queryset.update(is_used=True, used_at=timezone.now())
    invalidate_tokens.short_description = "Invalidate selected tokens"
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = "Expired"
    
    def has_add_permission(self, request):
        return False
