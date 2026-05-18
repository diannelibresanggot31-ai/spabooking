from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import models
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
from .models import StaffAttendance, ChatMessage, StaffSchedule
from accounts.models import User
from payments.models import Payment
from bookings.models import Booking

@login_required
def staff_dashboard(request):
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    today = timezone.now().date()

    # Get today's bookings
    from bookings.models import Booking
    bookings = Booking.objects.filter(booking_date=today).order_by('booking_time')

    # Get attendance records
    attendances = StaffAttendance.objects.filter(staff=user).order_by('-date')[:30]

    # Calculate stats
    this_month = timezone.now().replace(day=1)
    monthly_attendances = StaffAttendance.objects.filter(
        staff=user,
        date__gte=this_month
    )

    present_count = monthly_attendances.filter(status='present').count()
    late_count = monthly_attendances.filter(status='late').count()
    absent_count = monthly_attendances.filter(status='absent').count()

    # Get today's attendance
    today_attendance = StaffAttendance.objects.filter(staff=user, date=today).first()

    selected_partner_id = request.GET.get('conv_with')
    admin_user = User.objects.filter(role='admin').first()
    customer_users = User.objects.filter(role='customer').order_by('username')
    selected_chat_partner = None

    if selected_partner_id:
        try:
            selected_chat_partner = User.objects.get(id=selected_partner_id, role__in=['admin', 'customer'])
        except User.DoesNotExist:
            selected_chat_partner = None

    if not selected_chat_partner:
        selected_chat_partner = admin_user or customer_users.first()

    if selected_chat_partner:
        chat_messages = ChatMessage.objects.filter(
            (models.Q(sender=user) & models.Q(receiver=selected_chat_partner)) |
            (models.Q(sender=selected_chat_partner) & models.Q(receiver=user))
        ).order_by('timestamp')
        unread_messages_count = ChatMessage.objects.filter(receiver=user, is_read=False).count()
        ChatMessage.objects.filter(sender=selected_chat_partner, receiver=user, is_read=False).update(is_read=True)
    else:
        chat_messages = ChatMessage.objects.none()
        unread_messages_count = 0

    chat_partners = []
    if admin_user:
        chat_partners.append(admin_user)
    chat_partners.extend(customer_users)

    context = {
        'bookings': bookings,
        'attendances': attendances,
        'my_present_count': present_count,
        'my_late_count': late_count,
        'my_absent_count': absent_count,
        'today_attendance': today_attendance,
        'user': user,
        'chat_partners': chat_partners,
        'selected_chat_partner': selected_chat_partner,
        'chat_messages': chat_messages,
        'unread_messages_count': unread_messages_count,
        'admin_user': admin_user,
    }

    return render(request, 'core/staff_dashboard.html', context)

@login_required
def attendance(request):
    if request.user.role != 'staff':
        return redirect('home')

    today = timezone.now().date()
    
    # Check if today is a working day (Monday=0 to Saturday=5, Sunday=6 is off)
    is_working_day = today.weekday() < 6  # Monday to Saturday
    
    # Get or create today's attendance record
    attendance, created = StaffAttendance.objects.get_or_create(
        staff=request.user,
        date=today,
        defaults={'status': 'absent'}
    )

    attendance_history = StaffAttendance.objects.filter(
        staff=request.user
    ).order_by('-date')[:10]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'check_in':
            if attendance.check_in:
                messages.warning(request, 'You have already checked in today.')
            elif not is_working_day:
                messages.error(request, 'Today is Sunday - no work scheduled.')
            else:
                photo = request.FILES.get('photo')
                if not photo:
                    messages.error(request, 'Please upload a photo to confirm check-in.')
                else:
                    attendance.check_in = timezone.now()
                    # Late time: check in after 8:00 AM
                    check_in_time = attendance.check_in.time()
                    from datetime import time as dt_time
                    late_threshold = dt_time(8, 0)
                    attendance.status = 'late' if check_in_time > late_threshold else 'present'
                    attendance.photo = photo
                    attendance.save()
                    messages.success(request, f'Check-in successful. Status: {attendance.get_status_display()}')
        elif action == 'check_out':
            if not attendance.check_in:
                messages.error(request, 'Cannot check out before checking in.')
            elif attendance.check_out:
                messages.warning(request, 'You have already checked out today.')
            else:
                attendance.check_out = timezone.now()
                attendance.save()
                messages.success(request, 'Check-out successful.')
        elif action == 'mark_absent':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, 'Reason is required when marking absent.')
            else:
                attendance.status = 'absent'
                attendance.reason = reason
                attendance.save()
                messages.success(request, 'You have been marked absent.')
        return redirect('staff:attendance')

    if not is_working_day and attendance.status == 'absent' and not attendance.check_in:
        display_status = 'Closed'
    else:
        display_status = attendance.get_status_display()

    show_checkin_form = is_working_day and not attendance.check_in

    context = {
        'attendance': attendance,
        'display_status': display_status,
        'show_checkin_form': show_checkin_form,
        'is_working_day': is_working_day,
        'today_day': today.strftime('%A'),
        'working_hours': {
            'morning_start': '8:00 AM',
            'morning_end': '11:30 AM',
            'break_start': '12:00 PM',
            'break_end': '1:00 PM',
            'afternoon_start': '1:00 PM',
            'afternoon_end': '6:00 PM',
            'late_threshold': '8:00 AM',
        },
        'working_days': 'Monday to Saturday',
        'closed_day': 'Sunday',
        'attendance_history': attendance_history,
    }
    return render(request, 'staff/attendance.html', context)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def attendance_checkin(request):
    user = request.user
    today = timezone.now().date()
    
    # Get or create today's attendance
    attendance, created = StaffAttendance.objects.get_or_create(
        staff=user, 
        date=today,
        defaults={'status': 'absent'}
    )
    
    action = request.POST.get('action')
    
    if action == 'check_in':
        if attendance.check_in:
            return JsonResponse({'error': 'Already checked in today'}, status=400)
        
        # Handle photo upload
        photo = request.FILES.get('photo')
        if photo:
            attendance.photo = photo
        
        attendance.check_in = timezone.now()
        check_in_time = attendance.check_in.time()
        from datetime import time as dt_time
        late_threshold = dt_time(8, 0)
        attendance.status = 'late' if check_in_time > late_threshold else 'present'
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'time_in': attendance.check_in.strftime('%I:%M %p'),
            'status': attendance.status
        })
    
    elif action == 'check_out':
        if not attendance.check_in:
            return JsonResponse({'error': 'Must check in first'}, status=400)
        if attendance.check_out:
            return JsonResponse({'error': 'Already checked out today'}, status=400)
        
        attendance.check_out = timezone.now()
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'time_out': attendance.check_out.strftime('%I:%M %p')
        })
    
    elif action == 'mark_absent':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            return JsonResponse({'error': 'Reason is required for absence'}, status=400)
        
        attendance.status = 'absent'
        attendance.reason = reason
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'status': 'absent',
            'reason': reason
        })
    
    return JsonResponse({'error': 'Invalid action'}, status=400)

@login_required
def chat_messages(request):
    user = request.user
    other_user_id = request.GET.get('with')
    
    if not other_user_id:
        return JsonResponse({'error': 'Missing user ID'}, status=400)
    
    try:
        other_user = User.objects.get(id=other_user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Get messages between these users
    messages = ChatMessage.objects.filter(
        (models.Q(sender=user) & models.Q(receiver=other_user)) |
        (models.Q(sender=other_user) & models.Q(receiver=user))
    ).order_by('timestamp')
    
    # Mark messages as read
    messages.filter(receiver=user, is_read=False).update(is_read=True)
    
    messages_data = [{
        'id': msg.id,
        'sender_id': msg.sender.id,
        'sender_username': msg.sender.username,
        'message': msg.message,
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'is_read': msg.is_read
    } for msg in messages]
    
    return JsonResponse({'messages': messages_data})

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def send_message(request):
    user = request.user
    receiver_id = request.POST.get('receiver_id')
    message_text = request.POST.get('message', '').strip()
    
    if not receiver_id or not message_text:
        return JsonResponse({'error': 'Missing data'}, status=400)
    
    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    
    # Create message
    message = ChatMessage.objects.create(
        sender=user,
        receiver=receiver,
        message=message_text
    )
    
    return JsonResponse({
        'success': True,
        'message_id': message.id,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    })

@login_required
def staff_payments(request):
    """View for staff to see payment information."""
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    
    # Get filter parameters
    filter_status = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()
    
    # Start with all payments
    payments = Payment.objects.select_related(
        'booking__customer',
        'booking__service',
        'verified_by'
    ).order_by('-created_at')
    
    # Filter by status
    if filter_status != 'all':
        payments = payments.filter(status=filter_status)
    
    # Search by customer name or booking number
    if search_query:
        payments = payments.filter(
            Q(booking__customer__username__icontains=search_query) |
            Q(booking__customer__first_name__icontains=search_query) |
            Q(booking__customer__last_name__icontains=search_query) |
            Q(booking__booking_number__icontains=search_query)
        )
    
    # Calculate statistics
    total_payments = Payment.objects.all()
    pending_count = total_payments.filter(status='pending').count()
    verified_count = total_payments.filter(status='verified').count()
    rejected_count = total_payments.filter(status='rejected').count()
    
    verified_total = total_payments.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0
    pending_total = total_payments.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'payments': payments,
        'pending_count': pending_count,
        'verified_count': verified_count,
        'rejected_count': rejected_count,
        'verified_total': verified_total,
        'pending_total': pending_total,
        'filter_status': filter_status,
        'search_query': search_query,
    }
    
    return render(request, 'staff/payments.html', context)

@login_required
def staff_schedule(request):
    """View for staff to see their work schedule."""
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    
    # Get staff's schedules for the next 30 days
    today = timezone.now().date()
    schedules = StaffSchedule.objects.filter(
        staff=user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    # Get upcoming bookings for this staff member's dates
    booking_dates = set()
    for schedule in schedules:
        booking_dates.add(schedule.date)
    
    upcoming_bookings = Booking.objects.filter(
        booking_date__in=booking_dates,
        status__in=['pending', 'confirmed']
    ).select_related('customer', 'service').order_by('booking_date', 'booking_time')
    
    # Build a month calendar for the current month
    import calendar
    year = today.year
    month = today.month
    cal = calendar.Calendar(firstweekday=6)  # week starts on Sunday
    month_days = list(cal.itermonthdates(year, month))

    # Group bookings by day for the month
    from collections import defaultdict
    bookings_by_day = defaultdict(list)
    month_bookings = Booking.objects.filter(booking_date__year=year, booking_date__month=month).select_related('customer', 'service')
    for b in month_bookings:
        bookings_by_day[b.booking_date.day].append(b)
    # counts as simple mapping for template lookups
    bookings_count_by_day = {day: len(listings) for day, listings in bookings_by_day.items()}
    # prepare calendar cells aligned with month_days
    calendar_cells = []
    for d in month_days:
        day_num = d.day
        calendar_cells.append({
            'date': d,
            'in_month': (d.month == month),
            'day': day_num,
            'booking_count': bookings_count_by_day.get(day_num, 0),
            'bookings': bookings_by_day.get(day_num, []),
        })

    context = {
        'schedules': schedules,
        'upcoming_bookings': upcoming_bookings,
        'today': today,
        'calendar_cells': calendar_cells,
        'bookings_by_day': dict(bookings_by_day),
        'calendar_year': year,
        'calendar_month': month,
    }
    
    return render(request, 'staff/schedule.html', context)

@login_required
def staff_logout(request):
    """Logout staff member and redirect to home."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')