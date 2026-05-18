# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_link', 'payment_method', 'amount_display', 'gcash_reference', 'proof_link')
    # REMOVED: list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('gcash_reference', 'booking__customer__username', 'booking__booking_number')
    list_per_page = 20
    
    def booking_link(self, obj):
        return format_html('<a href="/admin/bookings/booking/{}/change/">Booking #{} - {}</a>', 
                          obj.booking.id, obj.booking.id, obj.booking.customer.username)
    
    def amount_display(self, obj):
        return f"₱{obj.amount}"
    
    def proof_link(self, obj):
        if obj.proof_image:
            return format_html('<a href="{}" target="_blank">📸 View GCash Proof</a>', obj.proof_image.url)
        return "No proof"