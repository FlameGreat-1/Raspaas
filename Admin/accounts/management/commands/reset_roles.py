from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Role, CustomUser


class Command(BaseCommand):
    help = "Reset roles to match the Role model ROLE_TYPES"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to reset all roles",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "This will DELETE all existing roles and create new ones.\n"
                    "Users will be temporarily without roles.\n"
                    "Run with --confirm to proceed."
                )
            )
            return

        with transaction.atomic():
            # Store users without roles temporarily
            self.stdout.write("Backing up user role assignments...")
            user_role_backup = {}
            for user in CustomUser.objects.all():
                if user.role:
                    user_role_backup[user.id] = user.role.name

            # Delete existing roles
            self.stdout.write("Deleting existing roles...")
            Role.objects.all().delete()

            # Create new roles based on ROLE_TYPES
            self.stdout.write("Creating new roles...")
            role_mapping = {}

            for role_name, display_name in Role.ROLE_TYPES:
                role = Role.objects.create(
                    name=role_name,
                    display_name=display_name,
                    description=f"{display_name} role with appropriate permissions",
                    level=self.get_role_level(role_name),
                    can_manage_employees=role_name in ["SUPER_ADMIN", "MANAGER"],
                    can_view_all_data=role_name in ["SUPER_ADMIN", "MANAGER"],
                    can_approve_leave=role_name in ["SUPER_ADMIN", "MANAGER"],
                    can_manage_payroll=role_name == "SUPER_ADMIN",
                    is_active=True,
                )
                role_mapping[role_name] = role
                self.stdout.write(f"Created role: {display_name}")

            # Restore user roles (map old roles to new ones)
            self.stdout.write("Restoring user role assignments...")
            role_name_mapping = {
                "ADMIN": "SUPER_ADMIN",
                "HR_ADMIN": "SUPER_ADMIN",
                "HR_MANAGER": "MANAGER",
                "DEPARTMENT_MANAGER": "MANAGER",
                "PAYROLL_MANAGER": "MANAGER",
                "AUDITOR": "OTHER_STAFF",
                "EMPLOYEE": "OTHER_STAFF",
            }

            for user_id, old_role_name in user_role_backup.items():
                try:
                    user = CustomUser.objects.get(id=user_id)
                    new_role_name = role_name_mapping.get(old_role_name, "OTHER_STAFF")
                    user.role = role_mapping[new_role_name]
                    user.save()
                    self.stdout.write(
                        f"Updated {user.employee_code}: {old_role_name} -> {new_role_name}"
                    )
                except CustomUser.DoesNotExist:
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reset roles! Created {len(Role.ROLE_TYPES)} roles."
            )
        )

    def get_role_level(self, role_name):
        level_mapping = {
            "SUPER_ADMIN": 10,
            "MANAGER": 8,
            "CASHIER": 5,
            "SALESMAN": 4,
            "ASSISTANT": 4,
            "STOREKEEPER": 5,
            "OFFICE_WORKER": 4,
            "OTHER_STAFF": 3,
            "DRIVER": 3,
            "CLEANER": 2,
        }
        return level_mapping.get(role_name, 3)
