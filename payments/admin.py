# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_link', 'payment_method', 'amount_display', 'status_badge', 'gcash_reference', 'proof_link', 'verify_button')
    list_filter = ('status', 'payment_method', 'created_at')  # Added back - useful for filtering
    search_fields = ('gcash_reference', 'booking__customer__username', 'booking__booking_number')
    list_per_page = 20
    readonly_fields = ('created_at', 'verified_at')
    
    def booking_link(self, obj):
        return format_html('<a href="/admin/bookings/booking/{}/change/">Booking #{} - {}</a>', 
                          obj.booking.id, obj.booking.id, obj.booking.customer.username)
    booking_link.short_description = 'Booking'
    
    def amount_display(self, obj):
        return f"₱{obj.amount}"
    amount_display.short_description = 'Amount'
    
    def proof_link(self, obj):
        if obj.proof_image:
            return format_html('<a href="{}" target="_blank" style="color: #C8522A;">📸 View GCash Proof</a>', obj.proof_image.url)
        return "No proof"
    proof_link.short_description = 'Payment Proof'
    
    def status_badge(self, obj):
        if obj.status == 'verified':
            return format_html('<span style="background: #28a745; color: white; padding: 4px 10px; border-radius: 20px;">✅ Verified</span>')
        elif obj.status == 'pending':
            return format_html('<span style="background: #ffc107; color: #2C2015; padding: 4px 10px; border-radius: 20px;">⏳ Pending</span>')
        elif obj.status == 'rejected':
            return format_html('<span style="background: #dc3545; color: white; padding: 4px 10px; border-radius: 20px;">❌ Rejected</span>')
        return obj.status
    status_badge.short_description = 'Status'
    
    def verify_button(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="{}" style="background: #28a745; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-weight: 600;">✓ Verify Payment</a>',
                reverse('admin:verify_payment', args=[obj.id])
            )
        return format_html('<span style="color: #28a745;">✓ Verified</span>')
    verify_button.short_description = 'Action'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:payment_id>/verify/', self.admin_site.admin_view(self.verify_payment_view), name='verify_payment'),
        ]
        return custom_urls + urls
    
    def verify_payment_view(self, request, payment_id):
        """Verify payment from admin panel"""
        payment = self.get_object(request, payment_id)
        
        if payment:
            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.verified_by = request.user
            payment.save()
            
            # Update booking status
            booking = payment.booking
            if booking.status == 'pending':
                booking.status = 'verify'
                booking.save()
            
            messages.success(request, f'✅ Payment #{payment_id} verified successfully! Booking confirmed.')
        else:
            messages.error(request, f'Payment #{payment_id} not found.')
        
        return redirect('/admin/payments/payment/')
    
    actions = ['verify_selected_payments']
    
    def verify_selected_payments(self, request, queryset):
        """Bulk verify selected payments"""
        updated = 0
        for payment in queryset:
            if payment.status == 'pending':
                payment.status = 'verified'
                payment.verified_at = timezone.now()
                payment.verified_by = request.user
                payment.save()
                
                # Update booking status
                booking = payment.booking
                if booking.status == 'pending':
                    booking.status = 'verify'
                    booking.save()
                
                updated += 1
        
        messages.success(request, f'✅ {updated} payment(s) verified successfully!')
    verify_selected_payments.short_description = 'Verify selected payments'