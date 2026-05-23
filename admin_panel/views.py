from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from datetime import datetime, timedelta
from accounts.models import User
from services.models import Room, Category
from bookings.models import Booking
from payments.models import Payment
from staff.models import StaffAttendance, ChatMessage, StaffSchedule

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


@login_required
@user_passes_test(is_admin)
def dashboard(request):
    today = timezone.now().date()
    
    pending_payments_count = Payment.objects.filter(status='pending').count()
    pending_payments_list = Payment.objects.filter(status='pending').select_related('booking__customer', 'booking__service').order_by('-created_at')[:6]
    
    recent_staff_messages = ChatMessage.objects.filter(
        sender__role='staff', 
        receiver__role='admin', 
        deleted_by_sender=False, 
        deleted_by_receiver=False
    ).order_by('-timestamp')[:3]
    
    recent_customer_messages = ChatMessage.objects.filter(
        sender__role='customer', 
        receiver__role='admin', 
        deleted_by_sender=False, 
        deleted_by_receiver=False
    ).order_by('-timestamp')[:3]
    
    total_unread = ChatMessage.objects.filter(
        receiver__role='admin', 
        is_read=False, 
        deleted_by_sender=False, 
        deleted_by_receiver=False
    ).count()

    context = {
        'active_page': 'dashboard',
        'today_bookings': Booking.objects.filter(booking_date=today).count(),
        'today_revenue': Payment.objects.filter(status='verified', created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0,
        'active_staff': StaffAttendance.objects.filter(date=today, check_in__isnull=False, check_out__isnull=True).count(),
        'available_rooms': Room.objects.filter(is_available=True).count(),
        'total_bookings': Booking.objects.count(),
        'total_customers': User.objects.filter(role='customer').count(),
        'total_revenue': Payment.objects.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0,
        'pending_payments_count': pending_payments_count,
        'pending_payments_list': pending_payments_list,
        'recent_staff_messages': recent_staff_messages,
        'recent_customer_messages': recent_customer_messages,
        'total_unread': total_unread,
        'recent_bookings': Booking.objects.select_related('customer', 'service', 'room').order_by('-created_at')[:10],
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def staff_attendance_review(request):
    """Admin can review staff attendance, verify photos, and update status"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    staff_filter = request.GET.get('staff', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    attendances = StaffAttendance.objects.select_related('staff').all().order_by('-date', '-check_in')
    
    if status_filter:
        attendances = attendances.filter(status=status_filter)
    if staff_filter:
        attendances = attendances.filter(staff_id=staff_filter)
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    
    # Calculate counts
    present_count = attendances.filter(status='present').count()
    late_count = attendances.filter(status='late').count()
    absent_count = attendances.filter(status='absent').count()
    pending_count = attendances.filter(status='pending').count()
    
    # Handle status update
    if request.method == 'POST':
        attendance_id = request.POST.get('attendance_id')
        new_status = request.POST.get('new_status')
        admin_notes = request.POST.get('admin_notes', '')
        
        attendance = get_object_or_404(StaffAttendance, id=attendance_id)
        old_status = attendance.status
        attendance.status = new_status
        attendance.admin_notes = admin_notes
        attendance.verified_by = request.user
        attendance.verified_at = timezone.now()
        attendance.save()
        
        messages.success(request, f'Attendance for {attendance.staff.username} updated from {old_status.upper()} to {new_status.upper()}')
        return redirect('admin_panel:staff_attendance_review')
    
    staff_members = User.objects.filter(role='staff')
    
    context = {
        'active_page': 'staff_attendance',
        'attendances': attendances,
        'staff_members': staff_members,
        'staff_filter': staff_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'pending_count': pending_count,
    }
    return render(request, 'admin_panel/staff_attendance_review.html', context)


@login_required
@user_passes_test(is_admin)
def delete_attendance(request, attendance_id):
    """Delete an attendance record - Silent delete, no message"""
    if request.method == 'POST':
        attendance = get_object_or_404(StaffAttendance, id=attendance_id)
        attendance.delete()
        # No success message - silent delete
    return redirect('admin_panel:staff_attendance_review')


# ==================== STAFF SCHEDULE ====================

@login_required
@user_passes_test(is_admin)
def staff_schedule_list(request):
    """View all staff schedules"""
    schedules = StaffSchedule.objects.select_related('staff').all().order_by('-date', 'staff__username')
    
    # Get filter parameters
    staff_id = request.GET.get('staff')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if staff_id:
        schedules = schedules.filter(staff_id=staff_id)
    if date_from:
        schedules = schedules.filter(date__gte=date_from)
    if date_to:
        schedules = schedules.filter(date__lte=date_to)
    
    staff_members = User.objects.filter(role='staff')
    
    context = {
        'active_page': 'staff_schedule_list',
        'schedules': schedules,
        'staff_members': staff_members,
        'selected_staff': staff_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'admin_panel/staff_schedule.html', context)

@login_required
@user_passes_test(is_admin)
def staff_schedule_add(request):
    """Add a new staff schedule"""
    if request.method == 'POST':
        staff_id = request.POST.get('staff')
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        is_available = request.POST.get('is_available') == 'on'
        
        if staff_id and date and start_time and end_time:
            StaffSchedule.objects.create(
                staff_id=staff_id,
                date=date,
                start_time=start_time,
                end_time=end_time,
                is_available=is_available
            )
            messages.success(request, 'Schedule added successfully.')
        else:
            messages.error(request, 'Please fill all required fields.')
        return redirect('admin_panel:staff_schedule_list')
    
    staff_members = User.objects.filter(role='staff')
    context = {
        'active_page': 'staff_schedule',
        'staff_members': staff_members,
    }
    return render(request, 'admin_panel/staff_schedule_form.html', context)


@login_required
@user_passes_test(is_admin)
def staff_schedule_edit(request, schedule_id):
    """Edit a staff schedule"""
    schedule = get_object_or_404(StaffSchedule, id=schedule_id)
    
    if request.method == 'POST':
        schedule.staff_id = request.POST.get('staff')
        schedule.date = request.POST.get('date')
        schedule.start_time = request.POST.get('start_time')
        schedule.end_time = request.POST.get('end_time')
        schedule.is_available = request.POST.get('is_available') == 'on'
        schedule.save()
        messages.success(request, 'Schedule updated successfully.')
        return redirect('admin_panel:staff_schedule_list')
    
    staff_members = User.objects.filter(role='staff')
    context = {
        'active_page': 'staff_schedule',
        'schedule': schedule,
        'staff_members': staff_members,
    }
    return render(request, 'admin_panel/staff_schedule_form.html', context)


@login_required
@user_passes_test(is_admin)
def staff_schedule_delete(request, schedule_id):
    """Delete a staff schedule"""
    if request.method == 'POST':
        schedule = get_object_or_404(StaffSchedule, id=schedule_id)
        schedule.delete()
        messages.success(request, 'Schedule deleted successfully.')
    return redirect('admin_panel:staff_schedule_list')


# ==================== REVENUE ====================

@login_required
@user_passes_test(is_admin)
def revenue(request):
    today = timezone.now().date()
    current_month = today.strftime('%B %Y')
    current_date = today.strftime('%b %d, %Y')
    
    # Calculate monthly total
    monthly_total = Payment.objects.filter(
        status='verified',
        created_at__year=today.year,
        created_at__month=today.month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Calculate weekly total
    week_ago = today - timedelta(days=7)
    weekly_total = Payment.objects.filter(
        status='verified',
        created_at__date__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Daily data with day names and percentages
    daily_data = []
    daily_labels = []
    daily_values = []
    week_total = 0
    
    for i in range(6, -1, -1):
        date_obj = today - timedelta(days=i)
        daily_revenue = Payment.objects.filter(
            status='verified', 
            created_at__date=date_obj
        ).aggregate(total=Sum('amount'))['total'] or 0
        week_total += daily_revenue
        daily_labels.append(date_obj.strftime('%b %d'))
        daily_values.append(float(daily_revenue))
        daily_data.append({
            'date': date_obj.strftime('%Y-%m-%d'),
            'day_name': date_obj.strftime('%A'),
            'revenue': daily_revenue,
            'percentage': 0
        })
    
    # Calculate percentages
    for item in daily_data:
        if week_total > 0:
            item['percentage'] = round((item['revenue'] / week_total) * 100, 1)
    
    # Weekly data
    weekly_labels = []
    weekly_values = []
    for i in range(3, -1, -1):
        week_start = today - timedelta(days=7 * i + 7)
        week_end = today - timedelta(days=7 * i)
        weekly_revenue = Payment.objects.filter(
            status='verified',
            created_at__date__gte=week_start,
            created_at__date__lt=week_end
        ).aggregate(total=Sum('amount'))['total'] or 0
        weekly_labels.append(f'Week {4-i}')
        weekly_values.append(float(weekly_revenue))
    
    # Monthly data with growth
    monthly_data = []
    monthly_labels = []
    monthly_values = []
    prev_revenue = None
    
    for i in range(11, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        monthly_revenue = Payment.objects.filter(
            status='verified',
            created_at__year=month_date.year,
            created_at__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        growth = 0
        if prev_revenue is not None and prev_revenue > 0:
            growth = round(((monthly_revenue - prev_revenue) / prev_revenue) * 100, 1)
        
        monthly_labels.append(month_date.strftime('%b'))
        monthly_values.append(float(monthly_revenue))
        monthly_data.append({
            'month': month_date.strftime('%B'),
            'month_name': month_date.strftime('%b'),
            'year': month_date.year,
            'revenue': monthly_revenue,
            'growth': growth if i < 11 else None
        })
        prev_revenue = monthly_revenue
    
    # Yearly data with growth
    yearly_data = []
    prev_year_revenue = None
    
    for year in range(today.year - 4, today.year + 1):
        yearly_revenue = Payment.objects.filter(
            status='verified', 
            created_at__year=year
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        growth = 0
        if prev_year_revenue is not None and prev_year_revenue > 0:
            growth = round(((yearly_revenue - prev_year_revenue) / prev_year_revenue) * 100, 1)
        
        yearly_data.append({
            'year': year,
            'revenue': yearly_revenue,
            'growth': growth if year > today.year - 4 else None
        })
        prev_year_revenue = yearly_revenue
    
    context = {
        'active_page': 'revenue',
        'total_revenue': Payment.objects.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0,
        'monthly_total': monthly_total,
        'weekly_total': weekly_total,
        'today_revenue': Payment.objects.filter(status='verified', created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0,
        'current_month': current_month,
        'current_date': current_date,
        'daily_data': daily_data,
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'weekly_labels': weekly_labels,
        'weekly_values': weekly_values,
        'monthly_labels': monthly_labels,
        'monthly_values': monthly_values,
        'monthly_data': monthly_data,
        'yearly_data': yearly_data,
    }
    return render(request, 'admin_panel/revenue.html', context)


# ==================== BOOKINGS ====================

@login_required
@user_passes_test(is_admin)
def bookings(request):
    bookings_list = Booking.objects.select_related('customer', 'service', 'room').all().order_by('-created_at')
    
    # Attach payment to each booking
    bookings_with_payment = []
    for booking in bookings_list:
        payment = Payment.objects.filter(booking=booking).first()
        bookings_with_payment.append({'booking': booking, 'payment': payment})
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        if status_filter == 'verify':
            bookings_with_payment = [b for b in bookings_with_payment if b['booking'].status == 'verify']
        elif status_filter == 'complete':
            bookings_with_payment = [b for b in bookings_with_payment if b['booking'].status == 'complete']
        elif status_filter == 'pending':
            bookings_with_payment = [b for b in bookings_with_payment if b['booking'].status == 'pending']
        elif status_filter == 'cancelled':
            bookings_with_payment = [b for b in bookings_with_payment if b['booking'].status == 'cancelled']
    
    context = {
        'active_page': 'bookings',
        'bookings': bookings_with_payment,
        'status_filter': status_filter
    }
    return render(request, 'admin_panel/bookings.html', context)


@login_required
@user_passes_test(is_admin)
def update_booking_status(request, booking_id):
    """Admin: Update booking status"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_panel:bookings')
    
    new_status = request.POST.get('new_status')
    
    valid_statuses = ['pending', 'verify', 'complete', 'cancelled']
    
    if new_status not in valid_statuses:
        messages.error(request, f'Invalid status: {new_status}')
        return redirect('admin_panel:bookings')
    
    old_status = booking.status
    
    if old_status == new_status:
        if new_status == 'verify':
            status_display = 'VERIFIED'
        elif new_status == 'complete':
            status_display = 'COMPLETE SESSION'
        elif new_status == 'pending':
            status_display = 'PENDING'
        elif new_status == 'cancelled':
            status_display = 'CANCELLED'
        else:
            status_display = new_status.upper()
        
        messages.info(request, f'ℹ️ Booking #{booking.id} is already {status_display}. No changes were made.')
        return redirect('admin_panel:bookings')
    
    booking.status = new_status
    booking.save()
    
    payment = Payment.objects.filter(booking=booking).first()
    
    storage = messages.get_messages(request)
    storage.used = True
    
    if new_status == 'verify':
        if payment and payment.payment_method == 'gcash':
            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.save()
        messages.success(request, f'✅ Booking #{booking.id} has been VERIFIED. Customer can now view their receipt.')
    
    elif new_status == 'complete':
        if payment and payment.payment_method == 'cash':
            payment.status = 'verified'
            payment.save()
        messages.success(request, f'🎉 Booking #{booking.id} has been marked as COMPLETE SESSION.')
    
    elif new_status == 'cancelled':
        messages.warning(request, f'❌ Booking #{booking.id} has been CANCELLED.')
    
    else:
        if new_status == 'pending':
            status_display = 'PENDING'
        else:
            status_display = new_status.upper()
        messages.info(request, f'📋 Booking #{booking.id} status updated to {status_display}.')
    
    return redirect('admin_panel:bookings')


# ==================== CHAT ====================

@login_required
@user_passes_test(is_admin)
def chat_with_staff(request):
    staff_members = User.objects.filter(role='staff')
    selected_staff_id = request.GET.get('staff')
    messages_list = []
    selected_staff = None
    
    if selected_staff_id:
        try:
            selected_staff = User.objects.get(id=selected_staff_id, role='staff')
            
            messages_list = ChatMessage.objects.filter(
                (Q(sender=request.user) & Q(receiver=selected_staff)) |
                (Q(sender=selected_staff) & Q(receiver=request.user))
            ).exclude(
                Q(sender=request.user, deleted_by_sender=True) |
                Q(receiver=request.user, deleted_by_receiver=True)
            ).order_by('timestamp')
            
            messages_list.filter(receiver=request.user, is_read=False).update(is_read=True)
            
            for staff in staff_members:
                staff.unread_count = ChatMessage.objects.filter(
                    sender=staff, 
                    receiver=request.user, 
                    is_read=False,
                    deleted_by_sender=False,
                    deleted_by_receiver=False
                ).count()
                
        except User.DoesNotExist:
            selected_staff = None
    
    context = {
        'active_page': 'chat',
        'staff_members': staff_members,
        'selected_staff': selected_staff,
        'chat_messages': messages_list,
    }
    return render(request, 'admin_panel/chat.html', context)


@login_required
@user_passes_test(is_admin)
def customer_inquiries(request):
    customers = User.objects.filter(role='customer')
    selected_customer_id = request.GET.get('customer')
    messages_list = []
    selected_customer = None

    if selected_customer_id:
        try:
            selected_customer = User.objects.get(id=selected_customer_id, role='customer')
            
            messages_list = ChatMessage.objects.filter(
                (Q(sender=request.user) & Q(receiver=selected_customer)) |
                (Q(sender=selected_customer) & Q(receiver=request.user))
            ).exclude(
                Q(sender=request.user, deleted_by_sender=True) |
                Q(receiver=request.user, deleted_by_receiver=True)
            ).order_by('timestamp')
            
            messages_list.filter(receiver=request.user, is_read=False).update(is_read=True)
            
            for customer in customers:
                customer.unread_count = ChatMessage.objects.filter(
                    sender=customer, 
                    receiver=request.user, 
                    is_read=False,
                    deleted_by_sender=False,
                    deleted_by_receiver=False
                ).count()
                
        except User.DoesNotExist:
            selected_customer = None

    context = {
        'active_page': 'inquiries',
        'customers': customers,
        'selected_customer': selected_customer,
        'chat_messages': messages_list,
    }
    return render(request, 'admin_panel/customer_inquiries.html', context)


@login_required
@user_passes_test(is_admin)
def send_chat_message(request):
    if request.method == 'POST':
        receiver_id = request.POST.get('receiver_id')
        message_text = request.POST.get('message', '').strip()
        
        if receiver_id and message_text:
            try:
                receiver = User.objects.get(id=receiver_id)
                ChatMessage.objects.create(
                    sender=request.user,
                    receiver=receiver,
                    message=message_text
                )
                messages.success(request, f'Message sent to {receiver.username}')
            except User.DoesNotExist:
                messages.error(request, 'User not found')
        
        if receiver and receiver.role == 'customer':
            return redirect(f'/admin-panel/customer-inquiries/?customer={receiver_id}')
        return redirect(f'/admin-panel/chat/?staff={receiver_id}')
    
    return redirect('admin_panel:chat_with_staff')


@login_required
@user_passes_test(is_admin)
def delete_message(request, message_id):
    """Delete message for the current user (soft delete)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
    
    message = get_object_or_404(ChatMessage, id=message_id)
    
    if request.user not in [message.sender, message.receiver]:
        return JsonResponse({'success': False, 'error': 'You cannot delete this message.'}, status=403)
    
    message.delete_for_user(request.user)
    
    return JsonResponse({'success': True, 'message': 'Message deleted.'})


@login_required
@user_passes_test(is_admin)
def clear_chat_history(request, user_id):
    """Clear entire chat history with a user (soft delete all messages for admin)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
    
    other_user = get_object_or_404(User, id=user_id)
    
    messages_list = ChatMessage.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    )
    
    count = 0
    for msg in messages_list:
        if msg.delete_for_user(request.user):
            count += 1
    
    return JsonResponse({'success': True, 'message': f'Cleared {count} messages from your chat history with {other_user.username}.'})