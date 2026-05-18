# bookings/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_number', 'customer_link', 'booking_date', 'total_amount', 'status_badge')
    # REMOVED: list_filter = ('status', 'booking_date', 'payment_method')
    search_fields = ('booking_number', 'customer__username', 'customer__email')
    list_per_page = 25
    # REMOVED: date_hierarchy = 'booking_date'
    
    def customer_link(self, obj):
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.customer.id, obj.customer.username)
    
    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'confirmed': '#28a745', 'completed': '#17a2b8', 'cancelled': '#dc3545'}
        return format_html('<span style="background:{}; color:white; padding:4px 12px; border-radius:20px">{}</span>', 
                          colors.get(obj.status, '#6c757d'), obj.status.upper())