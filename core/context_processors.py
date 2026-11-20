from django.conf import settings
from django.db.models import F

from .permissions import is_manager


def app_context(request):
    ctx = {"BUSINESS_NAME": settings.BUSINESS_NAME, "CURRENCY": settings.CURRENCY}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        ctx["is_manager"] = is_manager(user)
        if ctx["is_manager"]:
            from inventory.models import Ingredient

            ctx["low_stock_count"] = Ingredient.objects.filter(
                is_active=True, reorder_level__gt=0, stock__lte=F("reorder_level")
            ).count()
    return ctx
