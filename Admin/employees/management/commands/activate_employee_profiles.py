# accounts/management/commands/activate_all_employees.py
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Activates all employee user accounts and sets status to ACTIVE"

    def handle(self, *args, **options):
        with transaction.atomic():
            users = CustomUser.objects.filter(is_active=False)
            inactive_count = users.count()
            users.update(is_active=True)

            status_users = CustomUser.objects.exclude(status="ACTIVE")
            status_count = status_users.count()
            status_users.update(status="ACTIVE")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Activated {inactive_count} inactive users and updated {status_count} user statuses"
                )
            )
