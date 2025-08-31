from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Avg, F, ExpressionWrapper, fields
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date
from django.conf import settings
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string
        
import json
import csv
import datetime
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
import uuid
import io
import xlsxwriter

from accounts.models import CustomUser, Department, SystemConfiguration
from employees.models import EmployeeProfile, Contract
from .models import (
    Attendance,
    AttendanceLog,
    AttendanceDevice,
    Shift,
    EmployeeShift,
    LeaveRequest,
    LeaveType,
    LeaveBalance,
    Holiday,
    MonthlyAttendanceSummary,
    AttendanceCorrection,
    AttendanceReport,
)
from .utils import (
    TimeCalculator,
    EmployeeDataManager,
    AttendanceCalculator,
    DeviceDataProcessor,
    ValidationHelper,
    AuditHelper,
    CacheManager,
    get_current_date,
    get_current_datetime,
)

User = get_user_model()

class AttendanceView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if "id" in kwargs:
            return self.attendance_detail(request, kwargs["id"])
        elif "employee_id" in kwargs:
            return self.employee_attendance(request, kwargs["employee_id"])
        else:
            return self.attendance_list(request)

    def attendance_list(self, request):
        today = get_current_date()
        date_filter = request.GET.get("date", today.strftime("%Y-%m-%d"))
        department_filter = request.GET.get("department", "")
        status_filter = request.GET.get("status", "")
        search_query = request.GET.get("search", "")

        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            filter_date = today

        attendance_records = Attendance.objects.filter(date=filter_date)

        if department_filter:
            attendance_records = attendance_records.filter(
                employee__department_id=department_filter
            )

        if status_filter:
            attendance_records = attendance_records.filter(status=status_filter)

        if search_query:
            attendance_records = attendance_records.filter(
                Q(employee__first_name__icontains=search_query)
                | Q(employee__last_name__icontains=search_query)
                | Q(employee__employee_code__icontains=search_query)
            )

        paginator = Paginator(
            attendance_records.order_by("employee__employee_code"), 25
        )
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        departments = Department.objects.filter(is_active=True).order_by("name")
        status_choices = Attendance._meta.get_field("status").choices
        employees = User.objects.filter(is_active=True).order_by('first_name')

        context = {
            "page_obj": page_obj,
            "departments": departments,
            "employees": employees,
            "status_choices": status_choices,
            "filter_date": filter_date,
            "department_filter": department_filter,
            "status_filter": status_filter,
            "search_query": search_query,
            "today": today,
        }

        return render(request, "attendance/attendance_list.html", context)

    def attendance_detail(self, request, attendance_id):
        attendance = get_object_or_404(Attendance, id=attendance_id)

        attendance_logs = AttendanceLog.objects.filter(
            employee=attendance.employee, timestamp__date=attendance.date
        ).order_by("timestamp")

        corrections = AttendanceCorrection.objects.filter(
            attendance=attendance
        ).order_by("-requested_at")

        context = {
            "attendance": attendance,
            "attendance_logs": attendance_logs,
            "corrections": corrections,
        }

        return render(request, "attendance/attendance_detail.html", context)

    def employee_attendance(self, request, employee_id):
        employee = get_object_or_404(User, id=employee_id)

        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")
        status_filter = request.GET.get("status", "")

        today = get_current_date()
        if not start_date:
            start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = today.strftime("%Y-%m-%d")

        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            start_date_obj = today - timedelta(days=30)
            end_date_obj = today

        attendance_records = Attendance.objects.filter(
            employee=employee, date__range=[start_date_obj, end_date_obj]
        )

        if status_filter:
            attendance_records = attendance_records.filter(status=status_filter)

        attendance_records = attendance_records.order_by("-date")

        status_choices = Attendance._meta.get_field("status").choices

        context = {
            "employee": employee,
            "attendance_records": attendance_records,
            "start_date": start_date,
            "end_date": end_date,
            "status_filter": status_filter,
            "status_choices": status_choices,
        }

        return render(request, "attendance/employee_attendance.html", context)

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "create":
            return self.create_attendance(request)
        elif request.POST.get("action") == "update":
            return self.update_attendance(request)
        elif request.POST.get("action") == "bulk_update":
            return self.bulk_update_attendance(request)
        else:
            messages.error(request, "Invalid action")
            return redirect("attendance:attendance_list")

    def create_attendance(self, request):
        employee_id = request.POST.get("employee")
        date_str = request.POST.get("date")
        
        try:
            attendance_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            employee = User.objects.get(id=employee_id)

            if attendance_date > get_current_date():
                messages.error(request, "Cannot create attendance for future dates")
                return redirect(f"/attendance/?date={date_str}")

            if Attendance.objects.filter(
                employee=employee, date=attendance_date
            ).exists():
                messages.error(
                    request,
                    f"Attendance record already exists for {employee.get_full_name()} on {attendance_date}",
                )
                return redirect(f"/attendance/?date={date_str}")

            attendance = Attendance(
                employee=employee,
                date=attendance_date,
                is_manual_entry=True,
                created_by=request.user,
            )

            for i in range(1, 7):
                in_time = request.POST.get(f"check_in_{i}")
                out_time = request.POST.get(f"check_out_{i}")

                if in_time:
                    try:
                        in_time_obj = datetime.strptime(in_time, "%H:%M:%S").time()
                    except ValueError:
                        in_time_obj = datetime.strptime(in_time, "%H:%M").time()
                    setattr(attendance, f"check_in_{i}", in_time_obj)
                    
                if out_time:
                    try:
                        out_time_obj = datetime.strptime(out_time, "%H:%M:%S").time()
                    except ValueError:
                        out_time_obj = datetime.strptime(out_time, "%H:%M").time()
                    setattr(attendance, f"check_out_{i}", out_time_obj)

            attendance.notes = request.POST.get("notes", "")
            attendance.save()

            messages.success(
                request,
                f"Attendance record created for {employee.get_full_name()} on {attendance_date}",
            )
            return redirect("attendance:attendance_detail", id=attendance.id)

        except User.DoesNotExist:
            messages.error(request, "Employee not found")
        except ValueError as e:
            messages.error(request, f"Invalid format: {str(e)}")
        except ValidationError as e:
            messages.error(request, f"Validation error: {str(e)}")

        return redirect("attendance:attendance_list")
    
    def update_attendance(self, request):
        attendance_id = request.POST.get('attendance_id')

        try:
            attendance = Attendance.objects.get(id=attendance_id)

            for i in range(1, 7):
                in_time = request.POST.get(f'check_in_{i}')
                out_time = request.POST.get(f'check_out_{i}')

                if in_time:
                    setattr(attendance, f'check_in_{i}', in_time)
                else:
                    setattr(attendance, f'check_in_{i}', None)

                if out_time:
                    setattr(attendance, f'check_out_{i}', out_time)
                else:
                    setattr(attendance, f'check_out_{i}', None)

            attendance.notes = request.POST.get('notes', '')
            attendance.is_manual_entry = True
            attendance.save()

            messages.success(request, f'Attendance record updated for {attendance.employee.get_full_name()} on {attendance.date}')
            return redirect('attendance:attendance_detail', id=attendance.id)

        except Attendance.DoesNotExist:
            messages.error(request, 'Attendance record not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')

        return redirect('attendance:attendance_list')

    def bulk_update_attendance(self, request):
        try:
            data = json.loads(request.POST.get('attendance_data', '[]'))
            updated_count = 0

            for record in data:
                attendance_id = record.get('id')
                if not attendance_id:
                    continue

                try:
                    attendance = Attendance.objects.get(id=attendance_id)

                    for i in range(1, 7):
                        in_key = f'check_in_{i}'
                        out_key = f'check_out_{i}'

                        if in_key in record:
                            setattr(attendance, in_key, record[in_key] or None)

                        if out_key in record:
                            setattr(attendance, out_key, record[out_key] or None)

                    if 'notes' in record:
                        attendance.notes = record['notes']

                    attendance.is_manual_entry = True
                    attendance.save()
                    updated_count += 1

                except Attendance.DoesNotExist:
                    continue
                except ValidationError:
                    continue

            messages.success(request, f'Successfully updated {updated_count} attendance records')

        except json.JSONDecodeError:
            messages.error(request, 'Invalid data format')

        return redirect('attendance:attendance_list')


class Logs(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.log_detail(request, kwargs['id'])
        else:
            return self.log_list(request)

    def log_list(self, request):
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        device_filter = request.GET.get('device', '')
        status_filter = request.GET.get('status', '')
        search_query = request.GET.get('search', '')
        
        today = get_current_date()
        if not start_date:
            start_date = today.strftime('%Y-%m-%d')
        if not end_date:
            end_date = today.strftime('%Y-%m-%d')
        
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            start_date_obj = today
            end_date_obj = today
        
        logs = AttendanceLog.objects.filter(
            timestamp__date__range=[start_date_obj, end_date_obj]
        )
        
        if device_filter:
            logs = logs.filter(device_id=device_filter)
        
        if status_filter:
            logs = logs.filter(processing_status=status_filter)
        
        if search_query:
            logs = logs.filter(
                Q(employee_code__icontains=search_query) |
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query)
            )
        
        logs = logs.order_by('-timestamp')
        
        paginator = Paginator(logs, 50)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        devices = AttendanceDevice.objects.filter(is_active=True).order_by('device_name')
        status_choices = AttendanceLog._meta.get_field('processing_status').choices
        
        context = {
            'page_obj': page_obj,
            'devices': devices,
            'status_choices': status_choices,
            'start_date': start_date,
            'end_date': end_date,
            'device_filter': device_filter,
            'status_filter': status_filter,
            'search_query': search_query,
        }
        
        return render(request, 'attendance/logs_list.html', context)

    def log_detail(self, request, log_id):
        log = get_object_or_404(AttendanceLog, id=log_id)
        
        context = {
            'log': log,
            'raw_data': json.dumps(log.raw_data, indent=2),
        }
        
        return render(request, 'attendance/log_detail.html', context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'process':
            return self.process_logs(request)
        elif request.POST.get('action') == 'mark_processed':
            return self.mark_logs_processed(request)
        elif request.POST.get('action') == 'mark_error':
            return self.mark_logs_error(request)
        else:
            messages.error(request, 'Invalid action')
            return redirect('attendance:logs_list')
        
    def process_logs(self, request):
        log_ids = request.POST.getlist('log_ids')
        
        if not log_ids:
            messages.error(request, 'No logs selected')
            return redirect('attendance:logs_list')
        
        logs = AttendanceLog.objects.filter(id__in=log_ids, processing_status='PENDING')
        
        grouped_logs = {}
        for log in logs:
            key = f"{log.employee_code}_{log.timestamp.date()}"
            if key not in grouped_logs:
                grouped_logs[key] = []
            grouped_logs[key].append(log)
        
        processed_count = 0
        error_count = 0
        
        for key, employee_logs in grouped_logs.items():
            try:
                employee_code, log_date = key.split('_')
                employee = EmployeeDataManager.get_employee_by_code(employee_code)
                
                if not employee:
                    for log in employee_logs:
                        log.mark_as_error('Employee not found')
                    error_count += len(employee_logs)
                    continue
                
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=datetime.strptime(log_date, '%Y-%m-%d').date(),
                    defaults={'created_by': request.user}
                )
                
                time_pairs = DeviceDataProcessor.create_attendance_pairs(employee_logs)
                attendance.set_time_pairs(time_pairs)
                attendance.device = employee_logs[0].device
                attendance.is_manual_entry = False
                attendance.save()
                
                for log in employee_logs:
                    log.mark_as_processed()
                
                processed_count += len(employee_logs)
                
            except Exception as e:
                for log in employee_logs:
                    log.mark_as_error(str(e))
                error_count += len(employee_logs)
        
        if processed_count > 0:
            messages.success(request, f'Successfully processed {processed_count} logs')
        
        if error_count > 0:
            messages.warning(request, f'Failed to process {error_count} logs')
        
        return redirect('attendance:logs_list')

    def mark_logs_processed(self, request):
        log_ids = request.POST.getlist('log_ids')
        
        if not log_ids:
            messages.error(request, 'No logs selected')
            return redirect('attendance:logs_list')
        
        logs = AttendanceLog.objects.filter(id__in=log_ids)
        
        for log in logs:
            log.mark_as_processed()
        
        messages.success(request, f'Marked {logs.count()} logs as processed')
        return redirect('attendance:logs_list')

    def mark_logs_error(self, request):
        log_ids = request.POST.getlist('log_ids')
        error_message = request.POST.get('error_message', 'Marked as error manually')
        
        if not log_ids:
            messages.error(request, 'No logs selected')
            return redirect('attendance:logs_list')
        
        logs = AttendanceLog.objects.filter(id__in=log_ids)
        
        for log in logs:
            log.mark_as_error(error_message)
        
        messages.success(request, f'Marked {logs.count()} logs as error')
        return redirect('attendance:logs_list')


class Dashboard(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'report_id' in kwargs:
            return self.report_detail(request, kwargs['report_id'])
        elif 'summary_id' in kwargs:
            return self.summary_detail(request, kwargs['summary_id'])
        elif request.path.endswith('/reports/'):
            return self.reports_list(request)
        elif request.path.endswith('/summaries/'):
            return self.summaries_list(request)
        else:
            return self.dashboard_home(request)

    def dashboard_home(self, request):
        today = get_current_date()

        attendance_stats = self.get_attendance_stats(today)
        department_stats = self.get_department_stats(today)
        recent_leaves = LeaveRequest.objects.filter(
            status__in=['PENDING', 'APPROVED'],
            start_date__gte=today
        ).order_by('start_date')[:5]

        monthly_data = self.get_monthly_attendance_data(today.year, today.month)

        context = {
            'today': today,
            'attendance_stats': attendance_stats,
            'department_stats': department_stats,
            'recent_leaves': recent_leaves,
            'monthly_data': monthly_data,
        }

        return render(request, 'attendance/dashboard.html', context)

    def get_attendance_stats(self, date):
        attendance_records = Attendance.objects.filter(date=date)

        total_employees = User.objects.filter(is_active=True).count()
        present_count = attendance_records.filter(status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']).count()
        absent_count = attendance_records.filter(status='ABSENT').count()
        late_count = attendance_records.filter(status='LATE').count()
        leave_count = attendance_records.filter(status='LEAVE').count()

        if total_employees > 0:
            attendance_percentage = (present_count / total_employees) * 100
        else:
            attendance_percentage = 0

        work_hours_avg = attendance_records.exclude(
            status__in=['ABSENT', 'LEAVE', 'HOLIDAY']
        ).aggregate(
            avg_hours=Avg(
                ExpressionWrapper(
                    F('work_time'),
                    output_field=fields.DurationField()
                )
            )
        )['avg_hours'] or timedelta(0)

        avg_hours_decimal = Decimal(str(work_hours_avg.total_seconds() / 3600))

        return {
            'total_employees': total_employees,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'leave_count': leave_count,
            'attendance_percentage': round(attendance_percentage, 2),
            'avg_work_hours': round(avg_hours_decimal, 2),
        }

    def get_department_stats(self, date):
        departments = Department.objects.filter(is_active=True)

        stats = []
        for dept in departments:
            employees = User.objects.filter(department=dept, is_active=True)
            employee_count = employees.count()

            if employee_count == 0:
                continue

            attendance_records = Attendance.objects.filter(
                employee__in=employees,
                date=date
            )

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            if employee_count > 0:
                attendance_percentage = (present_count / employee_count) * 100
            else:
                attendance_percentage = 0

            stats.append({
                'department': dept,
                'employee_count': employee_count,
                'present_count': present_count,
                'absent_count': absent_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
            })

        return stats

    def get_monthly_attendance_data(self, year, month):
        start_date = date(year, month, 1)

        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        daily_stats = []
        current_date = start_date

        while current_date <= end_date:
            if current_date <= get_current_date():
                attendance_records = Attendance.objects.filter(date=current_date)

                total_employees = User.objects.filter(
                    is_active=True,
                    date_joined__date__lte=current_date
                ).count()

                present_count = attendance_records.filter(
                    status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
                ).count()

                absent_count = attendance_records.filter(status='ABSENT').count()
                leave_count = attendance_records.filter(status='LEAVE').count()

                if total_employees > 0:
                    attendance_percentage = (present_count / total_employees) * 100
                else:
                    attendance_percentage = 0

                daily_stats.append({
                    'date': current_date,
                    'day': current_date.strftime('%d'),
                    'weekday': current_date.strftime('%a'),
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'leave_count': leave_count,
                    'attendance_percentage': round(attendance_percentage, 2),
                })

            current_date += timedelta(days=1)

        return daily_stats

    def reports_list(self, request):
        reports = AttendanceReport.objects.all().order_by('-generated_at')

        paginator = Paginator(reports, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'report_types': AttendanceReport.REPORT_TYPES,
        }

        return render(request, 'attendance/reports_list.html', context)

    def report_detail(self, request, report_id):
        report = get_object_or_404(AttendanceReport, id=report_id)

        context = {
            'report': report,
        }

        return render(request, 'attendance/report_detail.html', context)

    def summaries_list(self, request):
        year = request.GET.get('year', get_current_date().year)
        month = request.GET.get('month', get_current_date().month)
        department_filter = request.GET.get('department', '')
        search_query = request.GET.get('search', '')

        try:
            year = int(year)
            month = int(month)
        except ValueError:
            year = get_current_date().year
            month = get_current_date().month

        summaries = MonthlyAttendanceSummary.objects.filter(year=year, month=month)

        if department_filter:
            summaries = summaries.filter(employee__department_id=department_filter)

        if search_query:
            summaries = summaries.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__employee_code__icontains=search_query)
            )

        summaries = summaries.order_by('employee__employee_code')

        paginator = Paginator(summaries, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        departments = Department.objects.filter(is_active=True).order_by('name')

        context = {
            'page_obj': page_obj,
            'departments': departments,
            'year': year,
            'month': month,
            'department_filter': department_filter,
            'search_query': search_query,
            'months': range(1, 13),
            'years': range(get_current_date().year - 2, get_current_date().year + 1),
        }

        return render(request, 'attendance/summaries_list.html', context)

    def summary_detail(self, request, summary_id):
        summary = get_object_or_404(MonthlyAttendanceSummary, id=summary_id)

        start_date = date(summary.year, summary.month, 1)
        if summary.month == 12:
            end_date = date(summary.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(summary.year, summary.month + 1, 1) - timedelta(days=1)

        attendance_records = Attendance.objects.filter(
            employee=summary.employee,
            date__range=[start_date, end_date]
        ).order_by('date')

        context = {
            'summary': summary,
            'attendance_records': attendance_records,
            'start_date': start_date,
            'end_date': end_date,
        }

        return render(request, 'attendance/summary_detail.html', context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'generate_report':
            return self.generate_report(request)
        elif request.POST.get('action') == 'generate_summaries':
            return self.generate_summaries(request)
        elif request.POST.get('action') == 'download_report':
            return self.download_report(request)
        else:
            messages.error(request, 'Invalid action')
            return redirect('attendance:dashboard')

    def generate_report(self, request):
        report_type = request.POST.get('report_type')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        name = request.POST.get('name', f'Attendance Report - {get_current_date()}')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            if end_date < start_date:
                messages.error(request, 'End date cannot be before start date')
                return redirect('attendance:reports')

            report = AttendanceReport(
                name=name,
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                generated_by=request.user
            )

            if report_type in ['EMPLOYEE', 'CUSTOM']:
                employee_ids = request.POST.getlist('employees')
                if not employee_ids:
                    messages.error(request, 'Please select at least one employee')
                    return redirect('attendance:reports')

                report.save()
                report.employees.set(employee_ids)

            elif report_type == 'DEPARTMENT':
                department_ids = request.POST.getlist('departments')
                if not department_ids:
                    messages.error(request, 'Please select at least one department')
                    return redirect('attendance:reports')

                report.save()
                report.departments.set(department_ids)

            else:
                report.save()

            filters = {}
            for key, value in request.POST.items():
                if key.startswith('filter_') and value:
                    filters[key[7:]] = value

            if filters:
                report.filters = filters
                report.save(update_fields=['filters'])

            self.process_report(report)

            messages.success(request, f'Report "{name}" generated successfully')
            return redirect('attendance:report_detail', report_id=report.id)

        except ValueError:
            messages.error(request, 'Invalid date format')
        except Exception as e:
            messages.error(request, f'Error generating report: {str(e)}')

        return redirect('attendance:reports')

    def process_report(self, report):
        if report.report_type == 'DAILY':
            self.process_daily_report(report)
        elif report.report_type == 'WEEKLY':
            self.process_weekly_report(report)
        elif report.report_type == 'MONTHLY':
            self.process_monthly_report(report)
        elif report.report_type == 'EMPLOYEE':
            self.process_employee_report(report)
        elif report.report_type == 'DEPARTMENT':
            self.process_department_report(report)
        elif report.report_type == 'CUSTOM':
            self.process_custom_report(report)

        report.status = 'COMPLETED'
        report.completed_at = get_current_datetime()
        report.save(update_fields=['status', 'completed_at'])

    def process_daily_report(self, report):
        date_range = (report.end_date - report.start_date).days + 1

        daily_data = []
        for i in range(date_range):
            current_date = report.start_date + timedelta(days=i)

            attendance_records = Attendance.objects.filter(date=current_date)

            total_employees = User.objects.filter(
                is_active=True,
                date_joined__date__lte=current_date
            ).count()

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            late_count = attendance_records.filter(status='LATE').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            if total_employees > 0:
                attendance_percentage = (present_count / total_employees) * 100
            else:
                attendance_percentage = 0

            daily_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'weekday': current_date.strftime('%A'),
                'total_employees': total_employees,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
            })

        report.report_data = {
            'daily_data': daily_data,
            'summary': {
                'total_days': date_range,
                'average_attendance': round(
                    sum(day['attendance_percentage'] for day in daily_data) / date_range, 2
                ) if date_range > 0 else 0,
            }
        }
        report.save(update_fields=['report_data'])

    def process_weekly_report(self, report):
        date_range = (report.end_date - report.start_date).days + 1
        weeks = (date_range + 6) // 7

        weekly_data = []
        for week in range(weeks):
            week_start = report.start_date + timedelta(days=week * 7)
            week_end = min(week_start + timedelta(days=6), report.end_date)

            attendance_records = Attendance.objects.filter(
                date__range=[week_start, week_end]
            )

            total_employees = User.objects.filter(
                is_active=True,
                date_joined__date__lte=week_end
            ).count()

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            late_count = attendance_records.filter(status='LATE').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            working_days = (week_end - week_start).days + 1

            if total_employees > 0 and working_days > 0:
                attendance_percentage = (present_count / (total_employees * working_days)) * 100
            else:
                attendance_percentage = 0

            weekly_data.append({
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'working_days': working_days,
                'total_employees': total_employees,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
            })

        report.report_data = {
            'weekly_data': weekly_data,
            'summary': {
                'total_weeks': weeks,
                'average_attendance': round(
                    sum(week['attendance_percentage'] for week in weekly_data) / weeks, 2
                ) if weeks > 0 else 0,
            }
        }
        report.save(update_fields=['report_data'])

    def process_monthly_report(self, report):
        start_month = report.start_date.month
        start_year = report.start_date.year
        end_month = report.end_date.month
        end_year = report.end_date.year

        total_months = (end_year - start_year) * 12 + (end_month - start_month) + 1

        monthly_data = []
        for i in range(total_months):
            year = start_year + (start_month + i - 1) // 12
            month = (start_month + i - 1) % 12 + 1

            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            month_end = min(month_end, report.end_date)

            if month_start > report.end_date or month_end < report.start_date:
                continue

            if month_start < report.start_date:
                month_start = report.start_date

            attendance_records = Attendance.objects.filter(
                date__range=[month_start, month_end]
            )

            total_employees = User.objects.filter(
                is_active=True,
                date_joined__date__lte=month_end
            ).count()

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            late_count = attendance_records.filter(status='LATE').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            working_days = (month_end - month_start).days + 1

            if total_employees > 0 and working_days > 0:
                attendance_percentage = (present_count / (total_employees * working_days)) * 100
            else:
                attendance_percentage = 0

            monthly_data.append({
                'year': year,
                'month': month,
                'month_name': month_start.strftime('%B'),
                'working_days': working_days,
                'total_employees': total_employees,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
            })

        report.report_data = {
            'monthly_data': monthly_data,
            'summary': {
                'total_months': total_months,
                'average_attendance': round(
                    sum(month['attendance_percentage'] for month in monthly_data) / len(monthly_data), 2
                ) if monthly_data else 0,
            }
        }
        report.save(update_fields=['report_data'])

    def process_employee_report(self, report):
        employees = report.employees.all()

        employee_data = []
        for employee in employees:
            attendance_records = Attendance.objects.filter(
                employee=employee,
                date__range=[report.start_date, report.end_date]
            )

            total_days = (report.end_date - report.start_date).days + 1

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            late_count = attendance_records.filter(status='LATE').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            if total_days > 0:
                attendance_percentage = (present_count / total_days) * 100
            else:
                attendance_percentage = 0

            total_work_time = attendance_records.aggregate(
                total=Sum('work_time')
            )['total'] or timedelta(0)

            total_overtime = attendance_records.aggregate(
                total=Sum('overtime')
            )['total'] or timedelta(0)

            employee_data.append({
                'employee_id': str(employee.id),
                'employee_code': employee.employee_code,
                'employee_name': employee.get_full_name(),
                'department': employee.department.name if employee.department else '',
                'total_days': total_days,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
                'total_work_hours': round(total_work_time.total_seconds() / 3600, 2),
                'total_overtime_hours': round(total_overtime.total_seconds() / 3600, 2),
            })

        report.report_data = {
            'employee_data': employee_data,
            'summary': {
                'total_employees': len(employee_data),
                'average_attendance': round(
                    sum(emp['attendance_percentage'] for emp in employee_data) / len(employee_data), 2
                ) if employee_data else 0,
            }
        }
        report.save(update_fields=['report_data'])

    def process_department_report(self, report):
        departments = report.departments.all()

        department_data = []
        for department in departments:
            employees = User.objects.filter(
                department=department,
                is_active=True
            )

            attendance_records = Attendance.objects.filter(
                employee__in=employees,
                date__range=[report.start_date, report.end_date]
            )

            total_days = (report.end_date - report.start_date).days + 1
            employee_count = employees.count()

            present_count = attendance_records.filter(
                status__in=['PRESENT', 'LATE', 'EARLY_DEPARTURE']
            ).count()

            absent_count = attendance_records.filter(status='ABSENT').count()
            late_count = attendance_records.filter(status='LATE').count()
            leave_count = attendance_records.filter(status='LEAVE').count()

            if employee_count > 0 and total_days > 0:
                attendance_percentage = (present_count / (employee_count * total_days)) * 100
            else:
                attendance_percentage = 0

            total_work_time = attendance_records.aggregate(
                total=Sum('work_time')
            )['total'] or timedelta(0)

            total_overtime = attendance_records.aggregate(
                total=Sum('overtime')
            )['total'] or timedelta(0)

            department_data.append({
                'department_id': department.id,
                'department_name': department.name,
                'employee_count': employee_count,
                'total_days': total_days,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'leave_count': leave_count,
                'attendance_percentage': round(attendance_percentage, 2),
                'total_work_hours': round(total_work_time.total_seconds() / 3600, 2),
                'total_overtime_hours': round(total_overtime.total_seconds() / 3600, 2),
            })

        report.report_data = {
            'department_data': department_data,
            'summary': {
                'total_departments': len(department_data),
                'average_attendance': round(
                    sum(dept['attendance_percentage'] for dept in department_data) / len(department_data), 2
                ) if department_data else 0,
            }
        }
        report.save(update_fields=['report_data'])

    def process_custom_report(self, report):
        employees = report.employees.all()
        date_range = (report.end_date - report.start_date).days + 1

        attendance_data = []
        for employee in employees:
            employee_data = {
                'employee_id': str(employee.id),
                'employee_code': employee.employee_code,
                'employee_name': employee.get_full_name(),
                'department': employee.department.name if employee.department else '',
                'attendance': []
            }

            for i in range(date_range):
                current_date = report.start_date + timedelta(days=i)

                try:
                    attendance = Attendance.objects.get(
                        employee=employee,
                        date=current_date
                    )

                    attendance_info = {
                        'date': current_date.strftime('%Y-%m-%d'),
                        'weekday': current_date.strftime('%A'),
                        'status': attendance.status,
                        'first_in': attendance.first_in_time.strftime('%H:%M:%S') if attendance.first_in_time else None,
                        'last_out': attendance.last_out_time.strftime('%H:%M:%S') if attendance.last_out_time else None,
                        'work_hours': round(attendance.work_time.total_seconds() / 3600, 2),
                        'overtime_hours': round(attendance.overtime.total_seconds() / 3600, 2),
                        'late_minutes': attendance.late_minutes,
                        'early_departure_minutes': attendance.early_departure_minutes,
                    }

                except Attendance.DoesNotExist:
                    attendance_info = {
                        'date': current_date.strftime('%Y-%m-%d'),
                        'weekday': current_date.strftime('%A'),
                        'status': 'NO_RECORD',
                        'first_in': None,
                        'last_out': None,
                        'work_hours': 0,
                        'overtime_hours': 0,
                        'late_minutes': 0,
                        'early_departure_minutes': 0,
                    }

                employee_data['attendance'].append(attendance_info)

            attendance_data.append(employee_data)

        report.report_data = {
            'attendance_data': attendance_data,
            'date_range': {
                'start_date': report.start_date.strftime('%Y-%m-%d'),
                'end_date': report.end_date.strftime('%Y-%m-%d'),
                'total_days': date_range,
            }
        }
        report.save(update_fields=['report_data'])

    def generate_summaries(self, request):

        year_str = request.POST.get('year', str(get_current_date().year))
        year = int(year_str.replace(',', ''))

        month = int(request.POST.get('month', get_current_date().month))

        employees = User.objects.filter(is_active=True)

        department_id = request.POST.get('department')
        if department_id:
            employees = employees.filter(department_id=department_id)

        generated_count = 0
        for employee in employees:
            try:
                MonthlyAttendanceSummary.generate_for_employee_month(
                    employee, year, month, generated_by=request.user
                )
                generated_count += 1
            except Exception as e:
                continue

        messages.success(request, f'Generated {generated_count} monthly summaries for {month}/{year}')
        return redirect('attendance:summaries')

    def download_report(self, request):
        report_id = request.POST.get('report_id')
        format_type = request.POST.get('format', 'xlsx')

        report = get_object_or_404(AttendanceReport, id=report_id)

        if format_type == 'xlsx':
            return self.download_report_xlsx(report)
        elif format_type == 'csv':
            return self.download_report_csv(report)
        else:
            messages.error(request, 'Invalid format type')
            return redirect('attendance:report_detail', report_id=report.id)

    def download_report_xlsx(self, report):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F0F0F0',
            'border': 1
        })

        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
        percent_format = workbook.add_format({'num_format': '0.00%'})

        if report.report_type == 'DAILY':
            worksheet = workbook.add_worksheet('Daily Report')

            headers = [
                'Date', 'Weekday', 'Total Employees', 'Present', 'Absent',
                'Late', 'On Leave', 'Attendance %'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            for row, day_data in enumerate(report.report_data.get('daily_data', []), 1):
                worksheet.write(row, 0, day_data['date'])
                worksheet.write(row, 1, day_data['weekday'])
                worksheet.write(row, 2, day_data['total_employees'])
                worksheet.write(row, 3, day_data['present_count'])
                worksheet.write(row, 4, day_data['absent_count'])
                worksheet.write(row, 5, day_data['late_count'])
                worksheet.write(row, 6, day_data['leave_count'])
                worksheet.write(row, 7, day_data['attendance_percentage'] / 100, percent_format)

        elif report.report_type == 'WEEKLY':
            worksheet = workbook.add_worksheet('Weekly Report')

            headers = [
                'Week Start', 'Week End', 'Working Days', 'Total Employees',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            for row, week_data in enumerate(report.report_data.get('weekly_data', []), 1):
                worksheet.write(row, 0, week_data['week_start'])
                worksheet.write(row, 1, week_data['week_end'])
                worksheet.write(row, 2, week_data['working_days'])
                worksheet.write(row, 3, week_data['total_employees'])
                worksheet.write(row, 4, week_data['present_count'])
                worksheet.write(row, 5, week_data['absent_count'])
                worksheet.write(row, 6, week_data['late_count'])
                worksheet.write(row, 7, week_data['leave_count'])
                worksheet.write(row, 8, week_data['attendance_percentage'] / 100, percent_format)

        elif report.report_type == 'MONTHLY':
            worksheet = workbook.add_worksheet('Monthly Report')

            headers = [
                'Year', 'Month', 'Working Days', 'Total Employees',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            for row, month_data in enumerate(report.report_data.get('monthly_data', []), 1):
                worksheet.write(row, 0, month_data['year'])
                worksheet.write(row, 1, month_data['month_name'])
                worksheet.write(row, 2, month_data['working_days'])
                worksheet.write(row, 3, month_data['total_employees'])
                worksheet.write(row, 4, month_data['present_count'])
                worksheet.write(row, 5, month_data['absent_count'])
                worksheet.write(row, 6, month_data['late_count'])
                worksheet.write(row, 7, month_data['leave_count'])
                worksheet.write(row, 8, month_data['attendance_percentage'] / 100, percent_format)

        elif report.report_type == 'EMPLOYEE':
            worksheet = workbook.add_worksheet('Employee Report')

            headers = [
                'Employee Code', 'Employee Name', 'Department', 'Total Days',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %',
                'Total Work Hours', 'Total Overtime Hours'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            for row, emp_data in enumerate(report.report_data.get('employee_data', []), 1):
                worksheet.write(row, 0, emp_data['employee_code'])
                worksheet.write(row, 1, emp_data['employee_name'])
                worksheet.write(row, 2, emp_data['department'])
                worksheet.write(row, 3, emp_data['total_days'])
                worksheet.write(row, 4, emp_data['present_count'])
                worksheet.write(row, 5, emp_data['absent_count'])
                worksheet.write(row, 6, emp_data['late_count'])
                worksheet.write(row, 7, emp_data['leave_count'])
                worksheet.write(row, 8, emp_data['attendance_percentage'] / 100, percent_format)
                worksheet.write(row, 9, emp_data['total_work_hours'])
                worksheet.write(row, 10, emp_data['total_overtime_hours'])

        elif report.report_type == 'DEPARTMENT':
            worksheet = workbook.add_worksheet('Department Report')

            headers = [
                'Department', 'Employee Count', 'Total Days',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %',
                'Total Work Hours', 'Total Overtime Hours'
            ]

            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)

            for row, dept_data in enumerate(report.report_data.get('department_data', []), 1):
                worksheet.write(row, 0, dept_data['department_name'])
                worksheet.write(row, 1, dept_data['employee_count'])
                worksheet.write(row, 2, dept_data['total_days'])
                worksheet.write(row, 3, dept_data['present_count'])
                worksheet.write(row, 4, dept_data['absent_count'])
                worksheet.write(row, 5, dept_data['late_count'])
                worksheet.write(row, 6, dept_data['leave_count'])
                worksheet.write(row, 7, dept_data['attendance_percentage'] / 100, percent_format)
                worksheet.write(row, 8, dept_data['total_work_hours'])
                worksheet.write(row, 9, dept_data['total_overtime_hours'])

        elif report.report_type == 'CUSTOM':
            for employee_data in report.report_data.get('attendance_data', []):
                worksheet = workbook.add_worksheet(employee_data['employee_name'][:31])

                headers = [
                    'Date', 'Weekday', 'Status', 'First In', 'Last Out',
                    'Work Hours', 'Overtime Hours', 'Late Minutes', 'Early Departure Minutes'
                ]

                for col, header in enumerate(headers):
                    worksheet.write(0, col, header, header_format)

                for row, att_data in enumerate(employee_data['attendance'], 1):
                    worksheet.write(row, 0, att_data['date'])
                    worksheet.write(row, 1, att_data['weekday'])
                    worksheet.write(row, 2, att_data['status'])
                    worksheet.write(row, 3, att_data['first_in'] or '')
                    worksheet.write(row, 4, att_data['last_out'] or '')
                    worksheet.write(row, 5, att_data['work_hours'])
                    worksheet.write(row, 6, att_data['overtime_hours'])
                    worksheet.write(row, 7, att_data['late_minutes'])
                    worksheet.write(row, 8, att_data['early_departure_minutes'])

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{report.name}.xlsx"'

        return response

    def download_report_csv(self, report):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report.name}.csv"'

        writer = csv.writer(response)

        if report.report_type == 'DAILY':
            writer.writerow([
                'Date', 'Weekday', 'Total Employees', 'Present', 'Absent',
                'Late', 'On Leave', 'Attendance %'
            ])

            for day_data in report.report_data.get('daily_data', []):
                writer.writerow([
                    day_data['date'],
                    day_data['weekday'],
                    day_data['total_employees'],
                    day_data['present_count'],
                    day_data['absent_count'],
                    day_data['late_count'],
                    day_data['leave_count'],
                    day_data['attendance_percentage']
                ])

        elif report.report_type == 'WEEKLY':
            writer.writerow([
                'Week Start', 'Week End', 'Working Days', 'Total Employees',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %'
            ])

            for week_data in report.report_data.get('weekly_data', []):
                writer.writerow([
                    week_data['week_start'],
                    week_data['week_end'],
                    week_data['working_days'],
                    week_data['total_employees'],
                    week_data['present_count'],
                    week_data['absent_count'],
                    week_data['late_count'],
                    week_data['leave_count'],
                    week_data['attendance_percentage']
                ])

        elif report.report_type == 'MONTHLY':
            writer.writerow([
                'Year', 'Month', 'Working Days', 'Total Employees',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %'
            ])

            for month_data in report.report_data.get('monthly_data', []):
                writer.writerow([
                    month_data['year'],
                    month_data['month_name'],
                    month_data['working_days'],
                    month_data['total_employees'],
                    month_data['present_count'],
                    month_data['absent_count'],
                    month_data['late_count'],
                    month_data['leave_count'],
                    month_data['attendance_percentage']
                ])

        elif report.report_type == 'EMPLOYEE':
            writer.writerow([
                'Employee Code', 'Employee Name', 'Department', 'Total Days',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %',
                'Total Work Hours', 'Total Overtime Hours'
            ])

            for emp_data in report.report_data.get('employee_data', []):
                writer.writerow([
                    emp_data['employee_code'],
                    emp_data['employee_name'],
                    emp_data['department'],
                    emp_data['total_days'],
                    emp_data['present_count'],
                    emp_data['absent_count'],
                    emp_data['late_count'],
                    emp_data['leave_count'],
                    emp_data['attendance_percentage'],
                    emp_data['total_work_hours'],
                    emp_data['total_overtime_hours']
                ])

        elif report.report_type == 'DEPARTMENT':
            writer.writerow([
                'Department', 'Employee Count', 'Total Days',
                'Present', 'Absent', 'Late', 'On Leave', 'Attendance %',
                'Total Work Hours', 'Total Overtime Hours'
            ])

            for dept_data in report.report_data.get('department_data', []):
                writer.writerow([
                    dept_data['department_name'],
                    dept_data['employee_count'],
                    dept_data['total_days'],
                    dept_data['present_count'],
                    dept_data['absent_count'],
                    dept_data['late_count'],
                    dept_data['leave_count'],
                    dept_data['attendance_percentage'],
                    dept_data['total_work_hours'],
                    dept_data['total_overtime_hours']
                ])

        elif report.report_type == 'CUSTOM':
            for employee_data in report.report_data.get('attendance_data', []):
                writer.writerow([f"Employee: {employee_data['employee_name']} ({employee_data['employee_code']})"])
                writer.writerow([])

                writer.writerow([
                    'Date', 'Weekday', 'Status', 'First In', 'Last Out',
                    'Work Hours', 'Overtime Hours', 'Late Minutes', 'Early Departure Minutes'
                ])

                for att_data in employee_data['attendance']:
                    writer.writerow([
                        att_data['date'],
                        att_data['weekday'],
                        att_data['status'],
                        att_data['first_in'] or '',
                        att_data['last_out'] or '',
                        att_data['work_hours'],
                        att_data['overtime_hours'],
                        att_data['late_minutes'],
                        att_data['early_departure_minutes']
                    ])

                writer.writerow([])

        return response


class Devices(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if "id" in kwargs:
            return self.device_detail(request, kwargs["id"])
        else:
            return self.device_list(request)

    def device_list(self, request):
        devices = AttendanceDevice.objects.all().order_by("device_name")

        status_filter = request.GET.get("status", "")
        device_type_filter = request.GET.get("device_type", "")
        search_query = request.GET.get("search", "")

        if status_filter:
            devices = devices.filter(status=status_filter)

        if device_type_filter:
            devices = devices.filter(device_type=device_type_filter)

        if search_query:
            devices = devices.filter(
                Q(device_name__icontains=search_query)
                | Q(device_id__icontains=search_query)
                | Q(location__icontains=search_query)
            )

        paginator = Paginator(devices, 20)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        status_choices = AttendanceDevice._meta.get_field("status").choices
        device_type_choices = AttendanceDevice._meta.get_field("device_type").choices
        departments = Department.objects.filter(is_active=True).order_by("name")

        context = {
            "page_obj": page_obj,
            "status_choices": status_choices,
            "device_type_choices": device_type_choices,
            "departments": departments,
            "status_filter": status_filter,
            "device_type_filter": device_type_filter,
            "search_query": search_query,
        }

        return render(request, "attendance/device_list.html", context)

    def device_detail(self, request, device_id):
        device = get_object_or_404(AttendanceDevice, id=device_id)

        start_date = request.GET.get("start_date", "")
        end_date = request.GET.get("end_date", "")

        today = get_current_date()
        if not start_date:
            start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = today.strftime("%Y-%m-%d")

        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            start_date_obj = today - timedelta(days=7)
            end_date_obj = today

        logs = AttendanceLog.objects.filter(
            device=device, timestamp__date__range=[start_date_obj, end_date_obj]
        ).order_by("-timestamp")

        paginator = Paginator(logs, 50)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context = {
            "device": device,
            "page_obj": page_obj,
            "start_date": start_date,
            "end_date": end_date,
        }

        return render(request, "attendance/device_detail.html", context)

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "create":
            return self.create_device(request)
        elif request.POST.get("action") == "update":
            return self.update_device(request)
        elif request.POST.get("action") == "sync":
            return self.sync_device(request)
        elif request.POST.get("action") == "sync_multiple":
            return self.sync_multiple_devices(request)
        elif request.POST.get("action") == "test_connection":
            return self.test_device_connection(request)
        elif request.POST.get("action") == "toggle_status":
            return self.toggle_device_status(request)
        else:
            messages.error(request, "Invalid action")
            return redirect("attendance:device_list")

    def create_device(self, request):
        device_id = request.POST.get("device_id")
        device_name = request.POST.get("device_name")
        device_type = request.POST.get("device_type")
        ip_address = request.POST.get("ip_address")
        port = request.POST.get("port")
        location = request.POST.get("location")
        department_id = request.POST.get("department")

        try:
            department = None
            if department_id:
                department = Department.objects.get(id=department_id)

            device = AttendanceDevice(
                device_id=device_id,
                device_name=device_name,
                device_type=device_type,
                ip_address=ip_address,
                port=int(port),
                location=location,
                department=department,
                created_by=request.user,
            )

            device.save()

            messages.success(request, f'Device "{device_name}" created successfully')
            return redirect("attendance:device_detail", id=device.id)

        except ValidationError as e:
            messages.error(request, f"Validation error: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error creating device: {str(e)}")

        return redirect("attendance:device_list")

    def update_device(self, request):
        device_id = request.POST.get("device_id")

        try:
            device = AttendanceDevice.objects.get(id=device_id)

            device.device_name = request.POST.get("device_name")
            device.device_type = request.POST.get("device_type")
            device.ip_address = request.POST.get("ip_address")
            device.port = int(request.POST.get("port"))
            device.location = request.POST.get("location")
            device.status = request.POST.get("status")

            department_id = request.POST.get("department")
            if department_id:
                device.department = Department.objects.get(id=department_id)
            else:
                device.department = None

            device.is_active = request.POST.get("is_active") == "on"

            device.save()

            messages.success(
                request, f'Device "{device.device_name}" updated successfully'
            )
            return redirect("attendance:device_detail", id=device.id)

        except AttendanceDevice.DoesNotExist:
            messages.error(request, "Device not found")
        except ValidationError as e:
            messages.error(request, f"Validation error: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error updating device: {str(e)}")

        return redirect("attendance:device_list")

    def sync_device(self, request):
        device_id = request.POST.get("device_id")

        try:
            device = AttendanceDevice.objects.get(id=device_id)

            from django.utils.module_loading import import_string

            DeviceService = import_string("attendance.services.DeviceService")

            result = DeviceService.sync_device_data(device)

            device.last_sync_time = timezone.now()
            device.save(update_fields=["last_sync_time"])

            if result.get("success"):
                messages.success(
                    request,
                    f'Successfully synced {result.get("records_synced", 0)} records from device "{device.device_name}"',
                )
            else:
                messages.error(
                    request,
                    f'Error syncing device: {result.get("error", "Unknown error")}',
                )

            return redirect("attendance:device_detail", id=device.id)

        except AttendanceDevice.DoesNotExist:
            messages.error(request, "Device not found")
        except Exception as e:
            messages.error(request, f"Error syncing device: {str(e)}")

        return redirect("attendance:device_list")

    def sync_multiple_devices(self, request):
        sync_all = request.POST.get("sync_all") in ["true", "on", True, "True", "1", 1]
        sync_employees = request.POST.get("sync_employees") in ["true", "on", True, "True", "1", 1]

        if sync_all:
            devices = AttendanceDevice.objects.filter(is_active=True)
        else:
            device_ids = request.POST.getlist("devices")
            devices = AttendanceDevice.objects.filter(id__in=device_ids)

        if not devices:
            messages.error(request, "No devices selected for syncing")
            return redirect("attendance:device_list")

        DeviceService = import_string("attendance.services.DeviceService")

        success_count = 0
        error_count = 0
        total_records = 0

        for device in devices:
            try:
                result = DeviceService.sync_device_data(device)

                device.last_sync_time = timezone.now()
                device.save(update_fields=["last_sync_time"])

                if result.get("success"):
                    success_count += 1
                    total_records += result.get("records_synced", 0)
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1

        if success_count > 0:
            messages.success(
                request,
                f"Successfully synced {total_records} records from {success_count} devices",
            )

        if error_count > 0:
            messages.warning(request, f"Failed to sync {error_count} devices")

        return redirect("attendance:device_list")

    def test_device_connection(self, request):
        device_id = request.POST.get("device_id")

        try:
            device = AttendanceDevice.objects.get(id=device_id)

            is_connected, message = device.test_connection()

            if is_connected:
                messages.success(
                    request, f'Successfully connected to device "{device.device_name}"'
                )
            else:
                messages.error(request, f"Failed to connect to device: {message}")

            return redirect("attendance:device_detail", id=device.id)

        except AttendanceDevice.DoesNotExist:
            messages.error(request, "Device not found")
        except Exception as e:
            messages.error(request, f"Error testing connection: {str(e)}")

        return redirect("attendance:device_list")

    def toggle_device_status(self, request):
        device_id = request.POST.get("device_id")

        try:
            device = AttendanceDevice.objects.get(id=device_id)
            device.is_active = not device.is_active
            device.save(update_fields=["is_active"])

            status = "activated" if device.is_active else "deactivated"
            messages.success(
                request, f'Device "{device.device_name}" {status} successfully'
            )

            if "id" in request.resolver_match.kwargs:
                return redirect("attendance:device_detail", id=device.id)
            else:
                return redirect("attendance:device_list")

        except AttendanceDevice.DoesNotExist:
            messages.error(request, "Device not found")
        except Exception as e:
            messages.error(request, f"Error toggling device status: {str(e)}")

        return redirect("attendance:device_list")


class Corrections(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.correction_detail(request, kwargs['id'])
        else:
            return self.correction_list(request)

    def correction_list(self, request):
        status_filter = request.GET.get('status', '')
        correction_type_filter = request.GET.get('correction_type', '')
        search_query = request.GET.get('search', '')
        
        corrections = AttendanceCorrection.objects.all()
        
        if status_filter:
            corrections = corrections.filter(status=status_filter)
        
        if correction_type_filter:
            corrections = corrections.filter(correction_type=correction_type_filter)
        
        if search_query:
            corrections = corrections.filter(
                Q(attendance__employee__first_name__icontains=search_query) |
                Q(attendance__employee__last_name__icontains=search_query) |
                Q(attendance__employee__employee_code__icontains=search_query) |
                Q(reason__icontains=search_query)
            )
        
        corrections = corrections.order_by('-requested_at')
        
        paginator = Paginator(corrections, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        status_choices = AttendanceCorrection._meta.get_field('status').choices
        correction_type_choices = AttendanceCorrection._meta.get_field('correction_type').choices
        
        context = {
            'page_obj': page_obj,
            'status_choices': status_choices,
            'correction_type_choices': correction_type_choices,
            'status_filter': status_filter,
            'correction_type_filter': correction_type_filter,
            'search_query': search_query,
        }
        
        return render(request, 'attendance/correction_list.html', context)

    def correction_detail(self, request, correction_id):
        correction = get_object_or_404(AttendanceCorrection, id=correction_id)
        
        context = {
            'correction': correction,
            'original_data': json.dumps(correction.original_data, indent=2),
            'corrected_data': json.dumps(correction.corrected_data, indent=2),
        }
        
        return render(request, 'attendance/correction_detail.html', context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'create':
            return self.create_correction(request)
        elif request.POST.get('action') == 'approve':
            return self.approve_correction(request)
        elif request.POST.get('action') == 'reject':
            return self.reject_correction(request)
        else:
            messages.error(request, 'Invalid action')
            return redirect('attendance:correction_list')

    def create_correction(self, request):
        attendance_id = request.POST.get('attendance_id')
        correction_type = request.POST.get('correction_type')
        reason = request.POST.get('reason')
        
        try:
            attendance = Attendance.objects.get(id=attendance_id)
            
            corrected_data = {}
            
            if correction_type == 'TIME_ADJUSTMENT':
                for i in range(1, 7):
                    in_time = request.POST.get(f'check_in_{i}')
                    out_time = request.POST.get(f'check_out_{i}')
                    
                    if in_time:
                        corrected_data[f'check_in_{i}'] = in_time
                    
                    if out_time:
                        corrected_data[f'check_out_{i}'] = out_time
            
            elif correction_type == 'STATUS_CHANGE':
                corrected_data['status'] = request.POST.get('status')
            
            elif correction_type == 'MANUAL_ENTRY':
                for i in range(1, 7):
                    in_time = request.POST.get(f'check_in_{i}')
                    out_time = request.POST.get(f'check_out_{i}')
                    
                    if in_time:
                        corrected_data[f'check_in_{i}'] = in_time
                    
                    if out_time:
                        corrected_data[f'check_out_{i}'] = out_time
                
                corrected_data['is_manual_entry'] = True
            
            if 'notes' in request.POST:
                corrected_data['notes'] = request.POST.get('notes')
            
            correction = AttendanceCorrection(
                attendance=attendance,
                correction_type=correction_type,
                reason=reason,
                corrected_data=corrected_data,
                requested_by=request.user
            )
            
            correction.save()
            
            approval_required = SystemConfiguration.get_bool_setting(
                "ATTENDANCE_CORRECTION_APPROVAL_REQUIRED", True
            )
            
            if not approval_required:
                correction.approve(request.user)
                messages.success(request, 'Attendance correction applied successfully')
            else:
                messages.success(request, 'Attendance correction request submitted successfully')
            
            return redirect('attendance:correction_detail', id=correction.id)
            
        except Attendance.DoesNotExist:
            messages.error(request, 'Attendance record not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating correction: {str(e)}')
        
        return redirect('attendance:attendance_list')

    def approve_correction(self, request):
        correction_id = request.POST.get('correction_id')
        
        try:
            correction = AttendanceCorrection.objects.get(id=correction_id)
            
            if correction.status != 'PENDING':
                messages.error(request, 'This correction has already been processed')
                return redirect('attendance:correction_detail', id=correction.id)
            
            correction.approve(request.user)
            
            messages.success(request, 'Attendance correction approved and applied successfully')
            return redirect('attendance:correction_detail', id=correction.id)
            
        except AttendanceCorrection.DoesNotExist:
            messages.error(request, 'Correction not found')
        except Exception as e:
            messages.error(request, f'Error approving correction: {str(e)}')
        
        return redirect('attendance:correction_list')

    def reject_correction(self, request):
        correction_id = request.POST.get('correction_id')
        rejection_reason = request.POST.get('rejection_reason')
        
        try:
            correction = AttendanceCorrection.objects.get(id=correction_id)
            
            if correction.status != 'PENDING':
                messages.error(request, 'This correction has already been processed')
                return redirect('attendance:correction_detail', id=correction.id)
            
            correction.reject(request.user, rejection_reason)
            
            messages.success(request, 'Attendance correction rejected successfully')
            return redirect('attendance:correction_detail', id=correction.id)
            
        except AttendanceCorrection.DoesNotExist:
            messages.error(request, 'Correction not found')
        except Exception as e:
            messages.error(request, f'Error rejecting correction: {str(e)}')
        
        return redirect('attendance:correction_list')

class Holidays(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs:
            return self.holiday_detail(request, kwargs['id'])
        else:
            return self.holiday_list(request)

    def holiday_list(self, request):
        year = request.GET.get('year', get_current_date().year)
        holiday_type_filter = request.GET.get('holiday_type', '')
        search_query = request.GET.get('search', '')
        
        try:
            year = int(year)
        except ValueError:
            year = get_current_date().year
        
        holidays = Holiday.objects.filter(date__year=year)
        
        if holiday_type_filter:
            holidays = holidays.filter(holiday_type=holiday_type_filter)
        
        if search_query:
            holidays = holidays.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        holidays = holidays.order_by('date')
        
        paginator = Paginator(holidays, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        holiday_type_choices = Holiday._meta.get_field('holiday_type').choices
        departments = Department.objects.filter(is_active=True).order_by('name')
        
        context = {
            'page_obj': page_obj,
            'holiday_type_choices': holiday_type_choices,
            'departments': departments,
            'year': year,
            'holiday_type_filter': holiday_type_filter,
            'search_query': search_query,
            'years': range(get_current_date().year - 2, get_current_date().year + 3),
        }
        
        return render(request, 'attendance/holiday_list.html', context)

    def holiday_detail(self, request, holiday_id):
        holiday = get_object_or_404(Holiday, id=holiday_id)
        
        context = {
            'holiday': holiday,
            'applicable_departments': holiday.applicable_departments.all(),
        }
        
        return render(request, 'attendance/holiday_detail.html', context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'create':
            return self.create_holiday(request)
        elif request.POST.get('action') == 'update':
            return self.update_holiday(request)
        elif request.POST.get('action') == 'delete':
            return self.delete_holiday(request)
        else:
            messages.error(request, 'Invalid action')
            return redirect('attendance:holiday_list')

    def create_holiday(self, request):
        name = request.POST.get('name')
        date_str = request.POST.get('date')
        holiday_type = request.POST.get('holiday_type')
        description = request.POST.get('description', '')
        is_optional = request.POST.get('is_optional') == 'on'
        is_paid = request.POST.get('is_paid') == 'on'
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            holiday = Holiday(
                name=name,
                date=date_obj,
                holiday_type=holiday_type,
                description=description,
                is_optional=is_optional,
                is_paid=is_paid,
                created_by=request.user
            )
            
            holiday.save()
            
            department_ids = request.POST.getlist('applicable_departments')
            if department_ids:
                holiday.applicable_departments.set(department_ids)
            
            locations = request.POST.get('applicable_locations', '')
            if locations:
                holiday.applicable_locations = [loc.strip() for loc in locations.split(',')]
                holiday.save(update_fields=['applicable_locations'])
            
            messages.success(request, f'Holiday "{name}" created successfully')
            return redirect('attendance:holiday_detail', id=holiday.id)
            
        except ValueError:
            messages.error(request, 'Invalid date format')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating holiday: {str(e)}')
        
        return redirect('attendance:holiday_list')

    def update_holiday(self, request):
        holiday_id = request.POST.get('holiday_id')
        
        try:
            holiday = Holiday.objects.get(id=holiday_id)
            
            holiday.name = request.POST.get('name')
            holiday.date = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
            holiday.holiday_type = request.POST.get('holiday_type')
            holiday.description = request.POST.get('description', '')
            holiday.is_optional = request.POST.get('is_optional') == 'on'
            holiday.is_paid = request.POST.get('is_paid') == 'on'
            holiday.is_active = request.POST.get('is_active') == 'on'
            
            holiday.save()
            
            department_ids = request.POST.getlist('applicable_departments')
            holiday.applicable_departments.set(department_ids)
            
            locations = request.POST.get('applicable_locations', '')
            if locations:
                holiday.applicable_locations = [loc.strip() for loc in locations.split(',')]
            else:
                holiday.applicable_locations = []
            
            holiday.save(update_fields=['applicable_locations'])
            
            messages.success(request, f'Holiday "{holiday.name}" updated successfully')
            return redirect('attendance:holiday_detail', id=holiday.id)
            
        except Holiday.DoesNotExist:
            messages.error(request, 'Holiday not found')
        except ValueError:
            messages.error(request, 'Invalid date format')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating holiday: {str(e)}')
        
        return redirect('attendance:holiday_list')

    def delete_holiday(self, request):
        holiday_id = request.POST.get('holiday_id')
        
        try:
            holiday = Holiday.objects.get(id=holiday_id)
            holiday_name = holiday.name
            
            holiday.delete()
            
            messages.success(request, f'Holiday "{holiday_name}" deleted successfully')
            return redirect('attendance:holiday_list')
            
        except Holiday.DoesNotExist:
            messages.error(request, 'Holiday not found')
        except Exception as e:
            messages.error(request, f'Error deleting holiday: {str(e)}')
        
        return redirect('attendance:holiday_list')


class Shifts(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'id' in kwargs and 'employee_id' in kwargs:
            return self.employee_shift_detail(request, kwargs['id'], kwargs['employee_id'])
        elif 'id' in kwargs:
            return self.shift_detail(request, kwargs['id'])
        elif 'employee_id' in kwargs:
            return self.employee_shifts(request, kwargs['employee_id'])
        elif request.path.endswith('/employee_shifts/'):
            return self.employee_shift_list(request)
        else:
            return self.shift_list(request)

    def shift_list(self, request):
        shifts = Shift.objects.all()

        shift_type_filter = request.GET.get('shift_type', '')
        search_query = request.GET.get('search', '')

        if shift_type_filter:
            shifts = shifts.filter(shift_type=shift_type_filter)

        if search_query:
            shifts = shifts.filter(
                Q(name__icontains=search_query) |
                Q(code__icontains=search_query)
            )

        shifts = shifts.order_by('name')

        paginator = Paginator(shifts, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        shift_type_choices = Shift._meta.get_field('shift_type').choices

        context = {
            'page_obj': page_obj,
            'shift_type_choices': shift_type_choices,
            'shift_type_filter': shift_type_filter,
            'search_query': search_query,
        }

        return render(request, 'attendance/shift_list.html', context)

    def shift_detail(self, request, shift_id):
        shift = get_object_or_404(Shift, id=shift_id)

        assigned_employees = EmployeeShift.objects.filter(
            shift=shift,
            is_active=True
        ).order_by('-effective_from')

        paginator = Paginator(assigned_employees, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        context = {
            'shift': shift,
            'page_obj': page_obj,
        }

        return render(request, 'attendance/shift_detail.html', context)

    def employee_shift_list(self, request):
        employee_shifts = EmployeeShift.objects.all()

        shift_filter = request.GET.get('shift', '')
        is_active_filter = request.GET.get('is_active', '')
        search_query = request.GET.get('search', '')

        if shift_filter:
            employee_shifts = employee_shifts.filter(shift_id=shift_filter)

        if is_active_filter:
            is_active = is_active_filter == 'true'
            employee_shifts = employee_shifts.filter(is_active=is_active)

        if search_query:
            employee_shifts = employee_shifts.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__employee_code__icontains=search_query)
            )

        employee_shifts = employee_shifts.order_by('-effective_from')

        paginator = Paginator(employee_shifts, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        shifts = Shift.objects.filter(is_active=True).order_by('name')

        employees = User.objects.filter(is_active=True).order_by(
            "first_name", "last_name"
        )

        context = {
            'page_obj': page_obj,
            'shifts': shifts,
            'shift_filter': shift_filter,
            'is_active_filter': is_active_filter,
            'search_query': search_query,
            'employees': employees,
            'current_date': date.today(),
        }

        return render(request, 'attendance/employee_shift_list.html', context)

    def employee_shifts(self, request, employee_id):
        employee = get_object_or_404(User, id=employee_id)

        employee_shifts = EmployeeShift.objects.filter(
            employee=employee
        ).order_by('-effective_from')

        context = {
            'employee': employee,
            'employee_shifts': employee_shifts,
        }

        return render(request, 'attendance/employee_shifts.html', context)
    
    def employee_shift_detail(self, request, shift_id, employee_id):
        employee_shift = get_object_or_404(
            EmployeeShift, 
            id=shift_id,
            employee_id=employee_id
        )
        
        employee = employee_shift.employee
        
        available_shifts = Shift.objects.filter(is_active=True).order_by('name')
        
        assignment_history = []
        
        context = {
            'employee_shift': employee_shift,
            'employee': employee,
            'available_shifts': available_shifts,
            'current_date': date.today(),
            'assignment_history': assignment_history
        }

        return render(request, 'attendance/employee_shift_detail.html', context)

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'create_shift':
            return self.create_shift(request)
        elif request.POST.get('action') == 'update_shift':
            return self.update_shift(request)
        elif request.POST.get('action') == 'assign_shift':
            return self.assign_shift(request)
        elif request.POST.get('action') == 'update_employee_shift':
            return self.update_employee_shift(request)
        elif request.POST.get('action') == 'end_employee_shift':
            return self.end_employee_shift(request)
        else:
            messages.error(request, 'Invalid action')
            return redirect('attendance:shift_list')

    def create_shift(self, request):
        name = request.POST.get('name')
        shift_type = request.POST.get('shift_type')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        break_duration_minutes = request.POST.get('break_duration_minutes')
        grace_period_minutes = request.POST.get('grace_period_minutes')
        working_hours = request.POST.get('working_hours')
        is_night_shift = request.POST.get('is_night_shift') == 'on'
        weekend_applicable = request.POST.get('weekend_applicable') == 'on'
        holiday_applicable = request.POST.get('holiday_applicable') == 'on'

        try:
            shift = Shift(
                name=name,
                shift_type=shift_type,
                start_time=start_time,
                end_time=end_time,
                break_duration_minutes=int(break_duration_minutes),
                grace_period_minutes=int(grace_period_minutes),
                working_hours=Decimal(working_hours),
                is_night_shift=is_night_shift,
                weekend_applicable=weekend_applicable,
                holiday_applicable=holiday_applicable,
                created_by=request.user
            )

            shift.save()

            messages.success(request, f'Shift "{name}" created successfully')
            return redirect('attendance:shift_detail', id=shift.id)

        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating shift: {str(e)}')

        return redirect('attendance:shift_list')

    def update_shift(self, request):
        shift_id = request.POST.get('shift_id')

        try:
            shift = Shift.objects.get(id=shift_id)

            shift.name = request.POST.get('name')
            shift.shift_type = request.POST.get('shift_type')
            shift.start_time = request.POST.get('start_time')
            shift.end_time = request.POST.get('end_time')
            shift.break_duration_minutes = int(request.POST.get('break_duration_minutes'))
            shift.grace_period_minutes = int(request.POST.get('grace_period_minutes'))
            shift.working_hours = Decimal(request.POST.get('working_hours'))
            shift.is_night_shift = request.POST.get('is_night_shift') == 'on'
            shift.weekend_applicable = request.POST.get('weekend_applicable') == 'on'
            shift.holiday_applicable = request.POST.get('holiday_applicable') == 'on'
            shift.is_active = request.POST.get('is_active') == 'on'

            shift.save()

            messages.success(request, f'Shift "{shift.name}" updated successfully')
            return redirect('attendance:shift_detail', id=shift.id)

        except Shift.DoesNotExist:
            messages.error(request, 'Shift not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating shift: {str(e)}')

        return redirect('attendance:shift_list')

    def assign_shift(self, request):
        employee_id = request.POST.get('employee_id')
        shift_id = request.POST.get('shift_id')
        effective_from_str = request.POST.get('effective_from')
        effective_to_str = request.POST.get('effective_to', '')
        is_temporary = request.POST.get('is_temporary') == 'on'
        notes = request.POST.get('notes', '')

        try:
            employee = User.objects.get(id=employee_id)
            shift = Shift.objects.get(id=shift_id)

            effective_from = datetime.strptime(effective_from_str, '%Y-%m-%d').date()

            effective_to = None
            if effective_to_str:
                effective_to = datetime.strptime(effective_to_str, '%Y-%m-%d').date()

                if effective_to <= effective_from:
                    messages.error(request, 'Effective to date must be after effective from date')
                    return redirect('attendance:employee_shifts', employee_id=employee_id)

            employee_shift = EmployeeShift(
                employee=employee,
                shift=shift,
                effective_from=effective_from,
                effective_to=effective_to,
                is_temporary=is_temporary,
                notes=notes,
                assigned_by=request.user
            )

            employee_shift.save()

            messages.success(
                request, 
                f'Shift "{shift.name}" assigned to {employee.get_full_name()} successfully'
            )
            return redirect('attendance:employee_shift_detail', id=employee_shift.id, employee_id=employee.id)

        except User.DoesNotExist:
            messages.error(request, 'Employee not found')
        except Shift.DoesNotExist:
            messages.error(request, 'Shift not found')
        except ValueError:
            messages.error(request, 'Invalid date format')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error assigning shift: {str(e)}')

        return redirect('attendance:employee_shift_list')

    def update_employee_shift(self, request):
        employee_shift_id = request.POST.get('employee_shift_id')

        try:
            employee_shift = EmployeeShift.objects.get(id=employee_shift_id)

            shift_id = request.POST.get('shift_id')
            effective_from_str = request.POST.get('effective_from')
            effective_to_str = request.POST.get('effective_to', '')
            is_temporary = request.POST.get('is_temporary') == 'on'
            notes = request.POST.get('notes', '')
            is_active = request.POST.get('is_active') == 'on'

            employee_shift.shift_id = shift_id
            employee_shift.effective_from = datetime.strptime(effective_from_str, '%Y-%m-%d').date()

            if effective_to_str:
                employee_shift.effective_to = datetime.strptime(effective_to_str, '%Y-%m-%d').date()
            else:
                employee_shift.effective_to = None

            employee_shift.is_temporary = is_temporary
            employee_shift.notes = notes
            employee_shift.is_active = is_active

            employee_shift.save()

            messages.success(
                request, 
                f'Shift assignment updated successfully for {employee_shift.employee.get_full_name()}'
            )
            return redirect(
                'attendance:employee_shift_detail', 
                id=employee_shift.id, 
                employee_id=employee_shift.employee.id
            )

        except EmployeeShift.DoesNotExist:
            messages.error(request, 'Shift assignment not found')
        except ValueError:
            messages.error(request, 'Invalid date format')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating shift assignment: {str(e)}')

        return redirect('attendance:employee_shift_list')

    def end_employee_shift(self, request):
        employee_shift_id = request.POST.get('employee_shift_id')
        end_date_str = request.POST.get('end_date')

        try:
            employee_shift = EmployeeShift.objects.get(id=employee_shift_id)

            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            if end_date <= employee_shift.effective_from:
                messages.error(request, 'End date must be after effective from date')
                return redirect(
                    'attendance:employee_shift_detail', 
                    id=employee_shift.id, 
                    employee_id=employee_shift.employee.id
                )

            employee_shift.effective_to = end_date
            employee_shift.save(update_fields=['effective_to'])

            messages.success(
                request, 
                f'Shift assignment ended successfully for {employee_shift.employee.get_full_name()}'
            )
            return redirect(
                'attendance:employee_shift_detail', 
                id=employee_shift.id, 
                employee_id=employee_shift.employee.id
            )

        except EmployeeShift.DoesNotExist:
            messages.error(request, 'Shift assignment not found')
        except ValueError:
            messages.error(request, 'Invalid date format')
        except Exception as e:
            messages.error(request, f'Error ending shift assignment: {str(e)}')

        return redirect('attendance:employee_shift_list')

class Leave(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if 'request_id' in kwargs:
            return self.leave_request_detail(request, kwargs['request_id'])
        elif 'balance_id' in kwargs:
            return self.leave_balance_detail(request, kwargs['balance_id'])
        elif 'type_id' in kwargs:
            return self.leave_type_detail(request, kwargs['type_id'])
        elif 'employee_id' in kwargs:
            if '/balances/' in request.path:
                return self.employee_leave_balances(request, kwargs['employee_id'])
            elif '/leave/' in request.path or '/requests/' in request.path:
                return self.employee_leave_requests(request, kwargs['employee_id'])
            else:
                return self.employee_leave_requests(request, kwargs['employee_id'])
        elif 'balances' in request.path:
            return self.leave_balance_list(request)
        elif 'types' in request.path:
            return self.leave_type_list(request)
        else:
            return self.leave_request_list(request)
            
    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'create_leave_type':
            return self.create_leave_type(request)
        elif request.POST.get('action') == 'update_leave_type':
            return self.update_leave_type(request)
        elif request.POST.get('action') == 'create_leave_request':
            return self.create_leave_request(request)
        elif request.POST.get('action') == 'approve_leave_request':
            return self.approve_leave_request(request)
        elif request.POST.get('action') == 'reject_leave_request':
            return self.reject_leave_request(request)
        elif request.POST.get('action') == 'cancel_leave_request':
            return self.cancel_leave_request(request)
        elif request.POST.get('action') == 'update_leave_balance':
            return self.update_leave_balance(request)
        elif request.POST.get('action') == 'initialize_leave_balances':
            employee_id = request.POST.get('employee_id')
            if employee_id:
                
                result = self.initialize_leave_balances(request)
                return redirect('attendance:employee_leave_balances', employee_id=employee_id)
            else:
                return self.initialize_leave_balances(request)
        else:
       
            if 'employee_id' in kwargs:
                employee_id = kwargs['employee_id']
                if '/balances/' in request.path:
                    messages.error(request, 'Invalid action')
                    return redirect('attendance:employee_leave_balances', employee_id=employee_id)
                else:
                    messages.error(request, 'Invalid action')
                    return redirect('attendance:employee_leave_requests', employee_id=employee_id)
            else:
                messages.error(request, 'Invalid action')
                return redirect('attendance:leave_request_list')

    def leave_request_list(self, request):
        status_filter = request.GET.get('status', '')
        leave_type_filter = request.GET.get('leave_type', '')
        search_query = request.GET.get('search', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')

        leave_requests = LeaveRequest.objects.all()

        if status_filter:
            leave_requests = leave_requests.filter(status=status_filter)

        if leave_type_filter:
            leave_requests = leave_requests.filter(leave_type_id=leave_type_filter)

        if search_query:
            leave_requests = leave_requests.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__employee_code__icontains=search_query) |
                Q(reason__icontains=search_query)
            )

        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                leave_requests = leave_requests.filter(start_date__gte=start_date_obj)
            except ValueError:
                pass

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                leave_requests = leave_requests.filter(end_date__lte=end_date_obj)
            except ValueError:
                pass

        leave_requests = leave_requests.order_by('-applied_at')

        paginator = Paginator(leave_requests, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        status_choices = LeaveRequest._meta.get_field('status').choices
        leave_types = LeaveType.objects.filter(is_active=True).order_by('name')

        employees = User.objects.filter(is_active=True)

        context = {
            'page_obj': page_obj,
            'status_choices': status_choices,
            'leave_types': leave_types,
            'status_filter': status_filter,
            'leave_type_filter': leave_type_filter,
            'search_query': search_query,
            'start_date': start_date,
            'end_date': end_date,
            'employees': employees,
        }

        return render(request, 'attendance/leave_request_list.html', context)

    def leave_request_detail(self, request, request_id):
        leave_request = get_object_or_404(LeaveRequest, id=request_id)
        
        try:
            leave_balance = LeaveBalance.objects.get(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=leave_request.start_date.year
            )
        except LeaveBalance.DoesNotExist:
            leave_balance = None
        
        context = {
            'leave_request': leave_request,
            'leave_balance': leave_balance,
        }

        return render(request, 'attendance/leave_request_detail.html', context)

    def leave_type_list(self, request):
        leave_types = LeaveType.objects.all()

        category_filter = request.GET.get('category', '')
        search_query = request.GET.get('search', '')

        if category_filter:
            leave_types = leave_types.filter(category=category_filter)

        if search_query:
            leave_types = leave_types.filter(
                Q(name__icontains=search_query) |
                Q(code__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        leave_types = leave_types.order_by('name')

        paginator = Paginator(leave_types, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        category_choices = LeaveType._meta.get_field('category').choices

        context = {
            'page_obj': page_obj,
            'category_choices': category_choices,
            'category_filter': category_filter,
            'search_query': search_query,
        }

        return render(request, 'attendance/leave_type_list.html', context)

    def leave_type_detail(self, request, type_id):
        
        leave_type = get_object_or_404(LeaveType, id=type_id)
        
        year = request.GET.get('year', get_current_date().year)
        try:
            year = int(year)
        except ValueError:
            year = get_current_date().year
        
        search_query = request.GET.get('search', '')
        
        balances_query = LeaveBalance.objects.filter(
            leave_type=leave_type,
            year=year
        ).select_related('employee').order_by('employee__employee_code')
        
        if search_query:
            balances_query = balances_query.filter(
                Q(employee__first_name__icontains=search_query) | 
                Q(employee__last_name__icontains=search_query) |
                Q(employee__employee_code__icontains=search_query)
            )
        
        paginator = Paginator(balances_query, 10)
        page = request.GET.get('page', 1)
        employee_balances = paginator.get_page(page)
        
        recent_leave_requests = LeaveRequest.objects.filter(
            leave_type=leave_type
        ).order_by('-applied_at')[:5]

        employees = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
        leave_types = LeaveType.objects.filter(is_active=True).order_by('name')

        context = {
            'leave_type': leave_type,
            'employee_balances': employee_balances,
            'recent_leave_requests': recent_leave_requests,
            'year': year,
            'years': range(get_current_date().year - 2, get_current_date().year + 3),
            'search_query': search_query,
            'employees': employees,  
            'leave_types': leave_types,
        }
        
        return render(request, 'attendance/leave_type_detail.html', context)
    
    def leave_balance_list(self, request):
        year = request.GET.get('year', get_current_date().year)
        leave_type_filter = request.GET.get('leave_type', '')
        search_query = request.GET.get('search', '')

        try:
            year = int(year)
        except ValueError:
            year = get_current_date().year

        leave_balances = LeaveBalance.objects.filter(year=year)

        if leave_type_filter:
            leave_balances = leave_balances.filter(leave_type_id=leave_type_filter)

        if search_query:
            leave_balances = leave_balances.filter(
                Q(employee__first_name__icontains=search_query) |
                Q(employee__last_name__icontains=search_query) |
                Q(employee__employee_code__icontains=search_query)
            )

        leave_balances = leave_balances.order_by('employee__employee_code', 'leave_type__name')

        paginator = Paginator(leave_balances, 25)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        leave_types = LeaveType.objects.filter(is_active=True).order_by('name')
        
        employees = User.objects.filter(is_active=True) 

        context = {
            "page_obj": page_obj,
            "leave_types": leave_types,
            "year": year,
            "leave_type_filter": leave_type_filter,
            "search_query": search_query,
            "years": range(get_current_date().year - 2, get_current_date().year + 2),
            "employees": employees,
        }

        return render(request, 'attendance/leave_balance_list.html', context)

    def leave_balance_detail(self, request, balance_id):
        from accounts.models import AuditLog
        
        leave_balance = get_object_or_404(LeaveBalance, id=balance_id)

        leave_requests = LeaveRequest.objects.filter(
            employee=leave_balance.employee,
            leave_type=leave_balance.leave_type,
            start_date__year=leave_balance.year
        ).order_by('-applied_at')
        
        other_balances = LeaveBalance.objects.filter(
            employee=leave_balance.employee,
            year=leave_balance.year
        ).exclude(id=leave_balance.id)
        
        balance_adjustments = AuditLog.objects.filter(
            action="LEAVE_CHANGE",
            object_id=str(leave_balance.id),
            model_name="LeaveBalance"
        ).order_by('-timestamp')
        
        context = {
            'leave_balance': leave_balance,
            'leave_requests': leave_requests,
            'other_balances': other_balances,
            'balance_adjustments': balance_adjustments,
        }

        return render(request, 'attendance/leave_balance_detail.html', context)

    def employee_leave_requests(self, request, employee_id):

        employee = get_object_or_404(User, id=employee_id)

        status_filter = request.GET.get('status', '')
        leave_type_filter = request.GET.get('leave_type', '')
        year_filter = request.GET.get('year', get_current_date().year)
        search_query = request.GET.get('search', '')

        try:
            year_filter = int(year_filter)
        except ValueError:
            year_filter = get_current_date().year

        leave_requests = LeaveRequest.objects.filter(employee=employee)

        if status_filter:
            leave_requests = leave_requests.filter(status=status_filter)

        if leave_type_filter:
            leave_requests = leave_requests.filter(leave_type_id=leave_type_filter)

        leave_requests = leave_requests.filter(
            Q(start_date__year=year_filter) | Q(end_date__year=year_filter)
        )
        
        if search_query:
            leave_requests = leave_requests.filter(
                Q(leave_type__name__icontains=search_query) |
                Q(reason__icontains=search_query)
            )

        leave_requests = leave_requests.order_by('-applied_at')
        
        paginator = Paginator(leave_requests, 10)  
        page = request.GET.get('page', 1)
        page_obj = paginator.get_page(page)

        current_year = get_current_date().year
        leave_balances = LeaveBalance.objects.filter(
            employee=employee,
            year=current_year
        ).select_related('leave_type')

        status_choices = LeaveRequest._meta.get_field('status').choices
        leave_types = LeaveType.objects.filter(is_active=True).order_by('name')

        context = {
            'employee': employee,
            'leave_requests': leave_requests,
            'page_obj': page_obj,
            'leave_balances': leave_balances,
            'status_choices': status_choices,
            'leave_types': leave_types,
            'status_filter': status_filter,
            'leave_type_filter': leave_type_filter,
            'year_filter': year_filter,
            'search_query': search_query,
            'years': range(get_current_date().year - 2, get_current_date().year + 2),
        }

        return render(request, 'attendance/employee_leave_requests.html', context)

    def employee_leave_balances(self, request, employee_id):
        from django.core.paginator import Paginator
        
        employee = get_object_or_404(User, id=employee_id)

        year = request.GET.get('year', get_current_date().year)
        try:
            year = int(year)
        except ValueError:
            year = get_current_date().year

        search_query = request.GET.get('search', '')
        
        leave_balances_query = LeaveBalance.objects.filter(
            employee=employee,
            year=year
        ).select_related('leave_type').order_by('leave_type__name')
        
        if search_query:
            leave_balances_query = leave_balances_query.filter(
                leave_type__name__icontains=search_query
            )
        
        paginator = Paginator(leave_balances_query, 10)  
        page = request.GET.get('page', 1)
        page_obj = paginator.get_page(page)
        
        leave_types = LeaveType.objects.filter(is_active=True).order_by('name')
        
        recent_leave_requests = LeaveRequest.objects.filter(
            employee=employee
        ).order_by('-applied_at')[:5]

        context = {
            'employee': employee,
            'leave_balances': leave_balances_query,
            'page_obj': page_obj,  
            'leave_types': leave_types,
            'recent_leave_requests': recent_leave_requests,
            'year': year,
            'years': range(get_current_date().year - 2, get_current_date().year + 3),
            'search_query': search_query,
        }

        return render(request, 'attendance/employee_leave_balances.html', context)

    def create_leave_request(self, request):
        employee_id = request.POST.get('employee')
        leave_type_id = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        is_half_day = request.POST.get('is_half_day') == 'on'
        half_day_period = request.POST.get('half_day_period', 'MORNING')
        emergency_contact = request.POST.get('emergency_contact_during_leave', '')
        handover_notes = request.POST.get('handover_notes', '')

        try:
            employee = User.objects.get(id=employee_id)
            leave_type = LeaveType.objects.get(id=leave_type_id)

            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

            leave_request = LeaveRequest(
                employee=employee,
                leave_type=leave_type,
                start_date=start_date_obj,
                end_date=end_date_obj,
                reason=reason,
                is_half_day=is_half_day,
                half_day_period=half_day_period if is_half_day else None,
                emergency_contact_during_leave=emergency_contact,
                handover_notes=handover_notes
            )

            if 'medical_certificate' in request.FILES:
                leave_request.medical_certificate = request.FILES['medical_certificate']

            leave_request.save()

            messages.success(request, 'Leave request submitted successfully')
            return redirect('attendance:leave_request_list')

        except User.DoesNotExist:
            messages.error(request, 'Employee not found')
        except LeaveType.DoesNotExist:
            messages.error(request, 'Leave type not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating leave request: {str(e)}')

        return redirect('attendance:leave_request_list')

    def create_leave_type(self, request):
        name = request.POST.get('name')
        category = request.POST.get('category')
        description = request.POST.get('description', '')
        days_allowed_per_year = request.POST.get('days_allowed_per_year')
        max_consecutive_days = request.POST.get('max_consecutive_days', '')
        min_notice_days = request.POST.get('min_notice_days')
        requires_approval = request.POST.get('requires_approval') == 'on'
        requires_medical_certificate = request.POST.get('requires_medical_certificate') == 'on'
        is_paid = request.POST.get('is_paid') == 'on'
        carry_forward_allowed = request.POST.get('carry_forward_allowed') == 'on'
        carry_forward_max_days = request.POST.get('carry_forward_max_days', '')
        applicable_after_probation_only = request.POST.get('applicable_after_probation_only') == 'on'
        gender_specific = request.POST.get('gender_specific')

        try:
            leave_type = LeaveType(
                name=name,
                category=category,
                description=description,
                days_allowed_per_year=int(days_allowed_per_year),
                min_notice_days=int(min_notice_days),
                requires_approval=requires_approval,
                requires_medical_certificate=requires_medical_certificate,
                is_paid=is_paid,
                carry_forward_allowed=carry_forward_allowed,
                applicable_after_probation_only=applicable_after_probation_only,
                gender_specific=gender_specific,
                created_by=request.user
            )

            if max_consecutive_days:
                leave_type.max_consecutive_days = int(max_consecutive_days)

            if carry_forward_allowed and carry_forward_max_days:
                leave_type.carry_forward_max_days = int(carry_forward_max_days)

            leave_type.save()

            messages.success(request, f'Leave type "{name}" created successfully')
            return redirect('attendance:leave_type_detail', type_id=leave_type.id)

        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating leave type: {str(e)}')

        return redirect('attendance:leave_type_list')

    def initialize_leave_balances(self, request):
        year = request.POST.get('year', get_current_date().year)
        leave_type_id = request.POST.get('leave_type')
        employee_ids = request.POST.getlist('employees')

        try:
            year = int(year)
            leave_type = LeaveType.objects.get(id=leave_type_id)

            created_count = 0
            for employee_id in employee_ids:
                try:
                    employee = User.objects.get(id=employee_id)

                    balance_exists = LeaveBalance.objects.filter(
                        employee=employee,
                        leave_type=leave_type,
                        year=year
                    ).exists()

                    if not balance_exists:
                        LeaveBalance.objects.create(
                            employee=employee,
                            leave_type=leave_type,
                            year=year,
                            allocated_days=leave_type.days_allowed_per_year,
                            updated_by=request.user
                        )
                        created_count += 1
                except User.DoesNotExist:
                    continue

            if created_count > 0:
                messages.success(request, f'Successfully initialized {created_count} leave balances')
            else:
                messages.info(request, 'No new leave balances were created')

        except LeaveType.DoesNotExist:
            messages.error(request, 'Leave type not found')
        except ValueError:
            messages.error(request, 'Invalid year')
        except Exception as e:
            messages.error(request, f'Error initializing leave balances: {str(e)}')

        return redirect('attendance:leave_balance_list')

    def update_leave_type(self, request):
        leave_type_id = request.POST.get('leave_type_id')

        try:
            leave_type = LeaveType.objects.get(id=leave_type_id)

            leave_type.name = request.POST.get('name')
            leave_type.category = request.POST.get('category')
            leave_type.description = request.POST.get('description', '')
            leave_type.days_allowed_per_year = int(request.POST.get('days_allowed_per_year'))

            max_consecutive_days = request.POST.get('max_consecutive_days', '')
            if max_consecutive_days:
                leave_type.max_consecutive_days = int(max_consecutive_days)
            else:
                leave_type.max_consecutive_days = None

            leave_type.min_notice_days = int(request.POST.get('min_notice_days'))
            leave_type.requires_approval = request.POST.get('requires_approval') == 'on'
            leave_type.requires_medical_certificate = request.POST.get('requires_medical_certificate') == 'on'
            leave_type.is_paid = request.POST.get('is_paid') == 'on'
            leave_type.carry_forward_allowed = request.POST.get('carry_forward_allowed') == 'on'

            carry_forward_max_days = request.POST.get('carry_forward_max_days', '')
            if carry_forward_max_days:
                leave_type.carry_forward_max_days = int(carry_forward_max_days)
            else:
                leave_type.carry_forward_max_days = None

            leave_type.applicable_after_probation_only = request.POST.get('applicable_after_probation_only') == 'on'
            leave_type.gender_specific = request.POST.get('gender_specific')
            leave_type.is_active = request.POST.get('is_active') == 'on'

            leave_type.save()

            messages.success(request, f'Leave type "{leave_type.name}" updated successfully')
            return redirect('attendance:leave_type_detail', type_id=leave_type.id)

        except LeaveType.DoesNotExist:
            messages.error(request, 'Leave type not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating leave type: {str(e)}')

        return redirect('attendance:leave_type_list')

    def approve_leave_request(self, request):
        request_id = request.POST.get('leave_request_id')

        try:
            leave_request = LeaveRequest.objects.get(id=request_id)

            if leave_request.status != 'PENDING':
                messages.error(request, 'Only pending leave requests can be approved')
                return redirect('attendance:leave_request_detail', request_id=leave_request.id)

            leave_request.approve(request.user)

            messages.success(request, f'Leave request for {leave_request.employee.get_full_name()} has been approved')

        except LeaveRequest.DoesNotExist:
            messages.error(request, 'Leave request not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error approving leave request: {str(e)}')

        return redirect('attendance:leave_request_list')

    def reject_leave_request(self, request):
        request_id = request.POST.get('leave_request_id')
        rejection_reason = request.POST.get('rejection_reason')

        try:
            leave_request = LeaveRequest.objects.get(id=request_id)

            if leave_request.status != 'PENDING':
                messages.error(request, 'Only pending leave requests can be rejected')
                return redirect('attendance:leave_request_detail', request_id=leave_request.id)

            if not rejection_reason:
                messages.error(request, 'Rejection reason is required')
                return redirect('attendance:leave_request_detail', request_id=leave_request.id)

            leave_request.reject(request.user, rejection_reason)

            messages.success(request, f'Leave request for {leave_request.employee.get_full_name()} has been rejected')

        except LeaveRequest.DoesNotExist:
            messages.error(request, 'Leave request not found')
        except ValidationError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error rejecting leave request: {str(e)}')

        return redirect('attendance:leave_request_list')

    def cancel_leave_request(self, request):
        request_id = request.POST.get('leave_request_id')

        try:
            leave_request = LeaveRequest.objects.get(id=request_id)

            if not leave_request.can_be_cancelled:
                messages.error(request, 'This leave request cannot be cancelled')
                return redirect('attendance:leave_request_detail', request_id=leave_request.id)

            if leave_request.status == 'APPROVED':
                try:
                    leave_balance = LeaveBalance.objects.get(
                        employee=leave_request.employee,
                        leave_type=leave_request.leave_type,
                        year=leave_request.start_date.year
                    )
                    leave_balance.add_leave(leave_request.total_days)
                except LeaveBalance.DoesNotExist:
                    pass

            leave_request.status = 'CANCELLED'
            leave_request.save(update_fields=['status'])

            messages.success(request, 'Leave request has been cancelled')

        except LeaveRequest.DoesNotExist:
            messages.error(request, 'Leave request not found')
        except Exception as e:
            messages.error(request, f'Error cancelling leave request: {str(e)}')

        return redirect('attendance:leave_request_list')

    def update_leave_balance(self, request):
        balance_id = request.POST.get('balance_id')
        employee_id = request.POST.get('employee')
        leave_type_id = request.POST.get('leave_type')
        year = request.POST.get('year')
        adjustment_days = request.POST.get('adjustment_days', '0')
        adjustment_reason = request.POST.get('reason', '')
        
        try:
            year = int(year)
            adjustment = Decimal(adjustment_days)
            
            if balance_id:
                leave_balance = LeaveBalance.objects.get(id=balance_id)
            else:
                employee = User.objects.get(id=employee_id)
                leave_type = LeaveType.objects.get(id=leave_type_id)
                
                leave_balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=year,
                    defaults={
                        'allocated_days': leave_type.days_allowed_per_year,
                        'updated_by': request.user
                    }
                )
            
            previous_adjustment = leave_balance.adjustment_days
            
            leave_balance.adjustment_days = adjustment
            leave_balance.updated_by = request.user
            leave_balance.save(update_fields=['adjustment_days', 'updated_by', 'last_updated'])

            AuditHelper.log_attendance_change(
                user=request.user,
                action="LEAVE_BALANCE_ADJUSTED",
                employee=leave_balance.employee,
                attendance_date=get_current_date(),
                changes={
                    'leave_type': leave_balance.leave_type.name,
                    'previous_adjustment': float(previous_adjustment),
                    'new_adjustment': float(adjustment),
                    'reason': adjustment_reason
                }
            )
            
            messages.success(request, f'Leave balance for {leave_balance.employee.get_full_name()} has been updated')
            
        except User.DoesNotExist:
            messages.error(request, 'Employee not found')
        except LeaveType.DoesNotExist:
            messages.error(request, 'Leave type not found')
        except LeaveBalance.DoesNotExist:
            messages.error(request, 'Leave balance not found')
        except ValueError:
            messages.error(request, 'Invalid year')
        except (InvalidOperation, decimal.InvalidOperation):
            messages.error(request, 'Invalid adjustment value')
        except Exception as e:
            messages.error(request, f'Error updating leave balance: {str(e)}')
        
        return redirect('attendance:leave_balance_list')
