from django import template
from datetime import datetime, date

register = template.Library()


@register.filter
def time_diff(end_time, start_time):
    if not end_time or not start_time:
        return "--:--:--"
    in_dt = datetime.combine(date.today(), start_time)
    out_dt = datetime.combine(date.today(), end_time)
    duration = out_dt - in_dt
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
