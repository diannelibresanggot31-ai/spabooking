from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Payment
from bookings.models import Booking


def is_admin_or_staff(user):
    """Check if user is admin or staff"""
    return getattr(user, 'role', None) in ['admin', 'staff'] or user.is_staff


@login_required
@user_passes_test(is_admin_or_staff)
def verify_payment_direct(request, payment_id):
    """Verify payment directly - for admin panel"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Update payment status
    payment.status = 'verified'
    payment.verified_by = request.user
    payment.verified_at = timezone.now()
    payment.save()
    
    # Update booking status
    booking = payment.booking
    booking.status = 'verify'  # Changed from 'confirmed' to 'verify' to match your model
    booking.save()
    
    messages.success(request, f'✅ Payment #{payment_id} verified! Booking confirmed.')
    
    # Redirect back to admin panel
    return redirect('/admin-panel/')


@login_required
@user_passes_test(is_admin_or_staff)
def verify_payment_admin(request, payment_id):
    """Verify payment from Django admin panel"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        payment.status = 'verified'
        payment.verified_at = timezone.now()
        payment.verified_by = request.user
        payment.save()
        
        # Update booking status
        booking = payment.booking
        if booking.status == 'pending':
            booking.status = 'verify'
            booking.save()
        
        messages.success(request, f'✅ Payment #{payment_id} verified successfully!')
    
    return redirect('/admin/payments/payment/')


@user_passes_test(lambda u: u.is_staff)
def payment_list(request):
    """Payment list restricted to staff users."""
    payments = Payment.objects.select_related('booking__customer', 'booking__service').all().order_by('-created_at')
    return render(request, 'payments/payment_list.html', {'payments': payments})


@user_passes_test(lambda u: u.is_staff)
def staff_payment_overview(request):
    """Staff-only overview of payments."""
    # Show upcoming bookings (pending or confirmed) with payment info so staff
    # can see who still needs to pay and who already paid.
    bookings = (
        Booking.objects.filter(status__in=['pending', 'verify'])
        .select_related('payment', 'customer', 'service')
        .order_by('-booking_date', '-booking_time')
    )
    
    # Add payment status to each booking
    for booking in bookings:
        try:
            booking.payment_status = booking.payment.status if hasattr(booking, 'payment') else 'pending'
        except:
            booking.payment_status = 'pending'
    
    return render(request, 'payments/staff_payment_overview.html', {'bookings': bookings})