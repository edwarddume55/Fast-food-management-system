from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def money(value):
    try:
        return f"{settings.CURRENCY} {Decimal(value):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return ""


@register.filter
def qty(value):
    """Decimal without trailing zeros: 12.500 -> 12.5, 3.000 -> 3"""
    try:
        return format(Decimal(value).normalize(), "f")
    except (InvalidOperation, TypeError, ValueError):
        return ""
