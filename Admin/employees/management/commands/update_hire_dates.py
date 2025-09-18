# accounts/management/commands/update_hire_dates.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from accounts.models import CustomUser
from datetime import timedelta


class Command(BaseCommand):
    help = "Updates hire dates for all employees to be 2 years ago"

    def handle(self, *args, **options):
        two_years_ago = timezone.now().date() - timedelta(days=730)

        with transaction.atomic():
            updated = CustomUser.objects.filter(is_active=True).update(
                hire_date=two_years_ago
            )
            self.stdout.write(
                self.style.SUCCESS(f"Updated hire dates for {updated} employees")
            )
