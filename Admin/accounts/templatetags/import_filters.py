from django import template

register = template.Library()


@register.filter
def split_row_number(value):
    if ":" in value:
        return value.split(":")[0]
    return value


@register.filter
def get_error_message(value):
    if ":" in value:
        parts = value.split(":", 1)
        if len(parts) > 1:
            return parts[1].strip()
    return value
