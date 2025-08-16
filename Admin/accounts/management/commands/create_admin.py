from django.core.management.base import BaseCommand
from accounts.models import CustomUser, Department, Role


class Command(BaseCommand):
    help = "Create admin superuser with all required fields"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, default="Softverse")
        parser.add_argument("--email", type=str, default="softverse.com@gmail.com")
        parser.add_argument("--password", type=str, default="admin123")
        parser.add_argument("--first_name", type=str, default="Flame")
        parser.add_argument("--last_name", type=str, default="Great")

    def handle(self, *args, **options):
        department, created = Department.objects.get_or_create(
            name="Administration",
            defaults={"code": "ADM", "description": "System Administration"},
        )

        role, created = Role.objects.get_or_create(
            name="ADMIN", defaults={"display_name": "System Administrator"}
        )

        if CustomUser.objects.filter(username=options["username"]).exists():
            self.stdout.write(
                self.style.WARNING(f'User {options["username"]} already exists!')
            )
            return

        admin = CustomUser.objects.create_superuser(
            username=options["username"],
            email=options["email"],
            password=options["password"],
            first_name=options["first_name"],
            last_name=options["last_name"],
            employee_code="ADM001",
            department=department,
            role=role,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Created superuser: {admin.username} with employee code: {admin.employee_code}"
            )
        )
