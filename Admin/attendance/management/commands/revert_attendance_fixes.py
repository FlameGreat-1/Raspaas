# attendance/management/commands/revert_attendance_fixes.py
from django.core.management.base import BaseCommand
from attendance.models import Attendance
from datetime import timedelta


class Command(BaseCommand):
    def handle(self, *args, **options):
        # Find all EARLY_DEPARTURE records with insufficient work time
        min_work_hours = 9.75  # Get this from your system configuration
        min_work_duration = timedelta(hours=min_work_hours)

        records_to_fix = Attendance.objects.filter(
            status="EARLY_DEPARTURE", work_time__lt=min_work_duration
        )

        count = records_to_fix.count()
        self.stdout.write(
            f"Found {count} records to revert from EARLY_DEPARTURE to HALF_DAY"
        )

        for record in records_to_fix:
            self.stdout.write(
                f"Fixing record for {record.employee.get_full_name()} on {record.date}"
            )
            self.stdout.write(
                f"  Current status: {record.status}, Work time: {record.work_time}, Required: {min_work_duration}"
            )

            record.status = "HALF_DAY"
            record.save(update_fields=["status"])

            self.stdout.write(f"  Updated status: EARLY_DEPARTURE → HALF_DAY")

        self.stdout.write(self.style.SUCCESS(f"Successfully reverted {count} records"))
