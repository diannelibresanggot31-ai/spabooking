from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Sum
from .models import StaffAttendance, ChatMessage, StaffSchedule
from accounts.models import User
from bookings.models import Booking
from payments.models import Payment


def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


@login_required
def staff_dashboard(request):
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    
    today = timezone.now().date()
    
    # Get today's bookings
    bookings = Booking.objects.filter(booking_date=today).select_related('customer', 'service', 'package', 'room').order_by('booking_time')
    
    # Calculate today's statistics
    total_today = bookings.count()
    confirmed_today = bookings.filter(status='verify').count()
    pending_today = bookings.filter(status='pending').count()
    
    # Get attendance records
    attendances = StaffAttendance.objects.filter(staff=user).order_by('-date')[:30]
    
    # Calculate stats for this month
    this_month = timezone.now().replace(day=1)
    monthly_attendances = StaffAttendance.objects.filter(staff=user, date__gte=this_month)
    
    present_count = monthly_attendances.filter(status='present').count()
    late_count = monthly_attendances.filter(status='late').count()
    absent_count = monthly_attendances.filter(status='absent').count()
    pending_count = monthly_attendances.filter(status='pending').count()
    
    # Get today's attendance
    today_attendance = StaffAttendance.objects.filter(staff=user, date=today).first()
    
    # Chat functionality
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
    
    # Initialize chat_partners list
    chat_partners = []
    if admin_user:
        admin_user.unread_count = ChatMessage.objects.filter(sender=admin_user, receiver=user, is_read=False).count()
        chat_partners.append(admin_user)
    for customer in customer_users:
        customer.unread_count = ChatMessage.objects.filter(sender=customer, receiver=user, is_read=False).count()
        chat_partners.append(customer)
    
    if selected_chat_partner:
        chat_messages = ChatMessage.objects.filter(
            (Q(sender=user) & Q(receiver=selected_chat_partner)) |
            (Q(sender=selected_chat_partner) & Q(receiver=user))
        ).order_by('timestamp')
        unread_messages_count = ChatMessage.objects.filter(receiver=user, is_read=False).count()
        ChatMessage.objects.filter(sender=selected_chat_partner, receiver=user, is_read=False).update(is_read=True)
    else:
        chat_messages = ChatMessage.objects.none()
        unread_messages_count = 0
    
    context = {
        'bookings': bookings,
        'attendances': attendances,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'pending_count': pending_count,
        'today_attendance': today_attendance,
        'user': user,
        'chat_partners': chat_partners,
        'selected_chat_partner': selected_chat_partner,
        'chat_messages': chat_messages,
        'unread_messages_count': unread_messages_count,
        'admin_user': admin_user,
        'total_today': total_today,
        'confirmed_today': confirmed_today,
        'pending_today': pending_today,
    }
    
    return render(request, 'staff/dashboard.html', context)


@login_required
def attendance(request):
    if request.user.role != 'staff':
        return redirect('home')
    
    today = timezone.now().date()
    is_working_day = today.weekday() < 6
    
    attendance, created = StaffAttendance.objects.get_or_create(
        staff=request.user,
        date=today,
        defaults={'status': 'pending'}
    )
    
    attendance_history = StaffAttendance.objects.filter(
        staff=request.user
    ).order_by('-date')[:30]
    
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
                    messages.error(request, 'Please upload a photo to confirm Time In.')
                else:
                    attendance.check_in = timezone.now()
                    attendance.status = 'pending'
                    attendance.photo = photo
                    attendance.save()
                    messages.success(request, '✅ Time In recorded. Status is PENDING - waiting for admin verification.')
                    
        elif action == 'check_out':
            if not attendance.check_in:
                messages.error(request, 'Cannot Time Out before Time In.')
            elif attendance.check_out:
                messages.warning(request, 'You have already timed out today.')
            else:
                attendance.check_out = timezone.now()
                attendance.save()
                messages.success(request, '✅ Time Out successful.')
                
        elif action == 'mark_absent':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, 'Reason is required when marking absent.')
            else:
                attendance.status = 'pending'
                attendance.reason = reason
                attendance.save()
                messages.info(request, 'Your absence has been recorded and is pending admin approval.')
                
        return redirect('staff:attendance')
    
    show_checkin_form = is_working_day and not attendance.check_in
    
    if attendance.status == 'pending':
        display_status = '⏳ PENDING (Waiting for admin verification)'
    elif attendance.status == 'present':
        display_status = '✅ PRESENT'
    elif attendance.status == 'late':
        display_status = '⚠️ LATE'
    elif attendance.status == 'absent':
        display_status = '❌ ABSENT'
    elif attendance.status == 'half_day':
        display_status = '⏳ HALF DAY'
    else:
        display_status = attendance.get_status_display()
    
    # Get today's schedule
    today_schedule = StaffSchedule.objects.filter(staff=request.user, date=today).first()
    
    context = {
        'attendance': attendance,
        'display_status': display_status,
        'show_checkin_form': show_checkin_form,
        'is_working_day': is_working_day,
        'today_day': today.strftime('%A'),
        'today_schedule': today_schedule,
        'working_hours': {
            'morning_start': '8:00 AM',
            'morning_end': '11:30 AM',
            'break_start': '12:00 PM',
            'break_end': '1:00 PM',
            'afternoon_start': '1:00 PM',
            'afternoon_end': '6:00 PM',
            'morning_late_threshold': '8:00 AM',
            'afternoon_late_threshold': '1:00 PM',
        },
        'working_days': 'Monday to Saturday',
        'closed_day': 'Sunday',
        'attendance_history': attendance_history,
    }
    return render(request, 'staff/attendance.html', context)


@login_required
def staff_schedule(request):
    """Staff view their work schedule"""
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    
    import calendar
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    today = timezone.now().date()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    # Get staff's schedules
    schedules = StaffSchedule.objects.filter(
        staff=user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    # Get upcoming bookings (services assigned to this staff)
    upcoming_bookings = Booking.objects.filter(
        booking_date__gte=today,
        status__in=['pending', 'verify']
    ).select_related('customer', 'service', 'room').order_by('booking_date', 'booking_time')
    
    # Build calendar
    cal = calendar.Calendar(firstweekday=6)
    month_days = list(cal.itermonthdates(year, month))
    
    schedule_dates = set(schedules.values_list('date', flat=True))
    
    bookings_by_day = defaultdict(int)
    for booking in upcoming_bookings:
        bookings_by_day[booking.booking_date] += 1
    
    calendar_cells = []
    for date_obj in month_days:
        calendar_cells.append({
            'date': date_obj,
            'day': date_obj.day,
            'is_today': date_obj == today,
            'in_month': date_obj.month == month,
            'has_schedule': date_obj in schedule_dates,
            'booking_count': bookings_by_day.get(date_obj, 0),
        })
    
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    context = {
        'schedules': schedules,
        'upcoming_bookings': upcoming_bookings,
        'today': today,
        'calendar_cells': calendar_cells,
        'month': month,
        'year': year,
        'month_name': month_names[month - 1],
    }
    return render(request, 'staff/schedule.html', context)


@login_required
@user_passes_test(is_admin)
def admin_staff_schedules(request):
    """Admin view to manage staff schedules"""
    from datetime import datetime, timedelta
    import calendar
    
    staff_members = User.objects.filter(role='staff')
    selected_staff_id = request.GET.get('staff')
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    
    schedules = StaffSchedule.objects.select_related('staff').all().order_by('date', 'staff__username')
    
    if selected_staff_id:
        schedules = schedules.filter(staff_id=selected_staff_id)
    if selected_date:
        schedules = schedules.filter(date=selected_date)
    
    # Handle add/edit/delete
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            staff_id = request.POST.get('staff_id')
            date = request.POST.get('date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            is_available = request.POST.get('is_available') == 'on'
            notes = request.POST.get('notes', '')
            
            if staff_id and date and start_time and end_time:
                schedule, created = StaffSchedule.objects.get_or_create(
                    staff_id=staff_id,
                    date=date,
                    defaults={
                        'start_time': start_time,
                        'end_time': end_time,
                        'is_available': is_available,
                        'notes': notes
                    }
                )
                if not created:
                    schedule.start_time = start_time
                    schedule.end_time = end_time
                    schedule.is_available = is_available
                    schedule.notes = notes
                    schedule.save()
                    messages.success(request, 'Schedule updated successfully.')
                else:
                    messages.success(request, 'Schedule added successfully.')
            else:
                messages.error(request, 'Please fill all required fields.')
                
        elif action == 'delete':
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(StaffSchedule, id=schedule_id)
            schedule.delete()
            messages.success(request, 'Schedule deleted successfully.')
        
        return redirect('admin_panel:staff_schedules')
    
    # Get calendar data for the selected month
    try:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except:
        date_obj = timezone.now().date()
    
    month = date_obj.month
    year = date_obj.year
    cal = calendar.Calendar(firstweekday=6)
    month_days = list(cal.itermonthdates(year, month))
    
    context = {
        'active_page': 'staff_schedules',
        'staff_members': staff_members,
        'schedules': schedules,
        'selected_staff_id': selected_staff_id,
        'selected_date': selected_date,
        'calendar_days': month_days,
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
    }
    return render(request, 'admin_panel/staff_schedules.html', context)


@login_required
def staff_payments(request):
    user = request.user
    if user.role != 'staff':
        return redirect('home')
    
    filter_status = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '').strip()
    
    payments = Payment.objects.select_related(
        'booking__customer',
        'booking__service',
        'verified_by'
    ).order_by('-created_at')
    
    if filter_status != 'all':
        payments = payments.filter(status=filter_status)
    
    if search_query:
        payments = payments.filter(
            Q(booking__customer__username__icontains=search_query) |
            Q(booking__customer__first_name__icontains=search_query) |
            Q(booking__customer__last_name__icontains=search_query) |
            Q(booking__booking_number__icontains=search_query)
        )
    
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


@require_http_methods(["POST"])
@login_required
def attendance_checkin(request):
    user = request.user
    today = timezone.now().date()
    
    attendance, created = StaffAttendance.objects.get_or_create(
        staff=user, 
        date=today,
        defaults={'status': 'pending'}
    )
    
    action = request.POST.get('action')
    
    if action == 'check_in':
        if attendance.check_in:
            return JsonResponse({'error': 'Already checked in today'}, status=400)
        
        photo = request.FILES.get('photo')
        if photo:
            attendance.photo = photo
        
        attendance.check_in = timezone.now()
        attendance.status = 'pending'
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'time_in': attendance.check_in.strftime('%I:%M %p'),
            'status': 'pending'
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
        
        attendance.status = 'pending'
        attendance.reason = reason
        attendance.save()
        
        return JsonResponse({
            'success': True,
            'status': 'pending',
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
    
    messages = ChatMessage.objects.filter(
        (Q(sender=user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=user))
    ).order_by('timestamp')
    
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
def staff_logout(request):
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')