# attendance/management/commands/fix_all_early_departures.py
from django.core.management.base import BaseCommand
from attendance.models import Attendance
from django.db.models import Q
from datetime import datetime, time


class Command(BaseCommand):
    def handle(self, *args, **options):
        # Get all attendance records that have early departure minutes but aren't marked as EARLY_DEPARTURE
        records_to_fix = Attendance.objects.filter(
            early_departure_minutes__gt=0,  # Has early departure minutes
            status__in=[
                "HALF_DAY",
                "PRESENT",
                "INCOMPLETE",
            ],  # But not marked as EARLY_DEPARTURE
        )

        count = records_to_fix.count()
        self.stdout.write(f"Found {count} records to fix")

        for record in records_to_fix:
            self.stdout.write(
                f"Fixing record for {record.employee.get_full_name()} on {record.date}"
            )
            self.stdout.write(
                f"  Current status: {record.status}, Early departure: {record.early_departure_minutes} mins"
            )

            old_status = record.status
            record.status = "EARLY_DEPARTURE"
            record.save(update_fields=["status"])

            self.stdout.write(f"  Updated status: {old_status} → EARLY_DEPARTURE")

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {count} records"))
