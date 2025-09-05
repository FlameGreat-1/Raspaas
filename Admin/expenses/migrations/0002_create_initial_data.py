from django.db import migrations


def create_default_categories_and_types(apps, schema_editor):
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    ExpenseType = apps.get_model("expenses", "ExpenseType")

    # Create Employee category
    employee_cat = ExpenseCategory.objects.create(
        name="Employee Expenses",
        code="EMPLOYEE",
        is_employee_expense=True,
        is_operational_expense=False,
    )

    # Create Operational category
    operational_cat = ExpenseCategory.objects.create(
        name="Operational Expenses",
        code="OPERATIONAL",
        is_operational_expense=True,
        is_employee_expense=False,
    )

    # Create Employee expense types
    employee_types = [
        ("MEDICAL", "Medical Expenses"),
        ("EDUCATION", "Education Support"),
        ("SALARY_ADVANCE", "Salary Advance"),
        ("EMPLOYEE_LOAN", "Employee Loan"),
        ("PURCHASE_RETURN", "Purchase Return"),
        ("RELOCATION", "Relocation Expenses"),
        ("ENTERTAINMENT", "Entertainment Expenses"),
    ]

    for code, name in employee_types:
        ExpenseType.objects.create(
            category=employee_cat,
            name=name,
            code=code,
            requires_receipt=True,
            is_reimbursable=True,
            is_purchase_return=(code == "PURCHASE_RETURN"),
        )

    # Create Operational expense types
    operational_types = [
        ("STATIONERY", "Stationery and Materials"),
        ("EQUIPMENT", "Equipment Purchases/Rentals"),
        ("TRAINING", "Training and Development"),
        ("TRAVEL", "Travel Expenses"),
        ("FUEL", "Fuel and Transportation"),
        ("SOFTWARE", "Software and Subscriptions"),
        ("MAINTENANCE", "Maintenance and Repairs"),
    ]

    for code, name in operational_types:
        ExpenseType.objects.create(
            category=operational_cat,
            name=name,
            code=code,
            requires_receipt=True,
            is_reimbursable=True,
        )


def reverse_migration(apps, schema_editor):
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")
    ExpenseCategory.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("expenses", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_categories_and_types, reverse_migration),
    ]
