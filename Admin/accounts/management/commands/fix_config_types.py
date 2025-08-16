from django.core.management.base import BaseCommand
from accounts.models import SystemConfiguration


class Command(BaseCommand):
    help = "Fix system configuration types"

    def handle(self, *args, **options):
        # Update attendance-related settings
        attendance_keys = [
            "WORK_START_TIME",
            "WORK_END_TIME",
            "NET_WORKING_HOURS",
            "TOTAL_WORK_DURATION",
            "LUNCH_BREAK_DURATION",
            "MANAGER_REPORTING_TIME",
            "CASHIER_REPORTING_TIME",
            "SALESMAN_REPORTING_TIME",
            "CLEANER_REPORTING_TIME",
            "DRIVER_REPORTING_TIME",
            "ASSISTANT_REPORTING_TIME",
            "STOREKEEPER_REPORTING_TIME",
            "OTHER_STAFF_REPORTING_TIME",
            "OTHER_STAFF_GRACE_PERIOD_MINUTES",
            "OFFICE_WORKER_REPORTING_TIME",
            "LATE_THRESHOLD_MINUTES",
            "EARLY_DEPARTURE_THRESHOLD_MINUTES",
            "OVERTIME_THRESHOLD_TIME",
            "HALF_DAY_THRESHOLD_MINUTES",
            "MIN_LUNCH_DURATION_MINUTES",
            "MAX_LUNCH_DURATION_MINUTES",
            "LUNCH_VIOLATION_LIMIT_PER_MONTH",
            "LUNCH_VIOLATION_PENALTY_DAYS",
            "MINIMUM_WORK_HOURS_FULL_DAY",
            "MINIMUM_WORK_HOURS_HALF_DAY",
        ]

        attendance_count = SystemConfiguration.objects.filter(
            key__in=attendance_keys
        ).update(setting_type="ATTENDANCE")
        self.stdout.write(f"Updated {attendance_count} attendance settings")

        # Update security settings
        security_keys = [
            "MAX_LOGIN_ATTEMPTS",
            "ACCOUNT_LOCKOUT_DURATION",
            "SESSION_TIMEOUT_MINUTES",
            "PASSWORD_EXPIRY_DAYS",
            "REQUIRE_PASSWORD_CHANGE",
            "MIN_PASSWORD_LENGTH",
            "REQUIRE_STRONG_PASSWORD",
        ]

        security_count = SystemConfiguration.objects.filter(
            key__in=security_keys
        ).update(setting_type="SECURITY")
        self.stdout.write(f"Updated {security_count} security settings")

        # Update leave settings
        leave_keys = [
            "ANNUAL_LEAVE_DAYS",
            "MEDICAL_LEAVE_DAYS",
            "TOTAL_LEAVE_DAYS",
            "UNPAID_LEAVE_THRESHOLD_TIME",
            "LEAVE_APPROVAL_REQUIRED",
            "MEDICAL_CERTIFICATE_REQUIRED_DAYS",
            "MIN_LEAVE_NOTICE_DAYS",
        ]

        leave_count = SystemConfiguration.objects.filter(key__in=leave_keys).update(
            setting_type="LEAVE"
        )
        self.stdout.write(f"Updated {leave_count} leave settings")

        # Update device settings
        device_keys = [
            "DEVICE_SYNC_INTERVAL_MINUTES",
            "DEVICE_CONNECTION_TIMEOUT_SECONDS",
            "MAX_DEVICE_RETRY_ATTEMPTS",
            "ATTENDANCE_LOG_RETENTION_DAYS",
            "MONTHLY_SUMMARY_RETENTION_MONTHS",
            "REPORT_RETENTION_DAYS",
            "AUTO_PROCESS_DEVICE_LOGS",
            "AUTO_GENERATE_DAILY_RECORDS",
            "AUTO_GENERATE_MONTHLY_SUMMARIES",
        ]

        device_count = SystemConfiguration.objects.filter(key__in=device_keys).update(
            setting_type="DEVICE"
        )
        self.stdout.write(f"Updated {device_count} device settings")

        # Update notification settings
        notification_keys = [
            "LATE_ARRIVAL_NOTIFICATION",
            "EARLY_DEPARTURE_NOTIFICATION",
            "MISSING_CHECKOUT_NOTIFICATION",
            "OVERTIME_NOTIFICATION",
            "LATE_NOTIFICATION_THRESHOLD_MINUTES",
            "MISSING_CHECKOUT_NOTIFICATION_TIME",
            "OVERTIME_NOTIFICATION_THRESHOLD_MINUTES",
        ]

        notification_count = SystemConfiguration.objects.filter(
            key__in=notification_keys
        ).update(setting_type="NOTIFICATION")
        self.stdout.write(f"Updated {notification_count} notification settings")

        # Update calculation settings
        calculation_keys = [
            "PUNCTUALITY_WEIGHT",
            "ATTENDANCE_WEIGHT",
            "EXCELLENT_ATTENDANCE_THRESHOLD",
            "GOOD_ATTENDANCE_THRESHOLD",
        ]

        calculation_count = SystemConfiguration.objects.filter(
            key__in=calculation_keys
        ).update(setting_type="CALCULATION")
        self.stdout.write(f"Updated {calculation_count} calculation settings")

        # Update validation settings
        validation_keys = [
            "MAX_DAILY_CHECKINS",
            "MIN_BREAK_DURATION_MINUTES",
            "MAX_BREAK_DURATION_MINUTES",
            "ALLOW_FUTURE_ATTENDANCE",
            "ALLOW_WEEKEND_OVERTIME",
            "ATTENDANCE_CORRECTION_APPROVAL_REQUIRED",
            "MAX_CORRECTION_DAYS_BACK",
            "ALLOW_SELF_CORRECTION",
        ]

        validation_count = SystemConfiguration.objects.filter(
            key__in=validation_keys
        ).update(setting_type="VALIDATION")
        self.stdout.write(f"Updated {validation_count} validation settings")

        total_updated = (
            attendance_count
            + security_count
            + leave_count
            + device_count
            + notification_count
            + calculation_count
            + validation_count
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {total_updated} configuration types!"
            )
        )
