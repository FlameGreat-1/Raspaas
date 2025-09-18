# File: employees/management/commands/delete_all_contracts.py

from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import Contract


class Command(BaseCommand):
    help = "Deletes all employee contracts in the system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to delete all contracts",
        )

    def handle(self, *args, **options):
        if not options.get("confirm"):
            self.stdout.write(
                self.style.WARNING(
                    "This will delete ALL contracts in the system. "
                    "Run with --confirm to proceed."
                )
            )
            return

        try:
            with transaction.atomic():
                count = Contract.objects.all().count()
                Contract.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully deleted {count} contracts")
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error deleting contracts: {str(e)}"))
