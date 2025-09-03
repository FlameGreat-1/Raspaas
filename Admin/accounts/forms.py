from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import RegexValidator, EmailValidator
from django.contrib.admin.widgets import AdminDateWidget
from decimal import Decimal
from .models import Department, Role, AuditLog, SystemConfiguration, CustomUser
from employees.models import EmployeeProfile

from .utils import validate_password_strength
import re
from datetime import datetime, timedelta

User = get_user_model()

def validate_password_field(password):
    is_valid, errors = validate_password_strength(password)
    if not is_valid:
        raise ValidationError(errors)
    return password

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=150,  
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username, Email, or Employee Code",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
        label="Login ID", 
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
        label="Password",
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Remember me",
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            try:
                from django.db.models import Q

                user = User.objects.get(
                    Q(username__iexact=username)
                    | Q(email__iexact=username)
                    | Q(employee_code__iexact=username)
                )

                if user.is_account_locked():
                    raise ValidationError(
                        "Your account is temporarily locked due to multiple failed login attempts. Please try again later.",
                        code="account_locked",
                    )

                if not user.is_active:
                    raise ValidationError(
                        "This account has been deactivated.", code="inactive"
                    )

                if user.status != "ACTIVE":
                    raise ValidationError(
                        f"Account status is {user.get_status_display()}. Please contact HR.",
                        code="invalid_status",
                    )

                self.user_cache = authenticate(
                    self.request, username=username, password=password
                )

                if self.user_cache is None:
                    user.increment_failed_login()
                    raise ValidationError(
                        "Invalid login credentials.", code="invalid_login"
                    )
                else:
                    user.reset_failed_login()
                    self.confirm_login_allowed(self.user_cache)

            except User.DoesNotExist:
                raise ValidationError(
                    "Invalid login credentials.", code="invalid_login"
                )

        return self.cleaned_data

    def get_user(self):
        return self.user_cache

class EmployeeRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Enter password"}
        ),
        help_text="Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character.",
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm password"}
        ),
    )
    basic_salary = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        initial=50000.00,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Basic Salary (LKR)",
                "step": "0.01",
                "min": "0.01",
            }
        ),
        help_text="Employee's basic monthly salary in LKR",
    )
    employment_status = forms.ChoiceField(
        choices=EmployeeProfile.EMPLOYMENT_STATUS_CHOICES,
        initial="PROBATION",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    grade_level = forms.ChoiceField(
        choices=EmployeeProfile.GRADE_LEVELS,
        initial="ENTRY",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    probation_end_date = forms.DateField(
        required=False,
        widget=AdminDateWidget(attrs={"class": "form-control"}),
        help_text="Required for probation status employees",
    )
    confirmation_date = forms.DateField(
        required=False,
        widget=AdminDateWidget(attrs={"class": "form-control"}),
        help_text="Date when employee was confirmed",
    )
    bank_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    bank_account_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter 8-20 digit account number",
            }
        ),
        help_text="Bank account number for salary payments",
    )
    bank_branch = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    tax_identification_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter unique tax ID"}
        ),
        help_text="Unique tax identification number",
    )
    marital_status = forms.ChoiceField(
        choices=EmployeeProfile.MARITAL_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    spouse_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter spouse name if married",
            }
        ),
    )
    number_of_children = forms.IntegerField(
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
    )
    work_location = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter work location/office",
            }
        ),
    )

    class Meta:
        model = CustomUser
        fields = [
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
            "department",
            "role",
            "job_title",
            "hire_date",
            "manager",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First Name",
                    "required": True,
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last Name",
                    "required": True,
                }
            ),
            "middle_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Middle Name (Optional)"}
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email Address",
                    "required": True,
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Phone Number"}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "address_line1": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Address Line 1"}
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Address Line 2 (Optional)",
                }
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "City"}
            ),
            "state": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "State/Province"}
            ),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Postal Code"}
            ),
            "country": forms.TextInput(
                attrs={"class": "form-control", "value": "Sri Lanka"}
            ),
            "emergency_contact_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Emergency Contact Name"}
            ),
            "emergency_contact_phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Emergency Contact Phone",
                }
            ),
            "emergency_contact_relationship": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Relationship"}
            ),
            "department": forms.Select(
                attrs={"class": "form-select", "required": True}
            ),
            "role": forms.Select(attrs={"class": "form-select", "required": True}),
            "job_title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Job Title"}
            ),
            "hire_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "manager": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.created_by = kwargs.pop("created_by", None)
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.active.all()
        self.fields["role"].queryset = Role.active.all()
        self.fields["manager"].queryset = CustomUser.active.all()
        self.fields["manager"].empty_label = "Select Manager (Optional)"

        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].required = True
        self.fields["department"].required = True
        self.fields["role"].required = True
        self.fields["basic_salary"].required = True

        if self.data.get("employment_status") == "PROBATION":
            self.fields["probation_end_date"].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            if CustomUser.objects.filter(email=email).exists():
                raise ValidationError("Email address already exists.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            phone_regex = re.compile(r"^\+?[1-9]\d{1,14}$")
            if not phone_regex.match(phone):
                raise ValidationError("Enter a valid phone number.")
        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob:
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
                raise ValidationError(f"Employee must be at least {min_age} years old.")
            if age > max_age:
                raise ValidationError("Please verify the date of birth.")
        return dob

    def clean_hire_date(self):
        hire_date = self.cleaned_data.get("hire_date")
        if hire_date:
            if hire_date > timezone.now().date():
                raise ValidationError("Hire date cannot be in the future.")
        return hire_date

    def clean_basic_salary(self):
        salary = self.cleaned_data.get("basic_salary")
        if salary:
            if salary <= 0:
                raise ValidationError("Basic salary must be greater than zero.")
            if salary > Decimal("1000000.00"):
                raise ValidationError(
                    "Basic salary seems unusually high. Please verify."
                )
        return salary

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1:
            validate_password_strength(password1)
            return password1
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        return password2

    def clean_probation_end_date(self):
        probation_end_date = self.cleaned_data.get("probation_end_date")
        employment_status = self.cleaned_data.get("employment_status")
        hire_date = self.cleaned_data.get("hire_date")

        if employment_status == "PROBATION":
            if not probation_end_date:
                raise ValidationError(
                    "Probation end date is required for probation status."
                )

            if probation_end_date <= timezone.now().date():
                raise ValidationError("Probation end date must be in the future.")

            if hire_date and probation_end_date <= hire_date:
                raise ValidationError("Probation end date must be after hire date.")

        return probation_end_date

    def clean_confirmation_date(self):
        confirmation_date = self.cleaned_data.get("confirmation_date")
        hire_date = self.cleaned_data.get("hire_date")

        if confirmation_date:
            if confirmation_date > timezone.now().date():
                raise ValidationError("Confirmation date cannot be in the future.")

            if hire_date and confirmation_date < hire_date:
                raise ValidationError("Confirmation date cannot be before hire date.")

        return confirmation_date

    def clean_tax_identification_number(self):
        tax_id = self.cleaned_data.get("tax_identification_number")
        if tax_id:
            if EmployeeProfile.objects.filter(
                tax_identification_number=tax_id
            ).exists():
                raise ValidationError(
                    "This tax identification number is already in use."
                )
        return tax_id

    def clean_spouse_name(self):
        spouse_name = self.cleaned_data.get("spouse_name")
        marital_status = self.cleaned_data.get("marital_status")

        if marital_status == "MARRIED" and not spouse_name:
            raise ValidationError("Spouse name is required for married employees.")

        if marital_status != "MARRIED" and spouse_name:
            return None

        return spouse_name

    def clean(self):
        cleaned_data = super().clean()
        manager = cleaned_data.get("manager")
        probation_end_date = cleaned_data.get("probation_end_date")
        confirmation_date = cleaned_data.get("confirmation_date")
        employment_status = cleaned_data.get("employment_status")

        if manager and self.instance and manager == self.instance:
            raise ValidationError("Employee cannot be their own manager.")

        if (
            probation_end_date
            and confirmation_date
            and confirmation_date <= probation_end_date
        ):
            raise ValidationError(
                {
                    "confirmation_date": "Confirmation date must be after probation end date."
                }
            )

        if employment_status == "PROBATION" and not probation_end_date:
            raise ValidationError(
                {
                    "probation_end_date": "Probation end date is required for probation status."
                }
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.must_change_password = True
        user.password_changed_at = timezone.now()
        user.is_verified = False
        user.status = "ACTIVE"

        if self.created_by:
            user.created_by = self.created_by

        if commit:
            user.save()

            EmployeeProfile.objects.create(
                user=user,
                employment_status=self.cleaned_data.get("employment_status"),
                grade_level=self.cleaned_data.get("grade_level"),
                basic_salary=self.cleaned_data.get("basic_salary"),
                probation_end_date=self.cleaned_data.get("probation_end_date"),
                confirmation_date=self.cleaned_data.get("confirmation_date"),
                bank_name=self.cleaned_data.get("bank_name"),
                bank_account_number=self.cleaned_data.get("bank_account_number"),
                bank_branch=self.cleaned_data.get("bank_branch"),
                tax_identification_number=self.cleaned_data.get(
                    "tax_identification_number"
                ),
                marital_status=self.cleaned_data.get("marital_status"),
                spouse_name=self.cleaned_data.get("spouse_name"),
                number_of_children=self.cleaned_data.get("number_of_children") or 0,
                work_location=self.cleaned_data.get("work_location"),
                is_active=True,
                created_by=self.created_by,
            )

        return user

class EmployeeUpdateForm(forms.ModelForm):
    basic_salary = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Basic Salary (LKR)",
                "step": "0.01",
                "min": "0.01",
            }
        ),
        help_text="Employee's basic monthly salary in LKR",
    )
    employment_status = forms.ChoiceField(
        choices=EmployeeProfile.EMPLOYMENT_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    grade_level = forms.ChoiceField(
        choices=EmployeeProfile.GRADE_LEVELS,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    probation_end_date = forms.DateField(
        required=False,
        widget=AdminDateWidget(attrs={"class": "form-control"}),
        help_text="Required for probation status employees",
    )
    confirmation_date = forms.DateField(
        required=False,
        widget=AdminDateWidget(attrs={"class": "form-control"}),
        help_text="Date when employee was confirmed",
    )
    bank_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    bank_account_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter 8-20 digit account number",
            }
        ),
        help_text="Bank account number for salary payments",
    )
    bank_branch = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    tax_identification_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Enter unique tax ID"}
        ),
        help_text="Unique tax identification number",
    )
    marital_status = forms.ChoiceField(
        choices=EmployeeProfile.MARITAL_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    spouse_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter spouse name if married",
            }
        ),
    )
    number_of_children = forms.IntegerField(
        initial=0,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0"}
        ),
    )
    work_location = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter work location/office",
            }
        ),
    )

    class Meta:
        model = CustomUser
        fields = [
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
            "department",
            "role",
            "job_title",
            "hire_date",
            "manager",
            "status",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "middle_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "address_line1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_relationship": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "department": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "hire_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "manager": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.active.all()
        self.fields["role"].queryset = Role.active.all()
        self.fields["manager"].queryset = CustomUser.active.exclude(
            id=self.instance.id if self.instance else None
        )
        self.fields["manager"].empty_label = "Select Manager (Optional)"

        if self.instance and hasattr(self.instance, "employee_profile"):
            profile = self.instance.employee_profile
            self.fields["basic_salary"].initial = profile.basic_salary
            self.fields["employment_status"].initial = profile.employment_status
            self.fields["grade_level"].initial = profile.grade_level
            self.fields["probation_end_date"].initial = profile.probation_end_date
            self.fields["confirmation_date"].initial = profile.confirmation_date
            self.fields["bank_name"].initial = profile.bank_name
            self.fields["bank_account_number"].initial = profile.bank_account_number
            self.fields["bank_branch"].initial = profile.bank_branch
            self.fields["tax_identification_number"].initial = profile.tax_identification_number
            self.fields["marital_status"].initial = profile.marital_status
            self.fields["spouse_name"].initial = profile.spouse_name
            self.fields["number_of_children"].initial = profile.number_of_children
            self.fields["work_location"].initial = profile.work_location
            
        if self.data.get("employment_status") == "PROBATION":
            self.fields["probation_end_date"].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and self.instance:
            if (
                CustomUser.objects.filter(email=email)
                .exclude(id=self.instance.id)
                .exists()
            ):
                raise ValidationError("Email address already exists.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            phone_regex = re.compile(r"^\+?[1-9]\d{1,14}$")
            if not phone_regex.match(phone):
                raise ValidationError("Enter a valid phone number.")
        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob:
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
                raise ValidationError(f"Employee must be at least {min_age} years old.")
            if age > max_age:
                raise ValidationError("Please verify the date of birth.")
        return dob

    def clean_hire_date(self):
        hire_date = self.cleaned_data.get("hire_date")
        if hire_date:
            if hire_date > timezone.now().date():
                raise ValidationError("Hire date cannot be in the future.")
        return hire_date

    def clean_basic_salary(self):
        salary = self.cleaned_data.get("basic_salary")
        if salary:
            if salary <= 0:
                raise ValidationError("Basic salary must be greater than zero.")
            if salary > Decimal("1000000.00"):
                raise ValidationError("Basic salary seems unusually high. Please verify.")
        return salary
        
    def clean_probation_end_date(self):
        probation_end_date = self.cleaned_data.get("probation_end_date")
        employment_status = self.cleaned_data.get("employment_status")
        hire_date = self.cleaned_data.get("hire_date")

        if employment_status == "PROBATION":
            if not probation_end_date:
                raise ValidationError("Probation end date is required for probation status.")

            if probation_end_date <= timezone.now().date():
                raise ValidationError("Probation end date must be in the future.")

            if hire_date and probation_end_date <= hire_date:
                raise ValidationError("Probation end date must be after hire date.")

        return probation_end_date

    def clean_confirmation_date(self):
        confirmation_date = self.cleaned_data.get("confirmation_date")
        hire_date = self.cleaned_data.get("hire_date")

        if confirmation_date:
            if confirmation_date > timezone.now().date():
                raise ValidationError("Confirmation date cannot be in the future.")

            if hire_date and confirmation_date < hire_date:
                raise ValidationError("Confirmation date cannot be before hire date.")

        return confirmation_date
        
    def clean_tax_identification_number(self):
        tax_id = self.cleaned_data.get("tax_identification_number")
        if tax_id:
            existing_tax_id = EmployeeProfile.objects.filter(tax_identification_number=tax_id)
            if self.instance and hasattr(self.instance, "employee_profile"):
                existing_tax_id = existing_tax_id.exclude(pk=self.instance.employee_profile.pk)
                
            if existing_tax_id.exists():
                raise ValidationError("This tax identification number is already in use.")
        return tax_id
        
    def clean_spouse_name(self):
        spouse_name = self.cleaned_data.get("spouse_name")
        marital_status = self.cleaned_data.get("marital_status")

        if marital_status == "MARRIED" and not spouse_name:
            raise ValidationError("Spouse name is required for married employees.")

        if marital_status != "MARRIED" and spouse_name:
            return None

        return spouse_name

    def clean(self):
        cleaned_data = super().clean()
        manager = cleaned_data.get("manager")
        probation_end_date = cleaned_data.get("probation_end_date")
        confirmation_date = cleaned_data.get("confirmation_date")
        employment_status = cleaned_data.get("employment_status")

        if manager and self.instance and manager == self.instance:
            raise ValidationError("Employee cannot be their own manager.")
            
        if probation_end_date and confirmation_date and confirmation_date <= probation_end_date:
            raise ValidationError({
                "confirmation_date": "Confirmation date must be after probation end date."
            })
            
        if employment_status == "PROBATION" and not probation_end_date:
            raise ValidationError({
                "probation_end_date": "Probation end date is required for probation status."
            })

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit and hasattr(user, "employee_profile"):
            profile = user.employee_profile
            profile.basic_salary = self.cleaned_data.get("basic_salary")
            profile.employment_status = self.cleaned_data.get("employment_status")
            profile.grade_level = self.cleaned_data.get("grade_level")
            profile.probation_end_date = self.cleaned_data.get("probation_end_date")
            profile.confirmation_date = self.cleaned_data.get("confirmation_date")
            profile.bank_name = self.cleaned_data.get("bank_name")
            profile.bank_account_number = self.cleaned_data.get("bank_account_number")
            profile.bank_branch = self.cleaned_data.get("bank_branch")
            profile.tax_identification_number = self.cleaned_data.get("tax_identification_number")
            profile.marital_status = self.cleaned_data.get("marital_status")
            profile.spouse_name = self.cleaned_data.get("spouse_name")
            profile.number_of_children = self.cleaned_data.get("number_of_children") or 0
            profile.work_location = self.cleaned_data.get("work_location")
            profile.is_active = user.status == "ACTIVE"
            
            profile.save(update_fields=[
                'basic_salary', 'employment_status', 'grade_level', 
                'probation_end_date', 'confirmation_date', 'bank_name',
                'bank_account_number', 'bank_branch', 'tax_identification_number',
                'marital_status', 'spouse_name', 'number_of_children',
                'work_location', 'is_active'
            ])

        return user
 
class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Current Password"}
        ),
        required=False,  
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
        help_text="Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character.",
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
    )

    def __init__(self, user, force_change=False, *args, **kwargs):
        self.force_change = force_change
        super().__init__(user, *args, **kwargs)

        if self.force_change:
            self.fields["old_password"].required = False
            self.fields["old_password"].widget = forms.HiddenInput()
        else:
            self.fields["old_password"].required = True

    def clean_old_password(self):
        old_password = self.cleaned_data.get("old_password")

        if not self.force_change:
            if not old_password:
                raise forms.ValidationError("This field is required.")
            if not self.user.check_password(old_password):
                raise forms.ValidationError(
                    "Your old password was entered incorrectly."
                )

        return old_password

    def clean_new_password1(self):
        password1 = self.cleaned_data.get("new_password1")

        if password1:
            return validate_password_field(password1)
        return password1

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("The two password fields didn't match.")
        return password2

    def save(self, commit=True):
        if self.force_change:
            password = self.cleaned_data["new_password1"]
            self.user.set_password(password)
            self.user.must_change_password = False
            self.user.password_changed_at = timezone.now()
            if commit:
                self.user.save()
            return self.user
        else:
            user = super().save(commit=False)
            user.must_change_password = False
            user.password_changed_at = timezone.now()
            if commit:
                user.save()
            return user
class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email Address",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email address",
                "autocomplete": "email",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            if not User.objects.filter(email=email, is_active=True).exists():
                raise ValidationError(
                    "No active account found with this email address."
                )
        return email


class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
        help_text="Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character.",
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
    )

    def clean_new_password1(self):
        password1 = self.cleaned_data.get("new_password1")
        if password1:
            return validate_password_field(password1)
        return password1

    def save(self, commit=True):
        user = super().save(commit=False)
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        if commit:
            user.save()
        return user

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "display_name", "description", "permissions"]
        widgets = {
            "name": forms.Select(attrs={"class": "form-select"}),
            "display_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Display Name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Role Description",
                }
            ),
            "permissions": forms.CheckboxSelectMultiple(
                attrs={"class": "form-check-input"}
            ),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            "first_name",
            "last_name",
            "middle_name",
            "phone_number",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_relationship",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "middle_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "address_line1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_contact_relationship": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            phone_regex = re.compile(r"^\+?[1-9]\d{1,14}$")
            if not phone_regex.match(phone):
                raise ValidationError("Enter a valid phone number.")
        return phone


class BulkEmployeeUploadForm(forms.Form):
    file = forms.FileField(
        label="Upload Employee File",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx,.xls,.csv"}
        ),
        help_text="Upload Excel or CSV file with employee data",
    )

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            if not file.name.endswith((".xlsx", ".xls", ".csv")):
                raise ValidationError(
                    "Only Excel (.xlsx, .xls) and CSV files are allowed."
                )
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size cannot exceed 5MB.")
        return file


class UserSearchForm(forms.Form):
    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search employees...",
                "autocomplete": "off",
            }
        ),
        label="Search",
    )
    department = forms.ModelChoiceField(
        queryset=Department.active.all(),
        required=False,
        empty_label="All Departments",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    role = forms.ModelChoiceField(
        queryset=Role.active.all(),
        required=False,
        empty_label="All Roles",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Status")] + CustomUser.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class BulkEmployeeUploadForm(forms.Form):
    file = forms.FileField(
        label="Upload Employee File",
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".xlsx,.xls,.csv"}
        ),
        help_text="Upload Excel or CSV file with employee data",
    )

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file:
            if not file.name.endswith((".xlsx", ".xls", ".csv")):
                raise ValidationError(
                    "Only Excel (.xlsx, .xls) and CSV files are allowed."
                )
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError("File size cannot exceed 5MB.")
        return file


class AdvancedUserFilterForm(forms.Form):
    hire_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Hired From",
    )
    hire_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Hired To",
    )
    is_active = forms.ChoiceField(
        choices=[("", "All"), ("true", "Active"), ("false", "Inactive")],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Account Status",
    )
    is_verified = forms.ChoiceField(
        choices=[("", "All"), ("true", "Verified"), ("false", "Unverified")],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Verification Status",
    )


class SystemConfigurationForm(forms.ModelForm):
    class Meta:
        model = SystemConfiguration
        fields = ["key", "value", "description", "is_active"]
        widgets = {
            "key": forms.TextInput(attrs={"class": "form-control"}),
            "value": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_key(self):
        key = self.cleaned_data.get("key")
        if key:
            key = key.upper().replace(" ", "_")
        return key
