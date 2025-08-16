from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Department, Role, UserSession

try:
    from employees.utils import (
        EmployeeUtils,
        ContractUtils,
        NotificationUtils,
        ReportUtils,
    )
    from employees.models import EmployeeProfile, Contract

    EMPLOYEES_APP_AVAILABLE = True
except ImportError:
    EMPLOYEES_APP_AVAILABLE = False


class UnifiedAnalytics:

    @staticmethod
    def get_complete_dashboard_data():
        data = {
            "user_analytics": UnifiedAnalytics.get_user_analytics(),
            "department_analytics": UnifiedAnalytics.get_department_analytics(),
            "role_analytics": UnifiedAnalytics.get_role_analytics(),
            "session_analytics": UnifiedAnalytics.get_session_analytics(),
        }

        if EMPLOYEES_APP_AVAILABLE:
            try:
                data.update(
                    {
                        "employee_stats": EmployeeUtils.get_employee_summary_stats(),
                        "contract_stats": ContractUtils.get_contract_summary_stats(),
                        "probation_ending": EmployeeProfile.objects.filter(
                            employment_status="PROBATION",
                            probation_end_date__lte=timezone.now().date()
                            + timedelta(days=30),
                            is_active=True,
                        ).count(),
                        "contracts_expiring": ContractUtils.get_expiring_contracts(
                            30
                        ).count(),
                        "recent_employees": EmployeeProfile.objects.filter(
                            is_active=True
                        )
                        .select_related("user", "user__department")
                        .order_by("-created_at")[:5],
                        "salary_analysis": ReportUtils.generate_salary_analysis_report(),
                        "probation_notifications": NotificationUtils.get_probation_notifications(),
                        "contract_notifications": NotificationUtils.get_contract_expiry_notifications(),
                        "birthday_notifications": NotificationUtils.get_birthday_notifications(),
                    }
                )
            except:
                data.update(
                    {
                        "employee_stats": {"total_employees": 0, "active_employees": 0},
                        "contract_stats": {"active_contracts": 0},
                        "probation_ending": 0,
                        "contracts_expiring": 0,
                        "recent_employees": [],
                        "salary_analysis": {"average_salary": 0, "total_payroll": 0},
                        "probation_notifications": [],
                        "contract_notifications": [],
                        "birthday_notifications": [],
                    }
                )
        else:
            data.update(
                {
                    "employee_stats": {"total_employees": 0, "active_employees": 0},
                    "contract_stats": {"active_contracts": 0},
                    "probation_ending": 0,
                    "contracts_expiring": 0,
                    "recent_employees": [],
                    "salary_analysis": {"average_salary": 0, "total_payroll": 0},
                    "probation_notifications": [],
                    "contract_notifications": [],
                    "birthday_notifications": [],
                }
            )

        data.update(
            {
                "total_departments": Department.objects.filter(is_active=True).count(),
                "total_roles": Role.objects.filter(is_active=True).count(),
            }
        )

        return data

    @staticmethod
    def get_user_analytics():
        return {
            "status_distribution": list(
                CustomUser.objects.values("status")
                .annotate(count=Count("id"))
                .order_by("status")
            ),
            "role_distribution": list(
                CustomUser.objects.filter(is_active=True)
                .values("role__display_name")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
            "department_assignments": list(
                CustomUser.objects.filter(is_active=True)
                .values("department__name")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
        }

    @staticmethod
    def get_department_analytics():
        departments = Department.objects.filter(is_active=True)
        employee_distribution = []
        for dept in departments:
            employee_distribution.append(
                {
                    "name": dept.name,
                    "employee_count": dept.get_all_employees().count(),
                }
            )

        return {
            "department_hierarchy": list(
                departments.filter(parent_department__isnull=True).values(
                    "name", "code"
                )
            ),
            "employee_distribution": employee_distribution,
        }

    @staticmethod
    def get_role_analytics():
        roles = Role.objects.filter(is_active=True)
        role_distribution = []

        for role in roles:
            user_count = CustomUser.objects.filter(role=role, is_active=True).count()
            role_distribution.append(
                {
                    "display_name": role.display_name,
                    "user_count": user_count,
                }
            )

        role_distribution.sort(key=lambda x: x["user_count"], reverse=True)

        return {
            "role_distribution": role_distribution,
            "role_levels": list(
                roles.values("level").annotate(count=Count("id")).order_by("level")
            ),
        }

    @staticmethod
    def get_session_analytics():
        return {
            "active_sessions": UserSession.objects.filter(is_active=True).count(),
        }

    @staticmethod
    def get_quick_stats():
        base_stats = {
            "total_users": CustomUser.objects.filter(is_active=True).count(),
            "total_departments": Department.objects.filter(is_active=True).count(),
            "total_roles": Role.objects.filter(is_active=True).count(),
            "active_sessions": UserSession.objects.filter(is_active=True).count(),
        }

        if EMPLOYEES_APP_AVAILABLE:
            try:
                base_stats.update(
                    {
                        "total_employees": EmployeeProfile.objects.filter(
                            is_active=True
                        ).count(),
                        "probation_employees": EmployeeProfile.objects.filter(
                            employment_status="PROBATION", is_active=True
                        ).count(),
                        "active_contracts": Contract.objects.filter(
                            status="ACTIVE", is_active=True
                        ).count(),
                        "expiring_contracts": ContractUtils.get_expiring_contracts(
                            30
                        ).count(),
                    }
                )
            except:
                pass

        return base_stats
