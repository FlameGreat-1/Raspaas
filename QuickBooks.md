After a full sync with our implementation, the following exact data will be in QuickBooks:

1. Journal Entries for Payroll Periods:
   - Entry with doc number format "PR-YYYYMM" containing:
     - DEBIT: Gross Salary (total_gross_salary)
     - DEBIT: Employer EPF Contribution (total_epf_employer)
     - DEBIT: ETF Contribution (total_etf_contribution)
     - CREDIT: Employee EPF Contribution (total_epf_employee)
     - CREDIT: Employer EPF Liability (total_epf_employer)
     - CREDIT: ETF Liability (total_etf_contribution)
     - CREDIT: Net Salary Payable (total_net_salary)
     - Department-specific salary entries if available

2. Journal Entries for Individual Payslips:
   - Entry with doc number format "PS-{reference_number}" containing:
     - DEBIT: Basic Salary (basic_salary)
     - DEBIT: Bonus 1 (bonus_1) if > 0
     - DEBIT: Bonus 2 (bonus_2) if > 0
     - DEBIT: Transport Allowance (transport_allowance) if > 0
     - DEBIT: Telephone Allowance (telephone_allowance) if > 0
     - DEBIT: Fuel Allowance (fuel_allowance) if > 0
     - DEBIT: Meal Allowance (meal_allowance) if > 0
     - DEBIT: Attendance Bonus (attendance_bonus) if > 0
     - DEBIT: Performance Bonus (performance_bonus) if > 0
     - DEBIT: Regular Overtime (regular_overtime) if > 0
     - DEBIT: Weekend Overtime (friday_overtime) if > 0
     - DEBIT: Employer EPF Contribution (employer_epf_contribution) if > 0
     - DEBIT: ETF Contribution (etf_contribution) if > 0
     - CREDIT: Employee EPF Contribution (employee_epf_contribution) if > 0
     - CREDIT: Employer EPF Liability (employer_epf_contribution) if > 0
     - CREDIT: ETF Liability (etf_contribution) if > 0
     - CREDIT: Income Tax (income_tax) if > 0
     - CREDIT: Salary Advance Deduction (advance_deduction) if > 0
     - CREDIT: Net Salary Payable (net_salary)

3. Journal Entries for Salary Advances:
   - Entry with doc number format "ADV-{reference_number}" containing:
     - DEBIT: Salary Advance Receivable (amount)
     - CREDIT: Cash Payment (amount)

4. Journal Entries for Bank Transfers:
   - Entry with doc number format "BT-{batch_reference}" containing:
     - DEBIT: Salary Payable (total_amount)
     - CREDIT: Bank Account (total_amount)

5. Journal Entries or Purchase Transactions for Expenses:
   - For non-reimbursable expenses (doc number "EXP-{reference}"):
     - DEBIT: Expense Account (expense_amount)
     - DEBIT: Tax Account (tax_amount) if tax_amount > 0
     - CREDIT: Payment Method Account (total_amount)
     - Memo includes cost center and tax category if available
   - For reimbursable expenses (doc number "REIMB-{reference}" or "REIMB-{purchase_reference}"):
     - Purchase transaction with employee as vendor
     - Line items for each expense item or single line for total
     - Private note includes vendor name if available

6. Employee Vendor Records:
   - DisplayName: "{employee_name} ({employee_code})"
   - PrintOnCheckName: employee_name
   - Active status matching employee.is_active
   - Email, phone, and address details
   - Bank account information if available
   - Tax identification number if available

7. Credit Memos for Returned Items:
   - Entry with doc number format "CR-{expense.reference}" containing:
     - Line items for each returned item with:
       - Description: "Return: {item_description} (Qty: {return_quantity})"
       - Amount: item.refund_amount
       - Non-taxable status

8. Journal Entries for Installment Plans:
   - Entry with doc number format "INST-PLAN-{expense.reference}" containing:
     - DEBIT: Expense Account (plan.total_amount)
     - CREDIT: Installment Receivable Account (plan.total_amount)
     - Memo includes plan details: "{installment_amount} x {number_of_installments}"

9. Journal Entries for Individual Installments:
   - Entry with doc number format "INST-{expense.reference}-{installment_number}" containing:
     - DEBIT: Installment Receivable Account (installment.amount)
     - CREDIT: Salary Payable Account (installment.amount)
     - Memo includes: "Installment {installment_number} of {plan.number_of_installments}"

All entries include appropriate department references when available, and employee-specific entries include entity references to the employee vendor records.




 EXACT MAPPING NEEDED:

### 1. QuickBooks API Credentials
- **client_id**: Your QuickBooks app's OAuth client ID (looks like: `ABCDEFGhijklMNOPqrst`)
- **client_secret**: Your QuickBooks app's OAuth client secret (looks like: `abcDEFghiJKLmnoPQRstuvwxyz`)
- **refresh_token**: The long-lived refresh token obtained during OAuth flow
- **realm_id**: Your QuickBooks company ID (looks like: `1234567890`)
- **environment**: Select "sandbox" for testing or "production" for live data

### 2. Account Mappings
For each mapping, enter:
- **mapping_type**: Select from dropdown (EXPENSE_CATEGORY, EXPENSE_TYPE, etc.)
- **source_id**: ID of your internal category/type (e.g., "TRAVEL", "MEALS")
- **source_name**: Name of your internal category/type (e.g., "Travel Expenses")
- **quickbooks_account_id**: ID from QuickBooks (e.g., "60")
- **quickbooks_account_name**: Name from QuickBooks (e.g., "Travel Expense")
- **quickbooks_account_type**: Type from QuickBooks (e.g., "Expense")

Essential mappings to create:
- Expense categories (EXPENSE_CATEGORY) → QuickBooks expense accounts
- Tax types (PAYROLL_TAX) → QuickBooks tax liability accounts
- Payment methods → QuickBooks bank/credit card accounts
- "INSTALLMENT_RECEIVABLE" → QuickBooks other current asset account
- "SALARY_PAYABLE" → QuickBooks other current liability account

### 3. Department Mappings
For each department, enter:
- **department**: Select your internal department from dropdown
- **quickbooks_department_id**: Department ID from QuickBooks (e.g., "2")
- **quickbooks_department_name**: Department name from QuickBooks (e.g., "Marketing")
- **quickbooks_class_id**: Class ID from QuickBooks if using classes (e.g., "1")
- **quickbooks_class_name**: Class name from QuickBooks if using classes (e.g., "Corporate")

### 4. Employee Vendor Records
These are created in QuickBooks directly, not in the system. For each employee:
1. Create a vendor in QuickBooks with:
   - **Display Name**: Format as "{employee_name} ({employee_code})"
   - **Print On Check Name**: Employee's full name
   - **Tax ID**: Employee's tax ID number if available
   - **Address**: Employee's address
   - **Email**: Employee's email address
   - **Phone**: Employee's phone number
   - **Payment Method**: Direct Deposit
   - **Account Number**: Employee's bank account if reimbursing electronically

The system will automatically link to these vendor records using the employee name and code during sync.
















To get the QuickBooks API credentials, follow these exact steps:

1. **Create a Developer Account**:
   - Go to `https://developer.intuit.com/`
   - Sign up for a free developer account

2. **Create an App**:
   - Log in to the developer portal
   - Go to "Dashboard" → "Create an app"
   - Select "QuickBooks Online and Payments"
   - Fill in the app details (name, description)

3. **Configure OAuth**:
   - In your app settings, set up the OAuth redirect URI
   - This should point to your application's callback URL
   - Example: `https://your-app-domain.com/accounting/quickbooks/callback/`

4. **Get Development Keys**:
   - From your app's dashboard, find the "Development" section
   - Copy the **client_id** and **client_secret**

5. **Get Refresh Token and Realm ID**:
   - Implement the OAuth flow in your application
   - When a user connects their QuickBooks account, you'll receive:
     - An initial access token
     - A refresh token
     - The realm ID (company ID)

6. **Store the Credentials**:
   - Enter these credentials in your application's QuickBooks settings page
   - Select "sandbox" for testing or "production" for live data

The OAuth flow requires a user to authorize your application to access their QuickBooks data. Your application needs to implement this flow to obtain the refresh token and realm ID.