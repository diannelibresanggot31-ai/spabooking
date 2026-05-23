from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Payment
from bookings.models import Booking


@login_required
@user_passes_test(lambda u: getattr(u, 'role', None) in ['admin', 'staff'])
def verify_payment_direct(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = 'verified'
    payment.verified_by = request.user
    payment.verified_at = timezone.now()
    payment.save()
    payment.booking.status = 'confirmed'
    payment.booking.save()
    messages.success(request, f'Payment #{payment_id} verified! Booking confirmed.')
    return redirect('/admin-dashboard/')


@user_passes_test(lambda u: u.is_staff)
def payment_list(request):
    """Payment list restricted to staff users."""
    payments = Payment.objects.select_related('booking').all().order_by('-created_at')
    return render(request, 'payments/payment_list.html', {'payments': payments})


@user_passes_test(lambda u: u.is_staff)
def staff_payment_overview(request):
    """Staff-only overview of payments."""
    # Show upcoming bookings (pending or confirmed) with payment info so staff
    # can see who still needs to pay and who already paid.
    bookings = (
        Booking.objects.filter(status__in=['pending', 'verify', 'confirmed'])
        .select_related('payment', 'customer')
        .order_by('-booking_date', '-booking_time')
    )
    return render(request, 'payments/staff_payment_overview.html', {'bookings': bookings})