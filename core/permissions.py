from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def is_manager(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=settings.MANAGER_GROUP).exists()


def manager_required(view):
    """Login required AND user must be a superuser or in the Manager group."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
