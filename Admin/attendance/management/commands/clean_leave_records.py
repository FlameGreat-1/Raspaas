# In attendance/management/commands/clean_leave_records.py
from django.core.management.base import BaseCommand
from attendance.models import Attendance
from datetime import timedelta

class Command(BaseCommand):
    help = "Cleans up check-in/check-out times for leave records"

    def handle(self, *args, **options):
        # Get all leave records
        leave_records = Attendance.objects.filter(status="LEAVE")
        count = leave_records.count()
        self.stdout.write(f"Found {count} leave records to update")

        # Update each record
        for record in leave_records:
            # Clear all check-in/check-out times
            record.check_in_1 = None
            record.check_out_1 = None
            record.check_in_2 = None
            record.check_out_2 = None
            record.check_in_3 = None
            record.check_out_3 = None
            record.check_in_4 = None
            record.check_out_4 = None
            record.check_in_5 = None
            record.check_out_5 = None
            record.check_in_6 = None
            record.check_out_6 = None

            # Clear first in and last out times
            record.first_in_time = None
            record.last_out_time = None

            # Ensure time calculations are zero
            record.total_time = timedelta(0)
            record.break_time = timedelta(0)
            record.work_time = timedelta(0)
            record.overtime = timedelta(0)
            record.undertime = timedelta(0)

            # Save without triggering full recalculation
            record.save(
                update_fields=[
                    "check_in_1",
                    "check_out_1",
                    "check_in_2",
                    "check_out_2",
                    "check_in_3",
                    "check_out_3",
                    "check_in_4",
                    "check_out_4",
                    "check_in_5",
                    "check_out_5",
                    "check_in_6",
                    "check_out_6",
                    "first_in_time",
                    "last_out_time",
                    "total_time",
                    "break_time",
                    "work_time",
                    "overtime",
                    "undertime",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {count} leave records")
        )
