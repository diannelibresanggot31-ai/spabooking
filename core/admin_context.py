# core/admin_context.py
from django.db.models import Sum
from django.utils import timezone
from bookings.models import Booking
from payments.models import Payment
from services.models import Service, Room

def admin_dashboard_context(request):
    if request.path.startswith('/admin/'):
        try:
            # Stats
            total_bookings = Booking.objects.count()
            total_revenue = Payment.objects.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0
            pending_bookings = Booking.objects.filter(status='pending').count()
            pending_payments = Payment.objects.filter(status='pending').count()
            
            # Pending payments with images
            pending_payments_list = Payment.objects.filter(status='pending').select_related('booking', 'booking__customer')[:15]
            
            # Recent bookings
            recent_bookings = Booking.objects.select_related('customer', 'service', 'package', 'room').order_by('-created_at')[:15]
            
            # Services
            services_list = Service.objects.filter(is_active=True)[:10]
            
            # Rooms
            rooms = Room.objects.all()
            total_rooms = rooms.count()
            available_rooms = rooms.filter(is_available=True).count()
            
            return {
                'total_bookings': total_bookings,
                'total_revenue': int(total_revenue) if total_revenue else 0,
                'pending_bookings': pending_bookings,
                'pending_payments': pending_payments,
                'pending_payments_list': pending_payments_list,
                'recent_bookings': recent_bookings,
                'services_list': services_list,
                'total_rooms': total_rooms,
                'available_rooms': available_rooms,
            }
        except Exception as e:
            return {}
    return {}