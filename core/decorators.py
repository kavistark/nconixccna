from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Allow superusers, staff, or users with admin role in profile
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view
