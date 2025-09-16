from django.core.management.base import BaseCommand
from attendance.models import MonthlyAttendanceSummary, CustomUser
from django.utils import timezone


class Command(BaseCommand):
    help = "Regenerates monthly attendance summaries for specified months"

    def add_arguments(self, parser):
        parser.add_argument("year", type=int, help="Year (e.g., 2025)")
        parser.add_argument("months", nargs="+", type=int, help="List of months (1-12)")
        parser.add_argument(
            "--employee", type=str, help="Optional: Specific employee code"
        )
        parser.add_argument("--department", type=str, help="Optional: Department name")

    def handle(self, *args, **options):
        start_time = timezone.now()
        year = options["year"]
        months = options["months"]
        employee_code = options.get("employee")
        department_name = options.get("department")

        # Filter employees based on arguments
        employees_query = CustomUser.objects.filter(is_active=True)

        if employee_code:
            employees_query = employees_query.filter(employee_code=employee_code)
            self.stdout.write(f"Filtering for employee: {employee_code}")

        if department_name:
            employees_query = employees_query.filter(department__name=department_name)
            self.stdout.write(f"Filtering for department: {department_name}")

        employees = list(employees_query)
        total_employees = len(employees)

        if total_employees == 0:
            self.stdout.write(self.style.WARNING("No matching employees found"))
            return

        self.stdout.write(f"Found {total_employees} employees to process")

        # Validate months
        valid_months = [m for m in months if 1 <= m <= 12]
        invalid_months = [m for m in months if m not in valid_months]

        if invalid_months:
            self.stdout.write(
                self.style.WARNING(
                    f'Ignoring invalid months: {", ".join(map(str, invalid_months))}'
                )
            )

        if not valid_months:
            self.stdout.write(self.style.ERROR("No valid months specified"))
            return

        # Process summaries
        total_summaries = 0
        processed_employees = 0

        for employee in employees:
            employee_summaries = 0
            for month in valid_months:
                try:
                    summary = MonthlyAttendanceSummary.generate_for_employee_month(
                        employee, year, month
                    )
                    employee_summaries += 1
                    total_summaries += 1
                    self.stdout.write(
                        f"Generated summary for {employee.get_full_name()} ({employee.employee_code}): "
                        f"{year}-{month:02d} - {summary.formatted_total_work_time} hrs"
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error generating summary for {employee.get_full_name()} ({employee.employee_code}): "
                            f"{year}-{month:02d} - {str(e)}"
                        )
                    )

            processed_employees += 1
            if processed_employees % 5 == 0 or processed_employees == total_employees:
                self.stdout.write(
                    f"Progress: {processed_employees}/{total_employees} employees processed "
                    f"({(processed_employees/total_employees*100):.1f}%)"
                )

        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully regenerated {total_summaries} summaries for {processed_employees} employees "
                f"in {duration:.2f} seconds"
            )
        )
