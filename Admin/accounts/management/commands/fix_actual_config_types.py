from django.core.management.base import BaseCommand
from accounts.models import SystemConfiguration


class Command(BaseCommand):
    help = "Fix system configuration types based on actual keys"

    def handle(self, *args, **options):
        # Update security settings
        security_keys = [
            "ACCOUNT_LOCKOUT_DURATION",
            "MAX_LOGIN_ATTEMPTS",
            "PASSWORD_EXPIRY_DAYS",
            "PASSWORD_EXPIRY_WARNING_DAYS",
            "SECURITY_ALERT_THRESHOLD",
            "SESSION_TIMEOUT",
        ]
        security_count = SystemConfiguration.objects.filter(
            key__in=security_keys
        ).update(setting_type="SECURITY")
        self.stdout.write(f"Updated {security_count} security settings")

        # Update payroll settings
        payroll_keys = ["OVERTIME_RATE", "LATE_PENALTY_RATE"]
        payroll_count = SystemConfiguration.objects.filter(key__in=payroll_keys).update(
            setting_type="PAYROLL"
        )
        self.stdout.write(f"Updated {payroll_count} payroll settings")

        # Update attendance settings
        attendance_keys = ["WORKING_DAYS_PER_WEEK", "WORKING_HOURS_PER_DAY"]
        attendance_count = SystemConfiguration.objects.filter(
            key__in=attendance_keys
        ).update(setting_type="ATTENDANCE")
        self.stdout.write(f"Updated {attendance_count} attendance settings")

        # Update notification settings
        notification_keys = ["EMAIL_NOTIFICATIONS_ENABLED"]
        notification_count = SystemConfiguration.objects.filter(
            key__in=notification_keys
        ).update(setting_type="NOTIFICATION")
        self.stdout.write(f"Updated {notification_count} notification settings")

        # Update validation settings
        validation_keys = [
            "MAX_EMPLOYEE_AGE",
            "MIN_EMPLOYEE_AGE",
            "MAX_UPLOAD_SIZE_MB",
            "ALLOWED_FILE_TYPES",
        ]
        validation_count = SystemConfiguration.objects.filter(
            key__in=validation_keys
        ).update(setting_type="VALIDATION")
        self.stdout.write(f"Updated {validation_count} validation settings")

        # Keep some as system settings (company info, maintenance, etc.)
        system_keys = [
            "COMPANY_NAME",
            "COMPANY_EMAIL",
            "COMPANY_PHONE",
            "COMPANY_ADDRESS",
            "SYSTEM_MAINTENANCE_MODE",
            "AUDIT_LOG_RETENTION_DAYS",
            "MAX_CONCURRENT_SESSIONS",
        ]
        system_count = SystemConfiguration.objects.filter(key__in=system_keys).update(
            setting_type="SYSTEM"
        )
        self.stdout.write(f"Updated {system_count} system settings")

        total_updated = (
            security_count
            + payroll_count
            + attendance_count
            + notification_count
            + validation_count
            + system_count
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {total_updated} configuration types!"
            )
        )
