from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Sum
from payments import views as payment_views
from payments.models import Payment
from bookings.models import Booking
from services.models import Room
from staff.models import StaffAttendance, ChatMessage
from core import views as core_views  # ADD THIS LINE - Keep everything else


# ── Custom Admin Site ──────────────────────────────────────────────────────────
# Overrides the built-in logout so it always lands on the customer home page.
class CustomAdminSite(admin.AdminSite):
    index_template = 'admin/index.html'

    def logout(self, request, extra_context=None):
        logout(request)
        return redirect('/')   # ← sends admin to customer home after logout

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        today = timezone.now().date()
        extra_context.update({
            'pending_payments_list': Payment.objects.filter(status='pending').select_related('booking__customer', 'booking__service').order_by('-created_at')[:6],
            'total_bookings': Booking.objects.count(),
            'today_revenue': Payment.objects.filter(status='verified', created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0,
            'pending_payments_count': Payment.objects.filter(status='pending').count(),
            'active_staff': StaffAttendance.objects.filter(date=today, check_in__isnull=False, check_out__isnull=True).count(),
            'available_rooms': Room.objects.filter(is_available=True).count(),
            'recent_bookings': Booking.objects.select_related('customer', 'service').order_by('-created_at')[:6],
        })
        return super().index(request, extra_context)


custom_admin_site = CustomAdminSite(name='custom_admin')

# Copy all registered models from the default admin to the custom one
# (keeps all your existing @admin.register decorators working)
for model, model_admin in admin.site._registry.items():
    try:
        custom_admin_site.register(model, type(model_admin))
    except admin.sites.AlreadyRegistered:
        pass
# ──────────────────────────────────────────────────────────────────────────────


urlpatterns = [
    path('admin/', custom_admin_site.urls),   # ← use custom admin
    path('', include('core.urls')),  # Keep this - includes home, login, etc.
    path('bookings/', include('bookings.urls')),
    path('payments/', include('payments.urls')),
    path('staff/', include('staff.urls')),
    path('admin-panel/', include('admin_panel.urls')),
    path('admin/payments/payment/<int:payment_id>/verify/', payment_views.verify_payment_direct, name='verify_payment_direct'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)