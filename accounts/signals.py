from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import UserActivityLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log user login events to track user activity."""
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip_address:
        ip_address = ip_address.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR')
    
    UserActivityLog.objects.create(
        user=user,
        action='login',
        ip_address=ip_address
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout events to track user activity."""
    if user:
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
        if ip_address:
            ip_address = ip_address.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        UserActivityLog.objects.create(
            user=user,
            action='logout',
            ip_address=ip_address
        )
