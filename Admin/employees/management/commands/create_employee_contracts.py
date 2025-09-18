from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from accounts.models import CustomUser, Department
from employees.models import Contract
from decimal import Decimal
import random
from datetime import timedelta


class Command(BaseCommand):
    help = (
        "Creates active permanent contracts for all employees without active contracts"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation of contracts even for employees who already have active contracts",
        )
        parser.add_argument(
            "--department",
            type=str,
            help="Create contracts only for employees in a specific department (by name)",
        )

    def handle(self, *args, **options):
        force_creation = options.get("force", False)
        department_filter = options.get("department")

        # Get all active employees
        employees = CustomUser.active.filter(is_active=True, status="ACTIVE")

        if department_filter:
            try:
                department = Department.objects.get(name__iexact=department_filter)
                employees = employees.filter(department=department)
                self.stdout.write(
                    self.style.SUCCESS(f"Filtering by department: {department.name}")
                )
            except Department.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Department '{department_filter}' not found")
                )
                return

        total_employees = employees.count()
        self.stdout.write(
            self.style.SUCCESS(f"Found {total_employees} active employees")
        )

        # Standard terms and conditions template
        terms_template = """
1. EMPLOYMENT TERMS
   The Employee agrees to perform duties as assigned by the Company.
   
2. COMPENSATION
   The Employee will be paid the basic salary as specified in this contract.
   
3. WORKING HOURS
   Standard working hours are as specified in this contract.
   
4. LEAVE ENTITLEMENT
   The Employee is entitled to annual leave as per company policy.
   
5. TERMINATION
   Either party may terminate this agreement with notice as specified.
   
6. CONFIDENTIALITY
   The Employee agrees to maintain confidentiality of company information.
        """

        # Standard benefits template
        benefits_template = """
- Health insurance coverage
- Annual leave entitlement
- Sick leave entitlement
- Performance bonus eligibility
- Professional development opportunities
        """

        # Track statistics
        contracts_created = 0
        contracts_skipped = 0
        errors = []

        # Process each employee
        for employee in employees:
            self.stdout.write(
                f"Processing employee: {employee.employee_code} - {employee.get_full_name()}"
            )

            try:
                # Check if employee already has an active contract
                existing_contract = Contract.objects.filter(
                    employee=employee, status="ACTIVE", is_active=True
                ).first()

                if existing_contract and not force_creation:
                    self.stdout.write(
                        f"  - Skipping: Employee already has active contract #{existing_contract.contract_number}"
                    )
                    contracts_skipped += 1
                    continue

                # Get employee department or assign to default
                department = employee.department
                if not department:
                    department = Department.objects.filter(is_active=True).first()
                    if not department:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  - Error: No active departments found for {employee.employee_code}"
                            )
                        )
                        errors.append(f"No department for {employee.employee_code}")
                        continue
                    self.stdout.write(
                        f"  - Warning: No department assigned, using default: {department.name}"
                    )

                # Get reporting manager (someone other than the employee)
                potential_managers = CustomUser.active.filter(
                    ~Q(id=employee.id), department=department, is_active=True
                )

                reporting_manager = None
                if potential_managers.exists():
                    reporting_manager = potential_managers.first()

                # Determine job title
                job_title = employee.job_title or f"{department.name} Staff"

                # Set basic salary (either from profile or default)
                try:
                    if (
                        hasattr(employee, "employee_profile")
                        and employee.employee_profile.basic_salary
                    ):
                        basic_salary = employee.employee_profile.basic_salary
                    else:
                        # Generate a reasonable salary based on role if available
                        if employee.role:
                            role_name = employee.role.name
                            if role_name in ["MANAGER", "DIRECTOR"]:
                                basic_salary = Decimal(random.randint(80000, 120000))
                            elif role_name in ["SENIOR", "LEAD"]:
                                basic_salary = Decimal(random.randint(60000, 90000))
                            else:
                                basic_salary = Decimal(random.randint(30000, 60000))
                        else:
                            basic_salary = Decimal(random.randint(30000, 60000))

                        self.stdout.write(
                            f"  - Warning: No basic salary found, using generated value: {basic_salary}"
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  - Error getting salary: {str(e)}")
                    )
                    basic_salary = Decimal("50000.00")  # Default fallback

                # Set contract dates
                # Start date: 1 year ago from today
                start_date = timezone.now().date() - timedelta(days=365)

                # For permanent contracts, end_date remains None
                end_date = None

                with transaction.atomic():
                    # Create the contract
                    contract = Contract(
                        employee=employee,
                        contract_type="PERMANENT",
                        status="ACTIVE",
                        start_date=start_date,
                        end_date=end_date,
                        signed_date=start_date,  # Set signed date to start date
                        job_title=job_title,
                        department=department,
                        reporting_manager=reporting_manager,
                        basic_salary=basic_salary,
                        terms_and_conditions=terms_template,
                        benefits=benefits_template,
                        working_hours=Decimal("9.75"),  # Default working hours
                        probation_period_months=0,  # No probation for permanent
                        notice_period_days=30,  # Standard notice period
                        is_active=True,
                    )

                    # Save without validation to avoid potential issues with overlapping contracts
                    if force_creation:
                        # If forcing creation, bypass validation
                        contract.save(force_insert=True)
                    else:
                        # Normal save with validation
                        contract.save()

                    contracts_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  - Created contract #{contract.contract_number} for {employee.employee_code}"
                        )
                    )

                    # If employee has a profile, update employment status
                    if hasattr(employee, "employee_profile"):
                        try:
                            profile = employee.employee_profile
                            profile.employment_status = "CONFIRMED"
                            profile.save(update_fields=["employment_status"])
                            self.stdout.write(
                                f"  - Updated employee profile status to CONFIRMED"
                            )
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  - Could not update profile: {str(e)}"
                                )
                            )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  - Error creating contract: {str(e)}")
                )
                errors.append(f"Error for {employee.employee_code}: {str(e)}")

        # Print summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Contract Creation Summary:"))
        self.stdout.write(f"Total employees processed: {total_employees}")
        self.stdout.write(self.style.SUCCESS(f"Contracts created: {contracts_created}"))
        self.stdout.write(f"Employees skipped: {contracts_skipped}")
        self.stdout.write(f"Errors encountered: {len(errors)}")

        if errors:
            self.stdout.write("\nErrors:")
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))

        self.stdout.write("=" * 50)
