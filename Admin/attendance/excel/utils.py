import os
import pandas as pd
import numpy as np
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from ..models import Attendance
from ..utils import get_current_date
from io import BytesIO

User = get_user_model()


class ExcelAttendanceImporter:
    def __init__(
        self,
        file_path,
        date_format="DMY_TEXT",
        sheet_name=None,
        update_existing=True,
        user=None,
    ):
        self.file_path = file_path
        self.date_format = date_format
        self.sheet_name = sheet_name
        self.update_existing = update_existing
        self.user = user
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.update_count = 0
        self.error_count = 0
        self.processed_data = []

    def read_excel(self):
        try:
            if self.sheet_name:
                self.df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
            else:
                self.df = pd.read_excel(self.file_path)

            if self.df.empty:
                self.errors.append("Excel file contains no data")
                return False

            self.df = self.df.replace({np.nan: None})
            return True
        except Exception as e:
            self.errors.append(f"Error reading Excel file: {str(e)}")
            return False

    def validate_excel_structure(self):
        required_columns = ["ID", "Date"]
        missing_columns = []

        for col in required_columns:
            if col not in self.df.columns:
                missing_columns.append(col)

        if missing_columns:
            self.errors.append(
                f"Missing required columns: {', '.join(missing_columns)}"
            )
            return False

        time_columns_found = False
        for i in range(1, 7):
            in_col = f"In"
            out_col = f"Out"

            if i > 1:
                in_col = f"{i}/{in_col}"
                out_col = f"{i}/{out_col}"

            if in_col in self.df.columns and out_col in self.df.columns:
                time_columns_found = True
                break

        if not time_columns_found:
            self.errors.append("No valid time column pairs found (In/Out)")
            return False

        return True

    def parse_date(self, date_value):
        if not date_value:
            return None

        if isinstance(date_value, date):
            return date_value

        if isinstance(date_value, datetime):
            return date_value.date()

        if isinstance(date_value, str):
            date_str = date_value.strip()

            if self.date_format == "DMY_TEXT":
                try:
                    return datetime.strptime(date_str, "%d-%b-%y").date()
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%d-%B-%y").date()
                    except ValueError:
                        try:
                            return datetime.strptime(date_str, "%d-%b-%Y").date()
                        except ValueError:
                            try:
                                return datetime.strptime(date_str, "%d-%B-%Y").date()
                            except ValueError:
                                pass

            elif self.date_format == "DMY":
                try:
                    return datetime.strptime(date_str, "%d/%m/%Y").date()
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%d-%m-%Y").date()
                    except ValueError:
                        pass

            elif self.date_format == "MDY":
                try:
                    return datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%m-%d-%Y").date()
                    except ValueError:
                        pass

            elif self.date_format == "YMD":
                try:
                    return datetime.strptime(date_str, "%Y/%m/%d").date()
                except ValueError:
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

        return None

    def parse_time(self, time_value):
        if not time_value:
            return None

        if isinstance(time_value, time):
            return time_value

        if isinstance(time_value, datetime):
            return time_value.time()

        if isinstance(time_value, str):
            time_str = time_value.strip()
            formats = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]

            for fmt in formats:
                try:
                    return datetime.strptime(time_str, fmt).time()
                except ValueError:
                    continue

        if isinstance(time_value, (int, float)):
            try:
                total_seconds = int(time_value * 24 * 60 * 60)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return time(hours, minutes, seconds)
            except (ValueError, OverflowError):
                pass

        return None
    
    def process_data(self):
        if not self.read_excel() or not self.validate_excel_structure():
            return False
            
        for _, row in self.df.iterrows():
            try:
                employee_id = row.get('ID')
                if not employee_id:
                    continue
                    
                employee_id = str(employee_id).strip()
                date_value = self.parse_date(row.get('Date'))
                
                if not date_value:
                    self.warnings.append(f"Invalid date format for employee ID {employee_id}")
                    continue
                    
                if date_value > get_current_date():
                    self.warnings.append(f"Future date {date_value} for employee ID {employee_id} will be skipped")
                    continue
                
                attendance_data = {
                    'employee_id': employee_id,
                    'date': date_value,
                    'division': row.get('Division'),
                    'notes': row.get('Notes', '')
                }
                
                # Process time pairs
                for i in range(1, 7):
                    in_col = f"In"
                    out_col = f"Out"
                    
                    if i > 1:
                        in_col = f"{i}/{in_col}"
                        out_col = f"{i}/{out_col}"
                    
                    if in_col in self.df.columns:
                        check_in = self.parse_time(row.get(in_col))
                        if check_in:
                            attendance_data[f'check_in_{i}'] = check_in
                    
                    if out_col in self.df.columns:
                        check_out = self.parse_time(row.get(out_col))
                        if check_out:
                            attendance_data[f'check_out_{i}'] = check_out
                
                # Add additional data if available
                if 'Total Time' in self.df.columns:
                    total_time_str = row.get('Total Time')
                    if total_time_str:
                        try:
                            hours, minutes, seconds = map(int, str(total_time_str).split(':'))
                            attendance_data['total_time'] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        except (ValueError, AttributeError):
                            pass
                
                if 'Out Time' in self.df.columns:
                    break_time_str = row.get('Out Time')
                    if break_time_str:
                        try:
                            hours, minutes, seconds = map(int, str(break_time_str).split(':'))
                            attendance_data['break_time'] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        except (ValueError, AttributeError):
                            pass
                
                if 'Work Time' in self.df.columns:
                    work_time_str = row.get('Work Time')
                    if work_time_str:
                        try:
                            hours, minutes, seconds = map(int, str(work_time_str).split(':'))
                            attendance_data['work_time'] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        except (ValueError, AttributeError):
                            pass
                
                if 'Over Time' in self.df.columns:
                    overtime_str = row.get('Over Time')
                    if overtime_str:
                        try:
                            hours, minutes, seconds = map(int, str(overtime_str).split(':'))
                            attendance_data['overtime'] = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        except (ValueError, AttributeError):
                            pass
                
                self.processed_data.append(attendance_data)
                
            except Exception as e:
                self.error_count += 1
                self.errors.append(f"Error processing row: {str(e)}")
        
        return len(self.processed_data) > 0
    
    @transaction.atomic
    def import_data(self):
        if not self.processed_data and not self.process_data():
            return False
        
        for data in self.processed_data:
            try:
                employee_id = data.pop('employee_id')
                date_value = data.pop('date')
                division = data.pop('division', None)
                
                # Find employee by ID
                employee = User.objects.filter(employee_code=employee_id).first()
                if not employee:
                    self.warnings.append(f"Employee with ID {employee_id} not found")
                    continue
                
                # Check if attendance record exists
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=date_value,
                    defaults={
                        'is_manual_entry': True,
                        'created_by': self.user
                    }
                )
                
                if not created and not self.update_existing:
                    self.warnings.append(f"Skipping existing record for {employee.get_full_name()} on {date_value}")
                    continue
                
                # Update attendance record with imported data
                for field, value in data.items():
                    if value is not None:
                        setattr(attendance, field, value)
                
                attendance.is_manual_entry = True
                if self.user:
                    attendance._attendance_changed_by = self.user
                    if created:
                        attendance.created_by = self.user
                
                attendance.save()
                
                if created:
                    self.success_count += 1
                else:
                    self.update_count += 1
                    
            except ValidationError as e:
                self.error_count += 1
                self.errors.append(f"Validation error for {employee_id} on {date_value}: {str(e)}")
            except Exception as e:
                self.error_count += 1
                self.errors.append(f"Error importing data: {str(e)}")
        
        return True
    
    def get_results(self):
        return {
            'success_count': self.success_count,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'errors': self.errors,
            'warnings': self.warnings
        }


class ExcelAttendanceValidator:
    @staticmethod
    def validate_file(file):
        if not file:
            return False, ["No file provided"]
            
        ext = os.path.splitext(file.name)[1]
        valid_extensions = ['.xlsx', '.xls']
        if ext.lower() not in valid_extensions:
            return False, ["Invalid file format. Please upload an Excel file (.xlsx, .xls)"]
            
        if file.size > 10 * 1024 * 1024:
            return False, ["File size exceeds 10MB limit"]
            
        return True, []

def generate_attendance_import_template():
    
    current_date = datetime.now().strftime('%d-%b-%y')
    
    data = {
        'No': [1, 2, 3],
        'Division': ['Department A', 'Department B', 'Department C'],
        'ID': ['EMP001', 'EMP002', 'EMP003'],
        'Name': ['Employee One', 'Employee Two', 'Employee Three'],
        'Date': [current_date, current_date, current_date],
        'In': ['08:00:00', '09:00:00', '08:30:00'],
        'Out': ['12:00:00', '13:00:00', '12:30:00'],
        '2/In': ['13:00:00', '14:00:00', '13:30:00'],
        '2/Out': ['17:00:00', '18:00:00', '17:30:00'],
        '3/In': ['', '', ''],
        '3/Out': ['', '', ''],
        '4/In': ['', '', ''],
        '4/Out': ['', '', ''],
        '5/In': ['', '', ''],
        '5/Out': ['', '', ''],
        '6/In': ['', '', ''],
        '6/Out': ['', '', ''],
        'Total Time': ['8:00:00', '8:00:00', '8:00:00'],
        'Out Time': ['1:00:00', '1:00:00', '1:00:00'],
        'Work Time': ['7:00:00', '7:00:00', '7:00:00'],
        'Over Time': ['0:00:00', '0:00:00', '0:00:00']
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Attendance Template', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Attendance Template']
        
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        date_format = workbook.add_format({'num_format': 'dd-mmm-yy'})
        time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 8)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 12)
        
        for row_num in range(1, len(data['No']) + 1):
            worksheet.write_string(row_num, 4, data['Date'][row_num-1], date_format)
        
        time_columns = ['F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U']
        for col in time_columns:
            worksheet.set_column(f'{col}:{col}', 10)
            
        instruction_sheet = workbook.add_worksheet('Instructions')
        instruction_sheet.set_column('A:A', 100)
        instruction_sheet.write('A1', 'Attendance Import Instructions', header_format)
        instruction_sheet.write('A3', '1. Do not modify the column headers or structure of the template.')
        instruction_sheet.write('A4', '2. The "ID" column must contain valid employee IDs from your system.')
        instruction_sheet.write('A5', '3. Date format should be DD-MMM-YY (e.g., 21-Mar-25).')
        instruction_sheet.write('A6', '4. Time format should be HH:MM:SS (e.g., 08:30:00).')
        instruction_sheet.write('A7', '5. Multiple check-ins and check-outs can be recorded using the numbered In/Out columns.')
        instruction_sheet.write('A8', '6. Total Time, Out Time, Work Time, and Over Time should be in HH:MM:SS format.')
        instruction_sheet.write('A9', '7. You can add as many rows as needed for your employees.')
    
    output.seek(0)
    return output
