from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Booking

@login_required
def booking_list(request):
    bookings = Booking.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'bookings/booking_list.html', {'bookings': bookings})