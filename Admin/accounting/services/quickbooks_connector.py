import requests
import json
import base64
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from accounting.models import (
    QuickBooksCredentials,
    AccountMapping,
    DepartmentMapping,
    SyncConfiguration,
    SyncLog,
    PayrollSyncStatus,
    ExpenseSyncStatus,
)
from payroll.models import (
    PayrollPeriod,
    Payslip,
    PayrollDepartmentSummary,
    SalaryAdvance,
    PayrollBankTransfer,
)

from expenses.models import (
    Expense,
    PurchaseItem,
    ExpenseInstallmentPlan,
    ExpenseInstallment,
)

from employees.models import EmployeeProfile


class QuickBooksConnector:
    def __init__(self, credentials=None):
        if credentials:
            self.credentials = credentials
        else:
            try:
                self.credentials = QuickBooksCredentials.active.latest("created_at")
            except QuickBooksCredentials.DoesNotExist:
                raise Exception("No active QuickBooks credentials found")

        self.base_url = "https://sandbox-quickbooks.api.intuit.com/v3/company"
        if self.credentials.environment == "production":
            self.base_url = "https://quickbooks.api.intuit.com/v3/company"

        self.company_endpoint = f"{self.base_url}/{self.credentials.realm_id}"
        self.token_endpoint = (
            "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        )

        self.refresh_token_if_needed()

    def refresh_token_if_needed(self):
        if self.credentials.is_token_expired():
            self.refresh_token()

    def refresh_token(self):
        auth_header = base64.b64encode(
            f"{self.credentials.client_id}:{self.credentials.client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.credentials.refresh_token,
        }

        response = requests.post(self.token_endpoint, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception(f"Failed to refresh token: {response.text}")

        token_data = response.json()

        self.credentials.access_token = token_data["access_token"]
        self.credentials.refresh_token = token_data.get(
            "refresh_token", self.credentials.refresh_token
        )
        self.credentials.token_expires_at = timezone.now() + timedelta(
            seconds=token_data["expires_in"]
        )
        self.credentials.save(
            update_fields=["access_token", "refresh_token", "token_expires_at"]
        )

    def get_headers(self):
        self.refresh_token_if_needed()
        return {
            "Authorization": f"Bearer {self.credentials.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def make_api_request(self, method, endpoint, data=None, params=None):
        url = f"{self.company_endpoint}/{endpoint}"
        headers = self.get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_message = f"API request failed: {str(e)}"
            if hasattr(e, "response") and e.response:
                error_message += f" - {e.response.text}"
            raise Exception(error_message)

    def get_account_by_id(self, account_id):
        return self.make_api_request("GET", f"account/{account_id}")

    def get_accounts(self, account_type=None):
        params = {"minorversion": "65"}
        if account_type:
            params["account_type"] = account_type

        response = self.make_api_request(
            "GET",
            "query",
            params={
                "query": f"SELECT * FROM Account {f'WHERE AccountType = \'{account_type}\'' if account_type else ''}"
            },
        )

        if "QueryResponse" in response and "Account" in response["QueryResponse"]:
            return response["QueryResponse"]["Account"]
        return []

    def get_departments(self):
        response = self.make_api_request(
            "GET", "query", params={"query": "SELECT * FROM Department"}
        )

        if "QueryResponse" in response and "Department" in response["QueryResponse"]:
            return response["QueryResponse"]["Department"]
        return []

    def get_classes(self):
        response = self.make_api_request(
            "GET", "query", params={"query": "SELECT * FROM Class"}
        )

        if "QueryResponse" in response and "Class" in response["QueryResponse"]:
            return response["QueryResponse"]["Class"]
        return []

    def get_vendors(self, query=None):
        query_str = "SELECT * FROM Vendor"
        if query:
            query_str += f" WHERE DisplayName LIKE '%{query}%'"

        response = self.make_api_request("GET", "query", params={"query": query_str})

        if "QueryResponse" in response and "Vendor" in response["QueryResponse"]:
            return response["QueryResponse"]["Vendor"]
        return []

    def get_vendor_by_employee_code(self, employee_code):
        response = self.make_api_request(
            "GET",
            "query",
            params={
                "query": f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{employee_code}%'"
            },
        )

        if "QueryResponse" in response and "Vendor" in response["QueryResponse"]:
            vendors = response["QueryResponse"]["Vendor"]
            if vendors:
                return vendors[0]
        return None

    def create_journal_entry(self, journal_data):
        return self.make_api_request("POST", "journalentry", data=journal_data)

    def create_bill(self, bill_data):
        return self.make_api_request("POST", "bill", data=bill_data)

    def create_expense(self, expense_data):
        return self.make_api_request("POST", "purchase", data=expense_data)

    def create_vendor(self, vendor_data):
        return self.make_api_request("POST", "vendor", data=vendor_data)

    def update_vendor(self, vendor_id, vendor_data):
        vendor_data["Id"] = vendor_id
        vendor_data["SyncToken"] = self.get_vendor_sync_token(vendor_id)
        return self.make_api_request("POST", "vendor", data=vendor_data)

    def get_vendor_sync_token(self, vendor_id):
        vendor = self.make_api_request("GET", f"vendor/{vendor_id}")
        if "Vendor" in vendor:
            return vendor["Vendor"]["SyncToken"]
        return "0"

    def get_account_mapping(self, mapping_type, source_id):
        try:
            return AccountMapping.active.get(
                mapping_type=mapping_type, source_id=source_id, is_active=True
            )
        except AccountMapping.DoesNotExist:
            return None

    def get_department_mapping(self, department_id):
        try:
            return DepartmentMapping.active.get(
                department_id=department_id, is_active=True
            )
        except DepartmentMapping.DoesNotExist:
            return None

    def format_decimal(self, value):
        if isinstance(value, Decimal):
            return float(value)
        return value

    def prepare_journal_entry(
        self, txn_date, doc_number, memo, line_items, department_id=None
    ):
        journal_entry = {
            "DocNumber": doc_number,
            "TxnDate": txn_date.strftime("%Y-%m-%d"),
            "PrivateNote": memo,
            "Line": [],
        }

        department_ref = None
        if department_id:
            dept_mapping = self.get_department_mapping(department_id)
            if dept_mapping and dept_mapping.quickbooks_department_id:
                department_ref = {
                    "value": dept_mapping.quickbooks_department_id,
                    "name": dept_mapping.quickbooks_department_name,
                }

        for item in line_items:
            line = {
                "Id": str(item.get("id", uuid.uuid4())),
                "Description": item.get("description", ""),
                "Amount": self.format_decimal(item["amount"]),
                "DetailType": "JournalEntryLineDetail",
                "JournalEntryLineDetail": {
                    "PostingType": item["posting_type"],
                    "AccountRef": {
                        "value": item["account_id"],
                        "name": item.get("account_name", ""),
                    },
                },
            }

            if department_ref and item.get("include_department", True):
                line["JournalEntryLineDetail"]["DepartmentRef"] = department_ref

            if item.get("class_id"):
                line["JournalEntryLineDetail"]["ClassRef"] = {
                    "value": item["class_id"],
                    "name": item.get("class_name", ""),
                }

            if item.get("entity_ref"):
                line["JournalEntryLineDetail"]["Entity"] = item["entity_ref"]

            journal_entry["Line"].append(line)

        return journal_entry

    def create_or_update_employee_vendor(self, employee):
        try:
            employee_code = employee.employee_code
            employee_name = employee.get_full_name()

            existing_vendor = self.get_vendor_by_employee_code(employee_code)

            try:
                profile = EmployeeProfile.objects.get(user=employee)
                has_profile = True
            except EmployeeProfile.DoesNotExist:
                has_profile = False

            vendor_data = {
                "DisplayName": f"{employee_name} ({employee_code})",
                "PrintOnCheckName": employee_name,
                "Active": employee.is_active,
                "CompanyName": settings.COMPANY_NAME if hasattr(settings, 'COMPANY_NAME') else "",
                "PrimaryEmailAddr": {
                    "Address": employee.email or ""
                },
                "PrimaryPhone": {
                    "FreeFormNumber": employee.phone_number or ""
                },
                "BillAddr": {
                    "Line1": employee.address_line1 or "",
                    "Line2": employee.address_line2 or "",
                    "City": employee.city or "",
                    "CountrySubDivisionCode": employee.state or "",
                    "PostalCode": employee.postal_code or "",
                    "Country": employee.country or ""
                },
                "VendorType": "Employee"
            }

            if has_profile:
                if profile.bank_name:
                    vendor_data["APAccountRef"] = {
                        "value": self.get_account_mapping("PAYMENT_METHOD", "BANK_TRANSFER").quickbooks_account_id
                    }

                vendor_data["TaxIdentifier"] = profile.tax_identification_number or ""

                if profile.bank_account_number:
                    vendor_data["GSTIN"] = profile.bank_account_number

                vendor_data["Notes"] = f"Job Title: {employee.job_title or ''}\nDepartment: {employee.department.name if employee.department else ''}"

            if existing_vendor:
                return self.update_vendor(existing_vendor["Id"], vendor_data)
            else:
                return self.create_vendor(vendor_data)

        except Exception as e:
            raise Exception(f"Failed to create/update employee vendor: {str(e)}")

    def get_employee_entity_ref(self, employee):
        vendor = self.get_vendor_by_employee_code(employee.employee_code)
        if vendor:
            return {
                "value": vendor["Id"],
                "name": vendor["DisplayName"],
                "type": "Vendor"
            }

        vendor_response = self.create_or_update_employee_vendor(employee)
        if "Vendor" in vendor_response:
            return {
                "value": vendor_response["Vendor"]["Id"],
                "name": vendor_response["Vendor"]["DisplayName"],
                "type": "Vendor"
            }

        raise Exception(f"Failed to get or create vendor for employee {employee.employee_code}")

    def sync_payroll_period(self, payroll_period_id, user=None):
        try:
            payroll_period = PayrollPeriod.objects.get(id=payroll_period_id)
        except PayrollPeriod.DoesNotExist:
            raise Exception(f"Payroll period with ID {payroll_period_id} not found")

        sync_log = SyncLog.objects.create(
            sync_type="PAYROLL_PERIOD",
            source_id=str(payroll_period.id),
            source_reference=f"{payroll_period.period_name}",
            created_by=user
        )

        try:
            sync_log.mark_as_started()

            payroll_sync_status, created = PayrollSyncStatus.objects.get_or_create(
                payroll_period_id=str(payroll_period.id),
                defaults={
                    "payroll_period_name": payroll_period.period_name,
                    "year": payroll_period.year,
                    "month": payroll_period.month,
                    "total_amount": payroll_period.total_net_salary
                }
            )

            if not created:
                payroll_sync_status.total_amount = payroll_period.total_net_salary
                payroll_sync_status.save(update_fields=["total_amount"])

            if payroll_sync_status.is_synced:
                sync_log.mark_as_completed(1, 1, 0)
                return True, "Payroll period already synced", sync_log

            journal_entry = self.create_payroll_journal_entry(payroll_period)

            qb_response = self.create_journal_entry(journal_entry)

            if qb_response and "JournalEntry" in qb_response:
                qb_id = qb_response["JournalEntry"]["Id"]
                payroll_sync_status.is_synced = True
                payroll_sync_status.last_sync_at = timezone.now()
                payroll_sync_status.quickbooks_reference = qb_id
                payroll_sync_status.sync_log = sync_log
                payroll_sync_status.save()

                sync_log.quickbooks_reference = qb_id
                sync_log.mark_as_completed(1, 1, 0)

                self.sync_payroll_details(payroll_period, user)

                return True, f"Payroll period synced successfully. QuickBooks ID: {qb_id}", sync_log
            else:
                sync_log.mark_as_failed("Failed to create journal entry in QuickBooks")
                return False, "Failed to create journal entry in QuickBooks", sync_log

        except Exception as e:
            error_message = str(e)
            sync_log.mark_as_failed(error_message)
            return False, f"Error syncing payroll period: {error_message}", sync_log

    def sync_payroll_details(self, payroll_period, user=None):
        payslips = Payslip.objects.filter(
            payroll_period=payroll_period,
            status__in=["CALCULATED", "APPROVED", "PAID"]
        )

        for payslip in payslips:
            try:
                self.sync_payslip(payslip, user)
            except Exception as e:
                continue

        salary_advances = SalaryAdvance.objects.filter(
            status__in=["APPROVED", "ACTIVE"],
            disbursement_date__gte=payroll_period.start_date,
            disbursement_date__lte=payroll_period.end_date
        )

        for advance in salary_advances:
            try:
                self.sync_salary_advance(advance, user)
            except Exception as e:
                continue

        bank_transfers = PayrollBankTransfer.objects.filter(
            payroll_period=payroll_period,
            status__in=["GENERATED", "SENT", "PROCESSED", "COMPLETED"]
        )

        for transfer in bank_transfers:
            try:
                self.sync_bank_transfer(transfer, user)
            except Exception as e:
                continue

    def sync_payslip(self, payslip, user=None):
        doc_number = f"PS-{payslip.reference_number}"
        txn_date = payslip.payroll_period.end_date
        memo = f"Payslip for {payslip.employee.get_full_name()} - {payslip.payroll_period.period_name}"

        line_items = []

        employee_entity_ref = self.get_employee_entity_ref(payslip.employee)

        salary_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_EXPENSE")
        if not salary_mapping:
            raise Exception("Salary expense account mapping not found")

        line_items.append({
            "description": f"Basic Salary",
            "amount": payslip.basic_salary,
            "posting_type": "DEBIT",
            "account_id": salary_mapping.quickbooks_account_id,
            "account_name": salary_mapping.quickbooks_account_name,
            "entity_ref": employee_entity_ref
        })

        if payslip.bonus_1 > 0:
            bonus_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "BONUS")
            if bonus_mapping:
                line_items.append({
                    "description": f"Bonus 1",
                    "amount": payslip.bonus_1,
                    "posting_type": "DEBIT",
                    "account_id": bonus_mapping.quickbooks_account_id,
                    "account_name": bonus_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.bonus_2 > 0:
            bonus_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "BONUS")
            if bonus_mapping:
                line_items.append({
                    "description": f"Bonus 2",
                    "amount": payslip.bonus_2,
                    "posting_type": "DEBIT",
                    "account_id": bonus_mapping.quickbooks_account_id,
                    "account_name": bonus_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.transport_allowance > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "TRANSPORT_ALLOWANCE")
            if allowance_mapping:
                line_items.append({
                    "description": f"Transport Allowance",
                    "amount": payslip.transport_allowance,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.telephone_allowance > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "TELEPHONE_ALLOWANCE")
            if allowance_mapping:
                line_items.append({
                    "description": f"Telephone Allowance",
                    "amount": payslip.telephone_allowance,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.fuel_allowance > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "FUEL_ALLOWANCE")
            if allowance_mapping:
                line_items.append({
                    "description": f"Fuel Allowance",
                    "amount": payslip.fuel_allowance,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.meal_allowance > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "MEAL_ALLOWANCE")
            if allowance_mapping:
                line_items.append({
                    "description": f"Meal Allowance",
                    "amount": payslip.meal_allowance,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.attendance_bonus > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "ATTENDANCE_BONUS")
            if allowance_mapping:
                line_items.append({
                    "description": f"Attendance Bonus",
                    "amount": payslip.attendance_bonus,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.performance_bonus > 0:
            allowance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "PERFORMANCE_BONUS")
            if allowance_mapping:
                line_items.append({
                    "description": f"Performance Bonus",
                    "amount": payslip.performance_bonus,
                    "posting_type": "DEBIT",
                    "account_id": allowance_mapping.quickbooks_account_id,
                    "account_name": allowance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.regular_overtime > 0:
            overtime_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "OVERTIME")
            if overtime_mapping:
                line_items.append({
                    "description": f"Regular Overtime",
                    "amount": payslip.regular_overtime,
                    "posting_type": "DEBIT",
                    "account_id": overtime_mapping.quickbooks_account_id,
                    "account_name": overtime_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.friday_overtime > 0:
            overtime_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "WEEKEND_OVERTIME")
            if overtime_mapping:
                line_items.append({
                    "description": f"Weekend Overtime",
                    "amount": payslip.friday_overtime,
                    "posting_type": "DEBIT",
                    "account_id": overtime_mapping.quickbooks_account_id,
                    "account_name": overtime_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.employee_epf_contribution > 0:
            epf_employee_mapping = self.get_account_mapping("PAYROLL_DEDUCTION", "EPF_EMPLOYEE")
            if epf_employee_mapping:
                line_items.append({
                    "description": f"Employee EPF Contribution",
                    "amount": payslip.employee_epf_contribution,
                    "posting_type": "CREDIT",
                    "account_id": epf_employee_mapping.quickbooks_account_id,
                    "account_name": epf_employee_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.employer_epf_contribution > 0:
            epf_employer_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "EPF_EMPLOYER")
            if epf_employer_mapping:
                line_items.append({
                    "description": f"Employer EPF Contribution",
                    "amount": payslip.employer_epf_contribution,
                    "posting_type": "DEBIT",
                    "account_id": epf_employer_mapping.quickbooks_account_id,
                    "account_name": epf_employer_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

                line_items.append({
                    "description": f"Employer EPF Liability",
                    "amount": payslip.employer_epf_contribution,
                    "posting_type": "CREDIT",
                    "account_id": epf_employer_mapping.quickbooks_account_id,
                    "account_name": epf_employer_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.etf_contribution > 0:
            etf_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "ETF_CONTRIBUTION")
            if etf_mapping:
                line_items.append({
                    "description": f"ETF Contribution",
                    "amount": payslip.etf_contribution,
                    "posting_type": "DEBIT",
                    "account_id": etf_mapping.quickbooks_account_id,
                    "account_name": etf_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

                line_items.append({
                    "description": f"ETF Liability",
                    "amount": payslip.etf_contribution,
                    "posting_type": "CREDIT",
                    "account_id": etf_mapping.quickbooks_account_id,
                    "account_name": etf_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.income_tax > 0:
            tax_mapping = self.get_account_mapping("PAYROLL_DEDUCTION", "INCOME_TAX")
            if tax_mapping:
                line_items.append({
                    "description": f"Income Tax",
                    "amount": payslip.income_tax,
                    "posting_type": "CREDIT",
                    "account_id": tax_mapping.quickbooks_account_id,
                    "account_name": tax_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        if payslip.advance_deduction > 0:
            advance_mapping = self.get_account_mapping("PAYROLL_DEDUCTION", "ADVANCE")
            if advance_mapping:
                line_items.append({
                    "description": f"Salary Advance Deduction",
                    "amount": payslip.advance_deduction,
                    "posting_type": "CREDIT",
                    "account_id": advance_mapping.quickbooks_account_id,
                    "account_name": advance_mapping.quickbooks_account_name,
                    "entity_ref": employee_entity_ref
                })

        salary_payable_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_PAYABLE")
        if not salary_payable_mapping:
            raise Exception("Salary payable account mapping not found")

        line_items.append({
            "description": f"Net Salary Payable",
            "amount": payslip.net_salary,
            "posting_type": "CREDIT",
            "account_id": salary_payable_mapping.quickbooks_account_id,
            "account_name": salary_payable_mapping.quickbooks_account_name,
            "entity_ref": employee_entity_ref
        })

        department_id = None
        if payslip.employee.department:
            department_id = payslip.employee.department.id

        journal_entry = self.prepare_journal_entry(txn_date, doc_number, memo, line_items, department_id)
        return self.create_journal_entry(journal_entry)

    def sync_salary_advance(self, advance, user=None):
        doc_number = f"ADV-{advance.reference_number}"
        txn_date = advance.disbursement_date or advance.approved_date or timezone.now().date()
        memo = f"Salary Advance for {advance.employee.get_full_name()} - {advance.purpose_details or advance.reason}"

        line_items = []

        employee_entity_ref = self.get_employee_entity_ref(advance.employee)

        advance_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "ADVANCE_RECEIVABLE")
        if not advance_mapping:
            raise Exception("Advance receivable account mapping not found")

        line_items.append({
            "description": f"Salary Advance - {advance.get_advance_type_display()}",
            "amount": advance.amount,
            "posting_type": "DEBIT",
            "account_id": advance_mapping.quickbooks_account_id,
            "account_name": advance_mapping.quickbooks_account_name,
            "entity_ref": employee_entity_ref
        })

        cash_mapping = self.get_account_mapping("PAYMENT_METHOD", "CASH")
        if not cash_mapping:
            raise Exception("Cash account mapping not found")

        line_items.append({
            "description": f"Cash Payment for Advance",
            "amount": advance.amount,
            "posting_type": "CREDIT",
            "account_id": cash_mapping.quickbooks_account_id,
            "account_name": cash_mapping.quickbooks_account_name
        })

        department_id = None
        if advance.employee.department:
            department_id = advance.employee.department.id

        journal_entry = self.prepare_journal_entry(txn_date, doc_number, memo, line_items, department_id)
        return self.create_journal_entry(journal_entry)

    def sync_bank_transfer(self, transfer, user=None):
        doc_number = f"BT-{transfer.batch_reference}"
        txn_date = transfer.sent_at.date() if transfer.sent_at else timezone.now().date()
        memo = f"Bank Transfer for {transfer.payroll_period.period_name}"

        line_items = []

        salary_payable_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_PAYABLE")
        if not salary_payable_mapping:
            raise Exception("Salary payable account mapping not found")

        line_items.append({
            "description": f"Salary Payment for {transfer.payroll_period.period_name}",
            "amount": transfer.total_amount,
            "posting_type": "DEBIT",
            "account_id": salary_payable_mapping.quickbooks_account_id,
            "account_name": salary_payable_mapping.quickbooks_account_name
        })

        bank_mapping = self.get_account_mapping("PAYMENT_METHOD", "BANK_TRANSFER")
        if not bank_mapping:
            raise Exception("Bank account mapping not found")

        line_items.append({
            "description": f"Bank Transfer for Payroll",
            "amount": transfer.total_amount,
            "posting_type": "CREDIT",
            "account_id": bank_mapping.quickbooks_account_id,
            "account_name": bank_mapping.quickbooks_account_name
        })

        journal_entry = self.prepare_journal_entry(txn_date, doc_number, memo, line_items)
        return self.create_journal_entry(journal_entry)

    def create_payroll_journal_entry(self, payroll_period):
        period_name = payroll_period.period_name
        doc_number = f"PR-{payroll_period.year}{payroll_period.month:02d}"
        txn_date = payroll_period.end_date
        memo = f"Payroll for {period_name}"

        line_items = []

        salary_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_EXPENSE")
        if not salary_mapping:
            raise Exception("Salary expense account mapping not found")

        line_items.append({
            "description": f"Gross Salary for {period_name}",
            "amount": payroll_period.total_gross_salary,
            "posting_type": "DEBIT",
            "account_id": salary_mapping.quickbooks_account_id,
            "account_name": salary_mapping.quickbooks_account_name
        })

        epf_employer_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "EPF_EMPLOYER")
        if epf_employer_mapping:
            line_items.append({
                "description": f"Employer EPF Contribution for {period_name}",
                "amount": payroll_period.total_epf_employer,
                "posting_type": "DEBIT",
                "account_id": epf_employer_mapping.quickbooks_account_id,
                "account_name": epf_employer_mapping.quickbooks_account_name
            })

        etf_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "ETF_CONTRIBUTION")
        if etf_mapping:
            line_items.append({
                "description": f"ETF Contribution for {period_name}",
                "amount": payroll_period.total_etf_contribution,
                "posting_type": "DEBIT",
                "account_id": etf_mapping.quickbooks_account_id,
                "account_name": etf_mapping.quickbooks_account_name
            })

        epf_employee_mapping = self.get_account_mapping("PAYROLL_DEDUCTION", "EPF_EMPLOYEE")
        if epf_employee_mapping:
            line_items.append({
                "description": f"Employee EPF Contribution for {period_name}",
                "amount": payroll_period.total_epf_employee,
                "posting_type": "CREDIT",
                "account_id": epf_employee_mapping.quickbooks_account_id,
                "account_name": epf_employee_mapping.quickbooks_account_name
            })

        if epf_employer_mapping:
            line_items.append({
                "description": f"Employer EPF Liability for {period_name}",
                "amount": payroll_period.total_epf_employer,
                "posting_type": "CREDIT",
                "account_id": epf_employer_mapping.quickbooks_account_id,
                "account_name": epf_employer_mapping.quickbooks_account_name
            })

        if etf_mapping:
            line_items.append({
                "description": f"ETF Liability for {period_name}",
                "amount": payroll_period.total_etf_contribution,
                "posting_type": "CREDIT",
                "account_id": etf_mapping.quickbooks_account_id,
                "account_name": etf_mapping.quickbooks_account_name
            })

        salary_payable_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_PAYABLE")
        if not salary_payable_mapping:
            raise Exception("Salary payable account mapping not found")

        line_items.append({
            "description": f"Net Salary Payable for {period_name}",
            "amount": payroll_period.total_net_salary,
            "posting_type": "CREDIT",
            "account_id": salary_payable_mapping.quickbooks_account_id,
            "account_name": salary_payable_mapping.quickbooks_account_name
        })

        self.add_department_payroll_entries(payroll_period, line_items)

        return self.prepare_journal_entry(txn_date, doc_number, memo, line_items)

    def add_department_payroll_entries(self, payroll_period, line_items):
        department_summaries = PayrollDepartmentSummary.objects.filter(
            payroll_period=payroll_period,
            is_active=True
        )

        if not department_summaries.exists():
            return

        salary_mapping = self.get_account_mapping("PAYROLL_COMPONENT", "SALARY_EXPENSE")
        if not salary_mapping:
            return

        for dept_summary in department_summaries:
            dept_mapping = self.get_department_mapping(dept_summary.department.id)
            if not dept_mapping:
                continue

            dept_line = {
                "description": f"Gross Salary for {dept_summary.department.name}",
                "amount": dept_summary.total_gross_salary,
                "posting_type": "DEBIT",
                "account_id": salary_mapping.quickbooks_account_id,
                "account_name": salary_mapping.quickbooks_account_name,
                "include_department": True
            }

            if dept_mapping.quickbooks_class_id:
                dept_line["class_id"] = dept_mapping.quickbooks_class_id
                dept_line["class_name"] = dept_mapping.quickbooks_class_name

            line_items.append(dept_line)

    def create_expense_journal_entry(self, expense):
        doc_number = f"EXP-{expense.reference}"
        txn_date = expense.date_incurred
        memo = f"Expense: {expense.description}"

        line_items = []

        try:
            purchase_summary = expense.purchase_summary
            has_summary = True
        except:
            has_summary = False

        expense_mapping = None
        if expense.expense_account:
            expense_mapping = self.get_account_mapping("EXPENSE_ACCOUNT", expense.expense_account)

        if not expense_mapping:
            expense_mapping = self.get_account_mapping("EXPENSE_TYPE", expense.expense_type.id)

        if not expense_mapping:
            expense_mapping = self.get_account_mapping("EXPENSE_CATEGORY", expense.expense_category.id)

        if not expense_mapping:
            raise Exception(f"No account mapping found for expense type {expense.expense_type.name}")

        expense_amount = expense.total_amount
        tax_amount = Decimal("0.00")

        if has_summary and purchase_summary.tax_amount > 0:
            tax_amount = purchase_summary.tax_amount
            expense_amount = purchase_summary.subtotal

        line_items.append({
            "description": expense.description,
            "amount": expense_amount,
            "posting_type": "DEBIT",
            "account_id": expense_mapping.quickbooks_account_id,
            "account_name": expense_mapping.quickbooks_account_name
        })

        if tax_amount > 0:
            tax_mapping = self.get_account_mapping("TAX", "SALES_TAX")
            if tax_mapping:
                line_items.append({
                    "description": f"Tax for {expense.reference}",
                    "amount": tax_amount,
                    "posting_type": "DEBIT",
                    "account_id": tax_mapping.quickbooks_account_id,
                    "account_name": tax_mapping.quickbooks_account_name
                })

        payment_account_mapping = None
        if expense.payment_method:
            payment_account_mapping = self.get_account_mapping("PAYMENT_METHOD", expense.payment_method)

        if not payment_account_mapping:
            payment_account_mapping = self.get_account_mapping("PAYMENT_METHOD", "DEFAULT")

        if not payment_account_mapping:
            raise Exception("No payment account mapping found")

        payment_description = f"Payment for {expense.reference}"
        if has_summary and purchase_summary.vendor_name:
            payment_description += f" to {purchase_summary.vendor_name}"

        if has_summary and purchase_summary.purchase_reference:
            payment_description += f" (Ref: {purchase_summary.purchase_reference})"

        line_items.append({
            "description": payment_description,
            "amount": expense.total_amount,
            "posting_type": "CREDIT",
            "account_id": payment_account_mapping.quickbooks_account_id,
            "account_name": payment_account_mapping.quickbooks_account_name
        })

        department_id = None
        if expense.department:
            department_id = expense.department.id

        if expense.cost_center:
            memo += f" | Cost Center: {expense.cost_center}"

        if expense.tax_category:
            memo += f" | Tax Category: {expense.tax_category}"

        return self.prepare_journal_entry(txn_date, doc_number, memo, line_items, department_id)

    def create_reimbursable_expense(self, expense):
        employee_entity_ref = self.get_employee_entity_ref(expense.employee)

        payment_method = expense.payment_method or "BANK_TRANSFER"
        bank_mapping = self.get_account_mapping("PAYMENT_METHOD", payment_method)
        if not bank_mapping:
            bank_mapping = self.get_account_mapping("PAYMENT_METHOD", "BANK_TRANSFER")
        if not bank_mapping:
            raise Exception("Bank account mapping not found")

        try:
            purchase_summary = expense.purchase_summary
            has_summary = True
        except:
            has_summary = False

        private_note = expense.description
        if expense.notes:
            private_note += f" | {expense.notes}"

        if has_summary and purchase_summary.vendor_name:
            private_note += f" | Vendor: {purchase_summary.vendor_name}"

        purchase_data = {
            "PaymentType": "Cash",
            "AccountRef": {
                "value": bank_mapping.quickbooks_account_id,
                "name": bank_mapping.quickbooks_account_name
            },
            "EntityRef": employee_entity_ref,
            "TotalAmt": self.format_decimal(expense.total_amount),
            "TxnDate": expense.date_incurred.strftime("%Y-%m-%d"),
            "DocNumber": f"REIMB-{expense.reference}",
            "PrivateNote": private_note,
            "Line": []
        }

        if has_summary and purchase_summary.purchase_reference:
            purchase_data["DocNumber"] = f"REIMB-{purchase_summary.purchase_reference}"

        dept_mapping = None
        if expense.department:
            dept_mapping = self.get_department_mapping(expense.department.id)

        purchase_items = PurchaseItem.objects.filter(expense=expense, is_active=True, return_status__in=["NOT_RETURNABLE", "RETURNABLE"])

        if purchase_items.exists():
            for item in purchase_items:
                expense_mapping = None
                if expense.expense_account:
                    expense_mapping = self.get_account_mapping("EXPENSE_ACCOUNT", expense.expense_account)

                if not expense_mapping:
                    expense_mapping = self.get_account_mapping("EXPENSE_TYPE", expense.expense_type.id)

                if not expense_mapping:
                    expense_mapping = self.get_account_mapping("EXPENSE_CATEGORY", expense.expense_category.id)

                if not expense_mapping:
                    raise Exception(f"No account mapping found for expense type {expense.expense_type.name}")

                item_dept_mapping = dept_mapping
                if item.department:
                    item_dept_mapping = self.get_department_mapping(item.department.id) or dept_mapping

                line_item = {
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "Amount": self.format_decimal(item.total_cost),
                    "Description": item.item_description,
                    "AccountBasedExpenseLineDetail": {
                        "AccountRef": {
                            "value": expense_mapping.quickbooks_account_id,
                            "name": expense_mapping.quickbooks_account_name
                        },
                        "BillableStatus": "Billable" if expense.is_reimbursable else "NotBillable",
                        "TaxCodeRef": {
                            "value": "TAX" if expense.is_taxable_benefit else "NON"
                        }
                    }
                }

                if item_dept_mapping:
                    if item_dept_mapping.quickbooks_department_id:
                        line_item["AccountBasedExpenseLineDetail"]["DepartmentRef"] = {
                            "value": item_dept_mapping.quickbooks_department_id,
                            "name": item_dept_mapping.quickbooks_department_name
                        }

                    if item_dept_mapping.quickbooks_class_id:
                        line_item["AccountBasedExpenseLineDetail"]["ClassRef"] = {
                            "value": item_dept_mapping.quickbooks_class_id,
                            "name": item_dept_mapping.quickbooks_class_name
                        }

                purchase_data["Line"].append(line_item)
        else:
            expense_mapping = None
            if expense.expense_account:
                expense_mapping = self.get_account_mapping("EXPENSE_ACCOUNT", expense.expense_account)

            if not expense_mapping:
                expense_mapping = self.get_account_mapping("EXPENSE_TYPE", expense.expense_type.id)

            if not expense_mapping:
                expense_mapping = self.get_account_mapping("EXPENSE_CATEGORY", expense.expense_category.id)

            if not expense_mapping:
                raise Exception(f"No account mapping found for expense type {expense.expense_type.name}")

            line_item = {
                "DetailType": "AccountBasedExpenseLineDetail",
                "Amount": self.format_decimal(expense.total_amount),
                "Description": expense.description,
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {
                        "value": expense_mapping.quickbooks_account_id,
                        "name": expense_mapping.quickbooks_account_name
                    },
                    "BillableStatus": "Billable" if expense.is_reimbursable else "NotBillable",
                    "TaxCodeRef": {
                        "value": "TAX" if expense.is_taxable_benefit else "NON"
                    }
                }
            }

            if dept_mapping:
                if dept_mapping.quickbooks_department_id:
                    line_item["AccountBasedExpenseLineDetail"]["DepartmentRef"] = {
                        "value": dept_mapping.quickbooks_department_id,
                        "name": dept_mapping.quickbooks_department_name
                    }

                if dept_mapping.quickbooks_class_id:
                    line_item["AccountBasedExpenseLineDetail"]["ClassRef"] = {
                        "value": dept_mapping.quickbooks_class_id,
                        "name": dept_mapping.quickbooks_class_name
                    }

            purchase_data["Line"].append(line_item)

        return purchase_data

    def sync_purchase_return(self, expense, returned_items):
        try:
            if not returned_items.exists():
                return None

            doc_number = f"CR-{expense.reference}"
            txn_date = timezone.now().date()
            memo = f"Credit Memo for returned items from {expense.reference}"

            try:
                latest_return = returned_items.latest("return_date")
                if latest_return.return_date:
                    txn_date = latest_return.return_date
            except:
                pass

            total_refund = sum(item.refund_amount for item in returned_items)

            if total_refund <= 0:
                return None

            credit_memo = {
                "DocNumber": doc_number,
                "TxnDate": txn_date.strftime("%Y-%m-%d"),
                "PrivateNote": memo,
                "CustomerRef": self.get_employee_entity_ref(expense.employee),
                "Line": [],
            }

            for item in returned_items:
                expense_mapping = None
                if expense.expense_account:
                    expense_mapping = self.get_account_mapping(
                        "EXPENSE_ACCOUNT", expense.expense_account
                    )

                if not expense_mapping:
                    expense_mapping = self.get_account_mapping(
                        "EXPENSE_TYPE", expense.expense_type.id
                    )

                if not expense_mapping:
                    expense_mapping = self.get_account_mapping(
                        "EXPENSE_CATEGORY", expense.expense_category.id
                    )

                if not expense_mapping:
                    raise Exception(
                        f"No account mapping found for expense type {expense.expense_type.name}"
                    )

                line_item = {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": self.format_decimal(item.refund_amount),
                    "Description": f"Return: {item.item_description} (Qty: {item.return_quantity})",
                    "SalesItemLineDetail": {
                        "ItemRef": {"name": "Returned Item"},
                        "TaxCodeRef": {"value": "NON"},
                    },
                }

                credit_memo["Line"].append(line_item)

            response = self.make_api_request("POST", "creditmemo", data=credit_memo)

            if response and "CreditMemo" in response:
                for item in returned_items:
                    item.notes = f"{item.notes or ''} | QuickBooks Credit Memo: {response['CreditMemo']['Id']}"
                    item.save(update_fields=["notes"])

                return response

            return None

        except Exception as e:
            raise Exception(f"Error creating credit memo for returns: {str(e)}")

    def sync_expense_installment_plan(self, plan):
        try:
            doc_number = f"INST-PLAN-{plan.expense.reference}"
            txn_date = plan.start_date
            memo = f"Installment Plan for {plan.expense.reference}: {plan.installment_amount} x {plan.number_of_installments}"

            journal_entry = {
                "DocNumber": doc_number,
                "TxnDate": txn_date.strftime("%Y-%m-%d"),
                "PrivateNote": memo,
                "Line": [],
            }

            expense_mapping = None
            if plan.expense.expense_account:
                expense_mapping = self.get_account_mapping(
                    "EXPENSE_ACCOUNT", plan.expense.expense_account
                )

            if not expense_mapping:
                expense_mapping = self.get_account_mapping(
                    "EXPENSE_TYPE", plan.expense.expense_type.id
                )

            if not expense_mapping:
                expense_mapping = self.get_account_mapping(
                    "EXPENSE_CATEGORY", plan.expense.expense_category.id
                )

            if not expense_mapping:
                raise Exception(
                    f"No account mapping found for expense type {plan.expense.expense_type.name}"
                )

            installment_receivable_mapping = self.get_account_mapping(
                "PAYROLL_COMPONENT", "ADVANCE_RECEIVABLE"
            )
            if not installment_receivable_mapping:
                raise Exception("Installment receivable account mapping not found")

            journal_entry["Line"].append(
                {
                    "Id": str(uuid.uuid4()),
                    "Description": f"Installment Plan Total for {plan.expense.reference}",
                    "Amount": self.format_decimal(plan.total_amount),
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "DEBIT",
                        "AccountRef": {
                            "value": expense_mapping.quickbooks_account_id,
                            "name": expense_mapping.quickbooks_account_name,
                        },
                        "Entity": self.get_employee_entity_ref(plan.expense.employee),
                    },
                }
            )

            journal_entry["Line"].append(
                {
                    "Id": str(uuid.uuid4()),
                    "Description": f"Installment Plan Receivable for {plan.expense.reference}",
                    "Amount": self.format_decimal(plan.total_amount),
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "CREDIT",
                        "AccountRef": {
                            "value": installment_receivable_mapping.quickbooks_account_id,
                            "name": installment_receivable_mapping.quickbooks_account_name,
                        },
                        "Entity": self.get_employee_entity_ref(plan.expense.employee),
                    },
                }
            )

            department_id = None
            if plan.expense.department:
                department_id = plan.expense.department.id

            response = self.create_journal_entry(journal_entry)

            if response and "JournalEntry" in response:
                return response

            return None

        except Exception as e:
            raise Exception(f"Error creating installment plan: {str(e)}")

    def sync_expense_installment(self, installment):
        try:
            if not installment.is_processed:
                return None

            doc_number = f"INST-{installment.plan.expense.reference}-{installment.installment_number}"
            txn_date = installment.processed_date or installment.scheduled_date
            memo = f"Installment {installment.installment_number} of {installment.plan.number_of_installments} for {installment.plan.expense.reference}"

            journal_entry = {
                "DocNumber": doc_number,
                "TxnDate": txn_date.strftime("%Y-%m-%d"),
                "PrivateNote": memo,
                "Line": [],
            }

            installment_receivable_mapping = self.get_account_mapping(
                "PAYROLL_COMPONENT", "ADVANCE_RECEIVABLE"
            )
            if not installment_receivable_mapping:
                raise Exception("Installment receivable account mapping not found")

            salary_payable_mapping = self.get_account_mapping(
                "PAYROLL_COMPONENT", "SALARY_PAYABLE"
            )
            if not salary_payable_mapping:
                raise Exception("Salary payable account mapping not found")

            journal_entry["Line"].append(
                {
                    "Id": str(uuid.uuid4()),
                    "Description": f"Installment Payment {installment.installment_number} for {installment.plan.expense.reference}",
                    "Amount": self.format_decimal(installment.amount),
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "DEBIT",
                        "AccountRef": {
                            "value": installment_receivable_mapping.quickbooks_account_id,
                            "name": installment_receivable_mapping.quickbooks_account_name,
                        },
                        "Entity": self.get_employee_entity_ref(
                            installment.plan.expense.employee
                        ),
                    },
                }
            )

            journal_entry["Line"].append(
                {
                    "Id": str(uuid.uuid4()),
                    "Description": f"Installment Payment {installment.installment_number} from Salary for {installment.plan.expense.reference}",
                    "Amount": self.format_decimal(installment.amount),
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "CREDIT",
                        "AccountRef": {
                            "value": salary_payable_mapping.quickbooks_account_id,
                            "name": salary_payable_mapping.quickbooks_account_name,
                        },
                        "Entity": self.get_employee_entity_ref(
                            installment.plan.expense.employee
                        ),
                    },
                }
            )

            department_id = None
            if installment.plan.expense.department:
                department_id = installment.plan.expense.department.id

            response = self.create_journal_entry(journal_entry)

            if response and "JournalEntry" in response:
                return response

            return None

        except Exception as e:
            raise Exception(f"Error creating installment payment: {str(e)}")


    def sync_expense(self, expense_id, user=None):
        try:
            expense = Expense.objects.get(id=expense_id)
        except Expense.DoesNotExist:
            raise Exception(f"Expense with ID {expense_id} not found")
        
        sync_log = SyncLog.objects.create(
            sync_type="EXPENSE",
            source_id=str(expense.id),
            source_reference=expense.reference,
            created_by=user
        )
        
        try:
            sync_log.mark_as_started()
            
            expense_sync_status, created = ExpenseSyncStatus.objects.get_or_create(
                expense_id=str(expense.id),
                defaults={
                    "expense_reference": expense.reference,
                    "employee_id": str(expense.employee.id),
                    "employee_name": expense.employee.get_full_name(),
                    "amount": expense.total_amount,
                    "expense_date": expense.date_incurred
                }
            )
            
            if not created:
                expense_sync_status.amount = expense.total_amount
                expense_sync_status.save(update_fields=["amount"])
            
            if expense_sync_status.is_synced:
                sync_log.mark_as_completed(1, 1, 0)
                return True, "Expense already synced", sync_log
            
            try:
                purchase_items = PurchaseItem.objects.filter(expense=expense, is_active=True)
                has_returns = purchase_items.filter(return_status="RETURNED").exists()
                
                if has_returns:
                    self.sync_purchase_return(expense, purchase_items.filter(return_status="RETURNED"))
            except:
                pass
            
            try:
                installment_plans = ExpenseInstallmentPlan.objects.filter(expense=expense, is_active=True)
                if installment_plans.exists():
                    for plan in installment_plans:
                        self.sync_expense_installment_plan(plan)
                
                        installments = ExpenseInstallment.objects.filter(plan=plan, is_active=True)
                        for installment in installments:
                            if installment.is_processed:
                                self.sync_expense_installment(installment)
            except:
                pass
            
            if expense.is_reimbursable:
                qb_data = self.create_reimbursable_expense(expense)
            else:
                qb_data = self.create_expense_journal_entry(expense)
            
            qb_response = None
            if isinstance(qb_data, dict) and qb_data.get("Line"):
                qb_response = self.create_journal_entry(qb_data)
            elif isinstance(qb_data, dict) and qb_data.get("AccountRef"):
                qb_response = self.create_expense(qb_data)
            
            if qb_response:
                entity_type = next(iter(qb_response.keys()))
                qb_id = qb_response[entity_type]["Id"]
                
                expense_sync_status.is_synced = True
                expense_sync_status.last_sync_at = timezone.now()
                expense_sync_status.quickbooks_reference = qb_id
                expense_sync_status.sync_log = sync_log
                expense_sync_status.save()
                
                sync_log.quickbooks_reference = qb_id
                sync_log.mark_as_completed(1, 1, 0)
                
                return True, f"Expense synced successfully. QuickBooks ID: {qb_id}", sync_log
            else:
                sync_log.mark_as_failed("Failed to create expense in QuickBooks")
                return False, "Failed to create expense in QuickBooks", sync_log
                
        except Exception as e:
            error_message = str(e)
            sync_log.mark_as_failed(error_message)
            return False, f"Error syncing expense: {error_message}", sync_log

    def batch_sync_expenses(self, expense_ids=None, status=None, date_range=None, user=None):
        filters = Q(is_active=True)

        if expense_ids:
            filters &= Q(id__in=expense_ids)

        if status:
            filters &= Q(status=status)

        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            filters &= Q(date_incurred__range=[start_date, end_date])

        expenses = Expense.objects.filter(filters)

        if not expenses.exists():
            return False, "No expenses found matching the criteria", None

        sync_log = SyncLog.objects.create(
            sync_type="EXPENSE",
            source_reference=f"Batch sync - {expenses.count()} expenses",
            created_by=user
        )

        try:
            sync_log.mark_as_started()

            success_count = 0
            failed_count = 0
            error_details = {}

            for expense in expenses:
                try:
                    success, message, _ = self.sync_expense(expense.id, user)
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                        error_details[str(expense.id)] = message
                except Exception as e:
                    failed_count += 1
                    error_details[str(expense.id)] = str(e)

            sync_log.mark_as_completed(
                expenses.count(),
                success_count,
                failed_count
            )

            if failed_count > 0:
                sync_log.error_details = error_details
                sync_log.save(update_fields=["error_details"])

            return success_count > 0, f"Synced {success_count} expenses, {failed_count} failed", sync_log

        except Exception as e:
            error_message = str(e)
            sync_log.mark_as_failed(error_message)
            return False, f"Error in batch sync: {error_message}", sync_log

    def batch_sync_payroll(self, period_ids=None, year=None, month=None, user=None):
        filters = Q(is_active=True)

        if period_ids:
            filters &= Q(id__in=period_ids)

        if year:
            filters &= Q(year=year)

        if month:
            filters &= Q(month=month)

        periods = PayrollPeriod.objects.filter(filters)

        if not periods.exists():
            return False, "No payroll periods found matching the criteria", None

        sync_log = SyncLog.objects.create(
            sync_type="PAYROLL",
            source_reference=f"Batch sync - {periods.count()} payroll periods",
            created_by=user
        )

        try:
            sync_log.mark_as_started()

            success_count = 0
            failed_count = 0
            error_details = {}

            for period in periods:
                try:
                    success, message, _ = self.sync_payroll_period(period.id, user)
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                        error_details[str(period.id)] = message
                except Exception as e:
                    failed_count += 1
                    error_details[str(period.id)] = str(e)

            sync_log.mark_as_completed(
                periods.count(),
                success_count,
                failed_count
            )

            if failed_count > 0:
                sync_log.error_details = error_details
                sync_log.save(update_fields=["error_details"])

            return success_count > 0, f"Synced {success_count} payroll periods, {failed_count} failed", sync_log

        except Exception as e:
            error_message = str(e)
            sync_log.mark_as_failed(error_message)
            return False, f"Error in batch sync: {error_message}", sync_log

    def full_sync(self, user=None):
        sync_log = SyncLog.objects.create(
            sync_type="FULL_SYNC",
            source_reference="Full system sync",
            created_by=user
        )

        try:
            sync_log.mark_as_started()

            config = SyncConfiguration.get_active_config()

            total_processed = 0
            total_succeeded = 0
            total_failed = 0
            error_details = {}

            if config.payroll_sync_enabled:
                unsynced_periods = PayrollPeriod.objects.filter(
                    is_active=True,
                    status__in=["COMPLETED", "APPROVED", "PAID"]
                ).exclude(
                    id__in=PayrollSyncStatus.objects.filter(
                        is_synced=True
                    ).values_list("payroll_period_id", flat=True)
                )

                if unsynced_periods.exists():
                    success, message, payroll_log = self.batch_sync_payroll(
                        period_ids=[p.id for p in unsynced_periods],
                        user=user
                    )

                    total_processed += payroll_log.records_processed
                    total_succeeded += payroll_log.records_succeeded
                    total_failed += payroll_log.records_failed

                    if payroll_log.error_details:
                        error_details["payroll"] = payroll_log.error_details

            if config.expense_sync_enabled:
                unsynced_expenses = Expense.objects.filter(
                    is_active=True,
                    status="APPROVED"
                ).exclude(
                    id__in=ExpenseSyncStatus.objects.filter(
                        is_synced=True
                    ).values_list("expense_id", flat=True)
                )

                if unsynced_expenses.exists():
                    success, message, expense_log = self.batch_sync_expenses(
                        expense_ids=[e.id for e in unsynced_expenses],
                        user=user
                    )

                    total_processed += expense_log.records_processed
                    total_succeeded += expense_log.records_succeeded
                    total_failed += expense_log.records_failed

                    if expense_log.error_details:
                        error_details["expenses"] = expense_log.error_details

            sync_log.mark_as_completed(
                total_processed,
                total_succeeded,
                total_failed
            )

            if total_failed > 0:
                sync_log.error_details = error_details
                sync_log.save(update_fields=["error_details"])

            config.last_full_sync = timezone.now()
            config.save(update_fields=["last_full_sync"])

            return total_succeeded > 0, f"Full sync completed: {total_succeeded} succeeded, {total_failed} failed", sync_log

        except Exception as e:
            error_message = str(e)
            sync_log.mark_as_failed(error_message)
            return False, f"Error in full sync: {error_message}", sync_log
