import pandas as pd
import numpy as np
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from accounts.models import Department, Role, CustomUser, SystemConfiguration
from employees.models import EmployeeProfile
from datetime import datetime
import uuid
import logging
from datetime import timedelta

from threading import local

_thread_locals = local()

logger = logging.getLogger(__name__)


def read_excel_file(file_obj):
    try:
        excel_file = pd.ExcelFile(file_obj, engine="openpyxl")
        sheet_names = excel_file.sheet_names

        for sheet_name in sheet_names:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)

                if df.empty:
                    continue

                first_column = df.iloc[:, 0].astype(str).str.lower().str.strip()
                common_fields = [
                    "first name",
                    "first_name",
                    "firstname",
                    "name",
                    "last name",
                    "last_name",
                    "lastname",
                    "email",
                    "phone",
                    "phone_number",
                ]

                matches = 0
                for field in common_fields:
                    for val in first_column:
                        if isinstance(val, str) and field in val:
                            matches += 1
                            break

                if matches >= 2:
                    if df.shape[1] > 2:
                        new_df = pd.DataFrame()

                        for i in range(1, df.shape[1]):
                            employee_data = {}
                            employee_data["first_name"] = df.columns[i]

                            for j in range(df.shape[0]):
                                field_name = (
                                    str(df.iloc[j, 0]).lower().strip().replace(" ", "_")
                                )
                                field_value = df.iloc[j, i]
                                employee_data[field_name] = field_value

                            new_df = pd.concat(
                                [new_df, pd.DataFrame([employee_data])],
                                ignore_index=True,
                            )

                        df = new_df
                    else:
                        single_employee = {}
                        for i, row in df.iterrows():
                            field_name = (
                                str(row.iloc[0]).lower().strip().replace(" ", "_")
                            )
                            field_value = row.iloc[1] if len(row) > 1 else None
                            single_employee[field_name] = field_value
                        df = pd.DataFrame([single_employee])

                df.columns = [
                    str(col).lower().strip().replace(" ", "_") for col in df.columns
                ]

                if "first_name" not in df.columns:
                    for col in df.columns:
                        col_lower = col.lower()
                        if "first" in col_lower or (
                            "name" in col_lower
                            and "last" not in col_lower
                            and "middle" not in col_lower
                        ):
                            df["first_name"] = df[col]
                            break

                df = df.replace({np.nan: None})

                if not df.empty:
                    return df

            except Exception as e:
                continue

        raise ValueError("Could not find valid employee data in any sheet")

    except Exception as e:
        logger.error(f"Error reading Excel file: {str(e)}")
        raise ValueError(f"Failed to read Excel file: {str(e)}")


def validate_excel_structure(df):
    required_fields = ["first_name"]

    all_expected_fields = [
        "first_name",
        "last_name",
        "middle_name",
        "email",
        "phone_number",
        "date_of_birth",
        "gender",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "postal_code",
        "country",
        "emergency_contact_name",
        "emergency_contact_phone",
        "emergency_contact_relationship",
        "department_code",
        "role_name",
        "job_title",
        "hire_date",
        "manager_code",
        "status",
        "employment_status",
        "grade_level",
        "basic_salary",
        "probation_end_date",
        "confirmation_date",
        "bank_name",
        "bank_account_number",
        "bank_branch",
        "tax_identification_number",
        "marital_status",
        "spouse_name",
        "number_of_children",
        "work_location",
    ]
    
    field_name_variants = {
        "first_name": ["first_name", "firstname", "first", "fname", "given_name", "name", "employee_name", "full_name", "first name"],
        "last_name": ["last_name", "lastname", "last", "lname", "surname", "family_name", "last name"],
        "middle_name": ["middle_name", "middlename", "middle", "mname", "middle name"],
        "email": ["email", "email_address", "emailaddress", "mail", "e_mail", "e-mail"],
        "phone_number": ["phone_number", "phone", "mobile", "cell", "contact", "telephone", "tel", "mobile_no", "phone number"],
        "date_of_birth": ["date_of_birth", "dob", "birth_date", "birthdate", "birth", "date of birth"],
        "gender": ["gender", "sex"],
        "address_line1": ["address_line1", "address1", "address", "street_address", "primary_address", "street", "permenant_address", "address line1"],
        "address_line2": ["address_line2", "address2", "secondary_address", "apt", "suite", "residence_address", "address line2"],
        "city": ["city", "town", "municipality"],
        "state": ["state", "province", "region"],
        "postal_code": ["postal_code", "zip", "zipcode", "zip_code", "postcode", "post_code", "postal code"],
        "country": ["country", "nation"],
        "emergency_contact_name": ["emergency_contact_name", "emergency_name", "emergency_contact", "ice_name", "emergency contact name"],
        "emergency_contact_phone": ["emergency_contact_phone", "emergency_phone", "emergency_number", "ice_phone", "emergency contact phone"],
        "emergency_contact_relationship": ["emergency_contact_relationship", "emergency_relationship", "relationship", "ice_relationship", "emergency contact relationship"],
        "department_code": ["department_code", "department", "dept", "dept_code", "division", "department code"],
        "role_name": ["role_name", "role", "position", "job_role", "title_role", "role name"],
        "job_title": ["job_title", "title", "designation", "position_title", "position", "job title"],
        "hire_date": ["hire_date", "joining_date", "start_date", "employment_date", "date_hired", "date_of_joint", "hire date"],
        "manager_code": ["manager_code", "manager", "supervisor", "reports_to", "supervisor_code", "manager code"],
        "status": ["status", "employee_status", "account_status", "emp_status"],
        "employment_status": ["employment_status", "emp_status", "contract_type", "employment_type", "employment status"],
        "grade_level": ["grade_level", "grade", "level", "pay_grade", "salary_grade", "grade level"],
        "basic_salary": ["basic_salary", "salary", "base_salary", "monthly_salary", "wage", "basic salary"],
        "probation_end_date": ["probation_end_date", "probation_end", "end_of_probation", "probation_completion", "probation end date"],
        "confirmation_date": ["confirmation_date", "confirmed_date", "permanent_date", "regularization_date", "confirmation date"],
        "bank_name": ["bank_name", "bank", "banking_institution", "bank name"],
        "bank_account_number": ["bank_account_number", "account_number", "bank_account", "account_no", "account", "account_number", "bank account number"],
        "bank_branch": ["bank_branch", "branch", "branch_name", "bank_branch_name", "bank branch"],
        "tax_identification_number": ["tax_identification_number", "tax_id", "tin", "tax_number", "tax_id_number", "nic", "tax identification number"],
        "marital_status": ["marital_status", "marital", "marriage_status", "civil_status", "marital status"],
        "spouse_name": ["spouse_name", "spouse", "partner_name", "husband_wife", "partner", "spouse name"],
        "number_of_children": ["number_of_children", "children", "dependents", "kids", "child_count", "number of children"],
        "work_location": ["work_location", "location", "office", "workplace", "site", "branch_location", "work location"]
    }

    if 'first_name' not in df.columns:
        for col in df.columns:
            col_lower = col.lower()
            if 'first' in col_lower or ('name' in col_lower and 'last' not in col_lower and 'middle' not in col_lower):
                df['first_name'] = df[col]
                break

    field_mapping = {}
    for standard_field, variants in field_name_variants.items():
        for column in df.columns:
            column_clean = column.lower()
            column_with_underscores = column_clean.replace(" ", "_").replace("-", "_")
            column_without_spaces = column_clean.replace(" ", "").replace("-", "")
            column_without_underscores = column_clean.replace("_", "").replace("-", "")
            
            if (column_clean in variants or 
                column_with_underscores in variants or 
                column_without_spaces in variants or
                column_without_underscores in variants):
                field_mapping[standard_field] = column
                break
    
    missing_required = [field for field in required_fields if field not in field_mapping]
    extra_fields = [field for field in df.columns if not any(
        field.lower() in variants or 
        field.lower().replace(" ", "_").replace("-", "_") in variants or
        field.lower().replace(" ", "").replace("-", "") in variants or
        field.lower().replace("_", "").replace("-", "") in variants
        for variants in field_name_variants.values())]

    return (len(missing_required) == 0, missing_required, extra_fields, field_mapping)

def map_excel_data(row, field_mapping):
    mapped_data = {}

    for expected_field, excel_field in field_mapping.items():
        if excel_field in row:
            mapped_data[expected_field] = row[excel_field]

    return mapped_data


def validate_employee_data(data, row_index, update_existing=False):
    errors = []
    validated_data = {}

    if not data.get("first_name"):
        errors.append(f"Row {row_index}: First name is required")
    else:
        full_name = str(data.get("first_name")).strip()
        if not data.get("last_name") and " " in full_name:
            name_parts = full_name.split()
            validated_data["first_name"] = " ".join(name_parts[:-1])
            validated_data["last_name"] = name_parts[-1]
        else:
            validated_data["first_name"] = full_name

    if data.get("last_name"):
        validated_data["last_name"] = str(data.get("last_name")).strip()

    if data.get("email"):
        email = str(data.get("email")).strip().lower()
        if "@" not in email or "." not in email:
            errors.append(f"Row {row_index}: Invalid email format")
        else:
            validated_data["email"] = email
            if not update_existing and CustomUser.objects.filter(email=email).exists():
                errors.append(f"Row {row_index}: Email {email} already exists")

    if "middle_name" in data and data.get("middle_name") is not None:
        validated_data["middle_name"] = str(data.get("middle_name")).strip()

    if "phone_number" in data and data.get("phone_number") is not None:
        phone = str(data.get("phone_number")).strip()
        clean_phone = phone.replace(" ", "").replace("-", "").replace(".", "")

        import re

        if clean_phone.startswith("+"):
            phone_regex = re.compile(r"^\+[0-9]{1,14}$")
        else:
            phone_regex = re.compile(r"^[0-9]{1,14}$")

        if not phone_regex.match(clean_phone):
            clean_phone = re.sub(r"[^0-9+]", "", clean_phone)
            if not phone_regex.match(clean_phone):
                validated_data["phone_number"] = clean_phone
            else:
                validated_data["phone_number"] = clean_phone
        else:
            validated_data["phone_number"] = clean_phone

    if "date_of_birth" in data and data.get("date_of_birth") is not None:
        try:
            if isinstance(data.get("date_of_birth"), str):
                dob_str = data.get("date_of_birth")
                if "." in dob_str:
                    dob_parts = dob_str.split(".")
                    if len(dob_parts) == 3:
                        dob_str = f"{dob_parts[2]}-{dob_parts[1]}-{dob_parts[0]}"
                try:
                    dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except:
                    try:
                        dob = datetime.strptime(dob_str, "%d.%m.%Y").date()
                    except:
                        try:
                            dob = datetime.strptime(dob_str, "%m/%d/%Y").date()
                        except:
                            dob = datetime.strptime(dob_str, "%d/%m/%Y").date()
            else:
                dob = data.get("date_of_birth")

            today = timezone.now().date()
            age = (
                today.year
                - dob.year
                - ((today.month, today.day) < (dob.month, dob.day))
            )

            try:
                min_age = int(SystemConfiguration.get_setting("MIN_EMPLOYEE_AGE", "18"))
                max_age = int(SystemConfiguration.get_setting("MAX_EMPLOYEE_AGE", "65"))
            except:
                min_age = 18
                max_age = 65

            if age < min_age:
                errors.append(
                    f"Row {row_index}: Employee must be at least {min_age} years old"
                )
            elif age > max_age:
                errors.append(
                    f"Row {row_index}: Employee age exceeds maximum allowed ({max_age})"
                )
            else:
                validated_data["date_of_birth"] = dob
        except Exception as e:
            errors.append(f"Row {row_index}: Invalid date of birth format - {str(e)}")

    if "gender" in data and data.get("gender") is not None:
        gender = str(data.get("gender")).strip().upper()
        if gender in ["M", "MALE"]:
            validated_data["gender"] = "M"
        elif gender in ["F", "FEMALE"]:
            validated_data["gender"] = "F"
        elif gender in ["O", "OTHER"]:
            validated_data["gender"] = "O"
        else:
            errors.append(f"Row {row_index}: Invalid gender. Use M, F, or O")

    address_fields = ["address_line1", "address_line2", "city", "state", "postal_code"]
    for field in address_fields:
        if field in data and data.get(field) is not None:
            validated_data[field] = str(data.get(field)).strip()

    if "country" in data and data.get("country") is not None:
        validated_data["country"] = str(data.get("country")).strip()
    else:
        validated_data["country"] = "Sri Lanka"

    emergency_fields = [
        "emergency_contact_name",
        "emergency_contact_phone",
        "emergency_contact_relationship",
    ]
    for field in emergency_fields:
        if field in data and data.get(field) is not None:
            validated_data[field] = str(data.get(field)).strip()

    if "department_code" in data and data.get("department_code") is not None:
        dept_code = str(data.get("department_code")).strip().upper()
        try:
            department = Department.active.get(code=dept_code)
            validated_data["department"] = department
        except Department.DoesNotExist:
            pass

    if "role_name" in data and data.get("role_name") is not None:
        role_name = str(data.get("role_name")).strip()
        try:
            role = Role.active.get(name__iexact=role_name)
            validated_data["role"] = role
        except Role.DoesNotExist:
            try:
                role = Role.active.get(name__icontains=role_name)
                validated_data["role"] = role
            except:
                pass

    if "job_title" in data and data.get("job_title") is not None:
        validated_data["job_title"] = str(data.get("job_title")).strip()

    if "hire_date" in data and data.get("hire_date") is not None:
        try:
            if isinstance(data.get("hire_date"), str):
                hire_date_str = data.get("hire_date")
                if "." in hire_date_str:
                    hire_parts = hire_date_str.split(".")
                    if len(hire_parts) == 3:
                        hire_date_str = (
                            f"{hire_parts[2]}-{hire_parts[1]}-{hire_parts[0]}"
                        )
                try:
                    hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d").date()
                except:
                    try:
                        hire_date = datetime.strptime(hire_date_str, "%d.%m.%Y").date()
                    except:
                        try:
                            hire_date = datetime.strptime(
                                hire_date_str, "%m/%d/%Y"
                            ).date()
                        except:
                            hire_date = datetime.strptime(
                                hire_date_str, "%d/%m/%Y"
                            ).date()
            else:
                hire_date = data.get("hire_date")

            if hire_date > timezone.now().date():
                errors.append(f"Row {row_index}: Hire date cannot be in the future")
            else:
                validated_data["hire_date"] = hire_date
        except Exception as e:
            errors.append(f"Row {row_index}: Invalid hire date format - {str(e)}")

    if "manager_code" in data and data.get("manager_code") is not None:
        manager_code = str(data.get("manager_code")).strip().upper()
        try:
            manager = CustomUser.active.get(employee_code=manager_code)
            validated_data["manager"] = manager
        except CustomUser.DoesNotExist:
            pass

    if "status" in data and data.get("status") is not None:
        status = str(data.get("status")).strip().upper()
        if status in ["ACTIVE", "INACTIVE", "SUSPENDED", "TERMINATED"]:
            validated_data["status"] = status
        else:
            validated_data["status"] = "ACTIVE"
    else:
        validated_data["status"] = "ACTIVE"

    if "employment_status" in data and data.get("employment_status") is not None:
        emp_status = str(data.get("employment_status")).strip().upper()
        if emp_status in ["PROBATION", "CONFIRMED", "CONTRACT", "INTERN", "CONSULTANT"]:
            validated_data["employment_status"] = emp_status
        elif "FULL" in emp_status and "TIME" in emp_status:
            validated_data["employment_status"] = "CONFIRMED"
        elif "PART" in emp_status and "TIME" in emp_status:
            validated_data["employment_status"] = "CONTRACT"
        else:
            validated_data["employment_status"] = "CONFIRMED"
    else:
        validated_data["employment_status"] = "CONFIRMED"

    if "grade_level" in data and data.get("grade_level") is not None:
        grade = str(data.get("grade_level")).strip().upper()
        if grade in [
            "ENTRY",
            "JUNIOR",
            "SENIOR",
            "LEAD",
            "MANAGER",
            "DIRECTOR",
            "EXECUTIVE",
            "G1",
            "G2",
            "G3",
            "G4",
            "G5",
            "G6",
            "G7",
            "G8",
            "G9",
            "G10",
        ]:
            validated_data["grade_level"] = grade
        else:
            if grade.startswith("G") and grade[1:].isdigit():
                validated_data["grade_level"] = grade
            else:
                validated_data["grade_level"] = "ENTRY"
    else:
        validated_data["grade_level"] = "ENTRY"

    if "basic_salary" in data and data.get("basic_salary") is not None:
        try:
            salary_str = str(data.get("basic_salary")).replace(",", "").replace(" ", "")
            salary = Decimal(salary_str)
            if salary <= 0:
                errors.append(
                    f"Row {row_index}: Basic salary must be greater than zero"
                )
            elif salary > Decimal("1000000.00"):
                validated_data["basic_salary"] = salary
            else:
                validated_data["basic_salary"] = salary
        except (InvalidOperation, ValueError):
            errors.append(f"Row {row_index}: Invalid basic salary format")
    else:
        validated_data["basic_salary"] = Decimal("50000.00")

    if "probation_end_date" in data and data.get("probation_end_date") is not None:
        try:
            if isinstance(data.get("probation_end_date"), str):
                prob_end_str = data.get("probation_end_date")
                if "." in prob_end_str:
                    prob_parts = prob_end_str.split(".")
                    if len(prob_parts) == 3:
                        prob_end_str = (
                            f"{prob_parts[2]}-{prob_parts[1]}-{prob_parts[0]}"
                        )
                try:
                    prob_end_date = datetime.strptime(prob_end_str, "%Y-%m-%d").date()
                except:
                    try:
                        prob_end_date = datetime.strptime(
                            prob_end_str, "%d.%m.%Y"
                        ).date()
                    except:
                        try:
                            prob_end_date = datetime.strptime(
                                prob_end_str, "%m/%d/%Y"
                            ).date()
                        except:
                            prob_end_date = datetime.strptime(
                                prob_end_str, "%d/%m/%Y"
                            ).date()
            else:
                prob_end_date = data.get("probation_end_date")

            validated_data["probation_end_date"] = prob_end_date
        except Exception as e:
            if "hire_date" in validated_data:
                validated_data["probation_end_date"] = validated_data[
                    "hire_date"
                ] + timedelta(days=90)
            else:
                validated_data["probation_end_date"] = (
                    timezone.now().date() + timedelta(days=90)
                )
    elif validated_data.get("employment_status") == "PROBATION":
        if "hire_date" in validated_data:
            validated_data["probation_end_date"] = validated_data[
                "hire_date"
            ] + timedelta(days=90)
        else:
            validated_data["probation_end_date"] = timezone.now().date() + timedelta(
                days=90
            )

    if "confirmation_date" in data and data.get("confirmation_date") is not None:
        try:
            if isinstance(data.get("confirmation_date"), str):
                conf_date_str = data.get("confirmation_date")
                if "." in conf_date_str:
                    conf_parts = conf_date_str.split(".")
                    if len(conf_parts) == 3:
                        conf_date_str = (
                            f"{conf_parts[2]}-{conf_parts[1]}-{conf_parts[0]}"
                        )
                try:
                    conf_date = datetime.strptime(conf_date_str, "%Y-%m-%d").date()
                except:
                    try:
                        conf_date = datetime.strptime(conf_date_str, "%d.%m.%Y").date()
                    except:
                        try:
                            conf_date = datetime.strptime(
                                conf_date_str, "%m/%d/%Y"
                            ).date()
                        except:
                            conf_date = datetime.strptime(
                                conf_date_str, "%d/%m/%Y"
                            ).date()
            else:
                conf_date = data.get("confirmation_date")

            validated_data["confirmation_date"] = conf_date
        except Exception as e:
            if "hire_date" in validated_data:
                validated_data["confirmation_date"] = validated_data[
                    "hire_date"
                ] + timedelta(days=90)

    bank_fields = ["bank_name", "bank_branch"]
    for field in bank_fields:
        if field in data and data.get(field) is not None:
            validated_data[field] = str(data.get(field)).strip()

    if "bank_account_number" in data and data.get("bank_account_number") is not None:
        account_num = str(data.get("bank_account_number")).strip()
        account_num = account_num.replace("-", "").replace(" ", "").replace(".", "")
        import re

        if not re.match(r"^[0-9]{1,20}$", account_num):
            validated_data["bank_account_number"] = "0000000000"
        else:
            validated_data["bank_account_number"] = account_num

    if (
        "tax_identification_number" in data
        and data.get("tax_identification_number") is not None
    ):
        tax_id = str(data.get("tax_identification_number")).strip()
        existing_tax_id = EmployeeProfile.objects.filter(
            tax_identification_number=tax_id
        )
        if existing_tax_id.exists() and not update_existing:
            errors.append(
                f"Row {row_index}: Tax identification number is already in use"
            )
        else:
            validated_data["tax_identification_number"] = tax_id

    if "marital_status" in data and data.get("marital_status") is not None:
        marital = str(data.get("marital_status")).strip().upper()
        if marital in ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED"]:
            validated_data["marital_status"] = marital
        else:
            validated_data["marital_status"] = "SINGLE"
    else:
        validated_data["marital_status"] = "SINGLE"

    if "spouse_name" in data and data.get("spouse_name") is not None:
        spouse_name = str(data.get("spouse_name")).strip()
        validated_data["spouse_name"] = spouse_name
    elif validated_data.get("marital_status") == "MARRIED":
        validated_data["spouse_name"] = "Not Provided"

    if "number_of_children" in data and data.get("number_of_children") is not None:
        try:
            num_children = int(data.get("number_of_children"))
            if num_children < 0:
                validated_data["number_of_children"] = 0
            else:
                validated_data["number_of_children"] = num_children
        except (ValueError, TypeError):
            validated_data["number_of_children"] = 0
    else:
        validated_data["number_of_children"] = 0

    if "work_location" in data and data.get("work_location") is not None:
        validated_data["work_location"] = str(data.get("work_location")).strip()

    return (len(errors) == 0, errors, validated_data)


def import_employees_from_excel(
    file_obj, update_existing=False, skip_errors=False, created_by=None, import_job=None
):
    results = {
        "total_rows": 0,
        "success_count": 0,
        "error_count": 0,
        "skipped_count": 0,
        "updated_count": 0,
        "created_count": 0,
        "errors": [],
        "warnings": [],
        "new_users": [],
    }

    try:
        _thread_locals.is_bulk_import = True

        df = read_excel_file(file_obj)
        results["total_rows"] = len(df)

        if import_job:
            import_job.total_rows = len(df)
            import_job.status = "PROCESSING"
            import_job.save()

        normalized_columns = [
            str(col).lower().strip().replace(" ", "_") for col in df.columns
        ]
        df.columns = normalized_columns

        field_mappings = {
            "first_name": ["first_name", "firstname", "fname", "first"],
            "last_name": ["last_name", "lastname", "lname", "last", "surname"],
            "middle_name": ["middle_name", "middlename", "mname", "middle"],
            "email": ["email", "email_address", "emailaddress", "mail"],
            "phone_number": [
                "phone_number",
                "phone",
                "mobile",
                "cell",
                "contact",
                "telephone",
            ],
            "date_of_birth": ["date_of_birth", "dob", "birth_date", "birthdate"],
            "gender": ["gender", "sex"],
            "address_line1": [
                "address_line1",
                "address1",
                "address",
                "street_address",
                "primary_address",
            ],
            "address_line2": ["address_line2", "address2", "secondary_address"],
            "city": ["city", "town"],
            "state": ["state", "province", "region"],
            "postal_code": ["postal_code", "zip", "zipcode", "zip_code", "postcode"],
            "country": ["country", "nation"],
            "emergency_contact_name": [
                "emergency_contact_name",
                "emergency_name",
                "emergency_contact",
            ],
            "emergency_contact_phone": [
                "emergency_contact_phone",
                "emergency_phone",
                "emergency_number",
            ],
            "emergency_contact_relationship": [
                "emergency_contact_relationship",
                "emergency_relationship",
                "relationship",
            ],
            "department_code": ["department_code", "department", "dept", "dept_code"],
            "role_name": ["role_name", "role", "position", "job_role"],
            "job_title": ["job_title", "title", "designation"],
            "hire_date": ["hire_date", "joining_date", "start_date", "employment_date"],
            "manager_code": ["manager_code", "manager", "supervisor", "reports_to"],
            "status": ["status", "employee_status", "account_status"],
            "employment_status": ["employment_status", "emp_status", "contract_type"],
            "grade_level": ["grade_level", "grade", "level", "pay_grade"],
            "basic_salary": ["basic_salary", "salary", "base_salary", "monthly_salary"],
            "probation_end_date": [
                "probation_end_date",
                "probation_end",
                "end_of_probation",
            ],
            "confirmation_date": [
                "confirmation_date",
                "confirmed_date",
                "permanent_date",
            ],
            "bank_name": ["bank_name", "bank"],
            "bank_account_number": [
                "bank_account_number",
                "account_number",
                "bank_account",
                "account_no",
            ],
            "bank_branch": ["bank_branch", "branch", "branch_name"],
            "tax_identification_number": [
                "tax_identification_number",
                "tax_id",
                "tin",
                "tax_number",
            ],
            "marital_status": ["marital_status", "marital", "marriage_status"],
            "spouse_name": ["spouse_name", "spouse", "partner_name", "husband_wife"],
            "number_of_children": [
                "number_of_children",
                "children",
                "dependents",
                "kids",
            ],
            "work_location": ["work_location", "location", "office", "workplace"],
        }

        field_mapping = {}
        for system_field, possible_names in field_mappings.items():
            for col_name in possible_names:
                if col_name in normalized_columns:
                    field_mapping[system_field] = col_name
                    break

        required_fields = ["first_name"]
        missing_required = [
            field for field in required_fields if field not in field_mapping
        ]

        if missing_required:
            results["error_count"] = results["total_rows"]
            results["errors"].append(
                f"Missing required fields: {', '.join(missing_required)}"
            )
            if import_job:
                import_job.status = "FAILED"
                import_job.error_count = results["error_count"]
                import_job.results = results
                import_job.completed_at = timezone.now()
                import_job.save()
            return results

        extra_fields = [
            col
            for col in normalized_columns
            if not any(
                col in possible_names for possible_names in field_mappings.values()
            )
        ]
        if extra_fields:
            results["warnings"].append(
                f"Extra fields found and will be ignored: {', '.join(extra_fields)}"
            )

        for index, row in df.iterrows():
            row_index = index + 2

            try:
                mapped_data = {}
                for system_field, excel_field in field_mapping.items():
                    value = row[excel_field]
                    if pd.isna(value):
                        mapped_data[system_field] = None
                    else:
                        mapped_data[system_field] = value

                is_valid, validation_errors, validated_data = validate_employee_data(
                    mapped_data, row_index, update_existing
                )

                if not is_valid and not skip_errors:
                    results["error_count"] += 1
                    results["errors"].extend(validation_errors)
                    if import_job:
                        import_job.processed_rows = index + 1
                        import_job.error_count = results["error_count"]
                        import_job.save()
                    continue
                elif not is_valid and skip_errors:
                    results["skipped_count"] += 1
                    results["errors"].extend(validation_errors)
                    if import_job:
                        import_job.processed_rows = index + 1
                        import_job.error_count = results["error_count"]
                        import_job.save()
                    continue

                with transaction.atomic():
                    existing_user = None
                    if update_existing:
                        try:
                            existing_user = CustomUser.objects.get(
                                email=validated_data["email"]
                            )
                        except CustomUser.DoesNotExist:
                            pass

                    if existing_user:
                        for field, value in validated_data.items():
                            if field in ["department", "role", "manager"]:
                                setattr(existing_user, field, value)
                            elif field not in [
                                "employment_status",
                                "grade_level",
                                "basic_salary",
                                "probation_end_date",
                                "confirmation_date",
                                "bank_name",
                                "bank_account_number",
                                "bank_branch",
                                "tax_identification_number",
                                "marital_status",
                                "spouse_name",
                                "number_of_children",
                                "work_location",
                            ]:
                                setattr(existing_user, field, value)

                        existing_user._skip_validation = True
                        existing_user.save()

                        profile = existing_user.employee_profile
                        profile_fields = [
                            "employment_status",
                            "grade_level",
                            "basic_salary",
                            "probation_end_date",
                            "confirmation_date",
                            "bank_name",
                            "bank_account_number",
                            "bank_branch",
                            "tax_identification_number",
                            "marital_status",
                            "spouse_name",
                            "number_of_children",
                            "work_location",
                        ]

                        for field in profile_fields:
                            if field in validated_data:
                                setattr(profile, field, validated_data[field])

                        profile.is_active = existing_user.status == "ACTIVE"
                        profile.save(bypass_validation=True)

                        results["updated_count"] += 1
                        results["success_count"] += 1
                    else:
                        user_fields = {
                            k: v
                            for k, v in validated_data.items()
                            if k
                            not in [
                                "employment_status",
                                "grade_level",
                                "basic_salary",
                                "probation_end_date",
                                "confirmation_date",
                                "bank_name",
                                "bank_account_number",
                                "bank_branch",
                                "tax_identification_number",
                                "marital_status",
                                "spouse_name",
                                "number_of_children",
                                "work_location",
                            ]
                        }

                        user_fields["is_active"] = (
                            user_fields.get("status", "ACTIVE") == "ACTIVE"
                        )
                        user_fields["is_verified"] = False
                        user_fields["must_change_password"] = True
                        user_fields["created_by"] = created_by

                        temp_password = CustomUser.objects.make_random_password()

                        new_user = CustomUser(**user_fields)
                        new_user.set_password(temp_password)
                        new_user._skip_validation = True
                        new_user.save()

                        profile_fields = {
                            k: v
                            for k, v in validated_data.items()
                            if k
                            in [
                                "employment_status",
                                "grade_level",
                                "basic_salary",
                                "probation_end_date",
                                "confirmation_date",
                                "bank_name",
                                "bank_account_number",
                                "bank_branch",
                                "tax_identification_number",
                                "marital_status",
                                "spouse_name",
                                "number_of_children",
                                "work_location",
                            ]
                        }

                        profile_fields["user"] = new_user
                        profile_fields["is_active"] = new_user.is_active
                        profile_fields["created_by"] = created_by

                        profile = EmployeeProfile(**profile_fields)
                        profile.save(bypass_validation=True)

                        results["created_count"] += 1
                        results["success_count"] += 1

                        results.setdefault("new_users", []).append(
                            {
                                "email": new_user.email,
                                "employee_code": new_user.employee_code,
                                "name": new_user.get_full_name(),
                                "temp_password": temp_password,
                            }
                        )

            except Exception as e:
                logger.error(f"Error processing row {row_index}: {str(e)}")
                results["error_count"] += 1
                results["errors"].append(
                    f"Row {row_index}: Unexpected error - {str(e)}"
                )
                if not skip_errors:
                    continue

            finally:
                if import_job:
                    import_job.processed_rows = index + 1
                    import_job.success_count = results["success_count"]
                    import_job.error_count = results["error_count"]
                    import_job.created_count = results["created_count"]
                    import_job.updated_count = results["updated_count"]
                    import_job.save()

    except Exception as e:
        logger.error(f"Error during employee import: {str(e)}")
        results["error_count"] = results["total_rows"]
        results["errors"].append(f"Error processing file: {str(e)}")
        if import_job:
            import_job.status = "FAILED"
            import_job.error_count = results["error_count"]
            import_job.results = results
            import_job.completed_at = timezone.now()
            import_job.save()

    finally:
        _thread_locals.is_bulk_import = False
        if import_job:
            import_job.status = "COMPLETED"
            import_job.processed_rows = results["total_rows"]
            import_job.success_count = results["success_count"]
            import_job.error_count = results["error_count"]
            import_job.created_count = results["created_count"]
            import_job.updated_count = results["updated_count"]
            import_job.results = results
            import_job.completed_at = timezone.now()
            import_job.save()

    return results

