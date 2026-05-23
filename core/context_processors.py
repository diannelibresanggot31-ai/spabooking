# core/context_processors.py
from django.db.models import Sum
from django.utils import timezone
from bookings.models import Booking
from payments.models import Payment
from services.models import Service, Room, Category
from staff.models import StaffAttendance
from accounts.models import User

def admin_dashboard_context(request):
    """Add admin dashboard data to context for admin pages"""
    if request.path.startswith('/admin/'):
        try:
            today = timezone.now().date()
            
            # Basic stats
            total_bookings = Booking.objects.count()
            total_revenue = Payment.objects.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0
            pending_bookings = Booking.objects.filter(status='pending').count()
            pending_payments = Payment.objects.filter(status='pending').count()
            total_customers = User.objects.filter(role='customer').count()
            
            # Today's stats
            today_bookings = Booking.objects.filter(booking_date=today).count()
            today_revenue = Payment.objects.filter(status='verified', created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0
            active_staff = StaffAttendance.objects.filter(date=today, check_in__isnull=False, check_out__isnull=True).count()
            
            # Pending payments list
            pending_payments_list = Payment.objects.filter(status='pending').select_related('booking', 'booking__customer').order_by('-created_at')[:15]
            
            # Recent bookings
            recent_bookings = Booking.objects.select_related('customer', 'service', 'package', 'room').order_by('-created_at')[:15]
            
            # Services and rooms stats
            services_count = Service.objects.filter(is_active=True).count()
            total_rooms = Room.objects.count()
            available_rooms = Room.objects.filter(is_available=True).count()
            
            # Categories count
            categories_count = Category.objects.filter(is_active=True).count()
            
            return {
                'total_bookings': total_bookings,
                'total_revenue': int(total_revenue) if total_revenue else 0,
                'pending_bookings': pending_bookings,
                'pending_payments': pending_payments,
                'total_customers': total_customers,
                'today_bookings': today_bookings,
                'today_revenue': int(today_revenue) if today_revenue else 0,
                'active_staff': active_staff,
                'pending_payments_list': pending_payments_list,
                'recent_bookings': recent_bookings,
                'services_count': services_count,
                'total_rooms': total_rooms,
                'available_rooms': available_rooms,
                'categories_count': categories_count,
            }
        except Exception as e:
            print(f"Error in admin_dashboard_context: {e}")
            return {}
    return {}