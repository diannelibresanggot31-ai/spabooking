from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from datetime import datetime, timedelta
from accounts.models import User, UserActivityLog
from services.models import Service, Package, Room
from bookings.models import Booking
from payments.models import Payment
from staff.models import StaffAttendance, StaffSchedule, ChatMessage

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def admin_base(request):
    return render(request, 'admin_panel/base.html')

@login_required
@user_passes_test(is_admin)
def dashboard(request):
    today = timezone.now().date()
    
    pending_payments_count = Payment.objects.filter(status='pending').count()
    pending_payments_list = Payment.objects.filter(status='pending').select_related('booking__customer', 'booking__service').order_by('-created_at')[:6]
    recent_staff_messages = ChatMessage.objects.filter(sender__role='staff', receiver__role='admin').order_by('-timestamp')[:3]
    recent_customer_messages = ChatMessage.objects.filter(sender__role='customer', receiver__role='admin').order_by('-timestamp')[:3]
    total_unread = ChatMessage.objects.filter(receiver__role='admin', is_read=False).count()

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
def user_history(request):
    # Get all logs with pagination
    logs = UserActivityLog.objects.select_related('user').all().order_by('-timestamp')[:500]
    
    # Get login counts per user
    login_counts = UserActivityLog.objects.filter(action='login').values('user__username', 'user__role').annotate(
        login_count=Count('id')
    ).order_by('-login_count')[:20]
    
    # Get today's activity
    today = timezone.now().date()
    today_logins = UserActivityLog.objects.filter(action='login', timestamp__date=today).count()
    today_logouts = UserActivityLog.objects.filter(action='logout', timestamp__date=today).count()
    
    # Get recent activity (last 10 actions)
    recent_activity = UserActivityLog.objects.select_related('user').all().order_by('-timestamp')[:10]
    
    # Get currently online users (logged in but not logged out today)
    from django.db.models import Q, Exists, OuterRef, Max
    latest_login = UserActivityLog.objects.filter(
        user_id=OuterRef('user_id'),
        action='login',
        timestamp__date=today
    ).order_by('-timestamp')
    
    latest_logout = UserActivityLog.objects.filter(
        user_id=OuterRef('user_id'),
        action='logout',
        timestamp__date=today
    ).order_by('-timestamp')
    
    online_users = UserActivityLog.objects.filter(
        action='login',
        timestamp__date=today
    ).values('user').annotate(
        last_login=Max('timestamp')
    ).exclude(
        user__in=UserActivityLog.objects.filter(
            action='logout',
            timestamp__date=today,
            timestamp__gt=OuterRef('last_login')
        ).values('user')
    )
    
    context = {
        'active_page': 'user_history',
        'logs': logs,
        'login_counts': login_counts,
        'today_logins': today_logins,
        'today_logouts': today_logouts,
        'recent_activity': recent_activity,
        'total_logs': UserActivityLog.objects.count(),
    }
    return render(request, 'admin_panel/user_history.html', context)

@login_required
@user_passes_test(is_admin)
def user_info(request):
    users = User.objects.all().order_by('-date_joined')
    context = {'active_page': 'user_info', 'users': users}
    return render(request, 'admin_panel/user_info.html', context)

@login_required
@user_passes_test(is_admin)
def staff_attendance(request):
    today = timezone.now().date()
    
    # Get all staff with their attendance for today
    all_staff = User.objects.filter(role='staff')
    attendances = []
    
    for staff in all_staff:
        attendance, created = StaffAttendance.objects.get_or_create(staff=staff, date=today)
        attendances.append({
            'staff': staff,
            'attendance': attendance
        })
    
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()
        
        staff = get_object_or_404(User, id=staff_id, role='staff')
        attendance, created = StaffAttendance.objects.get_or_create(staff=staff, date=today)
        
        if action == 'check_in' and not attendance.check_in:
            attendance.check_in = timezone.now()
            attendance.status = 'present'
            attendance.save()
            messages.success(request, f'{staff.username} checked in')
        elif action == 'check_out' and not attendance.check_out:
            attendance.check_out = timezone.now()
            attendance.save()
            messages.success(request, f'{staff.username} checked out')
        elif action == 'mark_absent':
            if not reason:
                messages.error(request, 'Reason is required when marking staff as absent')
            else:
                attendance.status = 'absent'
                attendance.reason = reason
                attendance.save()
                messages.success(request, f'{staff.username} marked as absent: {reason}')
        return redirect('admin_panel:staff_attendance')
    
    context = {
        'active_page': 'staff_attendance',
        'staff_members': all_staff,
        'attendances': attendances,
        'now': timezone.now(),
    }
    return render(request, 'admin_panel/staff_attendance.html', context)

@login_required
@user_passes_test(is_admin)
def edit_staff(request):
    all_staff = User.objects.filter(role='staff')
    
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        if staff_id:
            staff = get_object_or_404(User, id=staff_id, role='staff')
            staff.username = username
            staff.email = email
            staff.phone = phone
            if password:
                staff.set_password(password)
            staff.save()
            messages.success(request, f'Staff "{username}" updated')
        else:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                phone=phone,
                role='staff'
            )
            messages.success(request, f'Staff "{username}" created')
        return redirect('admin_panel:edit_staff')
    
    context = {'active_page': 'edit_staff', 'staff_members': all_staff}
    return render(request, 'admin_panel/edit_staff.html', context)

@login_required
@user_passes_test(is_admin)
def delete_staff(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff')
    staff.delete()
    messages.success(request, 'Staff deleted')
    return redirect('admin_panel:edit_staff')

@login_required
@user_passes_test(is_admin)
def revenue(request):
    today = timezone.now().date()
    
    # Daily data (last 7 days)
    daily_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        revenue = Payment.objects.filter(status='verified', created_at__date=date).aggregate(total=Sum('amount'))['total'] or 0
        daily_data.append({'date': date.strftime('%Y-%m-%d'), 'revenue': float(revenue)})
    
    # Monthly data (last 12 months)
    monthly_data = []
    for i in range(11, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30*i)
        revenue = Payment.objects.filter(
            status='verified',
            created_at__year=month_date.year,
            created_at__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_data.append({'month': month_date.strftime('%B %Y'), 'revenue': float(revenue)})
    
    # Yearly data
    yearly_data = []
    for year in range(today.year - 4, today.year + 1):
        revenue = Payment.objects.filter(status='verified', created_at__year=year).aggregate(total=Sum('amount'))['total'] or 0
        yearly_data.append({'year': year, 'revenue': float(revenue)})
    
    context = {
        'active_page': 'revenue',
        'daily_data': daily_data,
        'monthly_data': monthly_data,
        'yearly_data': yearly_data,
    }
    return render(request, 'admin_panel/revenue.html', context)

@login_required
@user_passes_test(is_admin)
def services(request):
    services_list = Service.objects.all().order_by('category', 'name')
    
    if request.method == 'POST':
        service_id = request.POST.get('service_id')
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        duration = request.POST.get('duration_minutes')
        description = request.POST.get('description')
        
        if service_id:
            service = get_object_or_404(Service, id=service_id)
            service.name = name
            service.category = category
            service.price = price
            service.duration_minutes = duration
            service.description = description
            if request.FILES.get('image'):
                service.image = request.FILES['image']
            service.save()
            messages.success(request, 'Service updated')
        else:
            Service.objects.create(
                name=name, category=category, price=price,
                duration_minutes=duration, description=description,
                image=request.FILES.get('image')
            )
            messages.success(request, 'Service added')
        return redirect('admin_panel:services')
    
    context = {'active_page': 'services', 'services': services_list}
    return render(request, 'admin_panel/services.html', context)

@login_required
@user_passes_test(is_admin)
def delete_service(request, service_id):
    Service.objects.filter(id=service_id).delete()
    messages.success(request, 'Service deleted')
    return redirect('admin_panel:services')
@login_required
@user_passes_test(is_admin)
def packages(request):
    packages_list = Package.objects.all()
    all_services = Service.objects.filter(is_active=True)
    
    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        name = request.POST.get('name')
        price = request.POST.get('price')
        description = request.POST.get('description')
        service_ids = request.POST.getlist('services')
        
        if package_id:
            package = get_object_or_404(Package, id=package_id)
            package.name = name
            package.price = price
            package.description = description
            package.save()
            package.services.set(service_ids)
            messages.success(request, 'Package updated')
        else:
            package = Package.objects.create(name=name, price=price, description=description)
            package.services.set(service_ids)
            messages.success(request, 'Package added')
        return redirect('admin_panel:packages')
    
    context = {
        'active_page': 'packages',
        'packages': packages_list,
        'services': all_services
    }
    return render(request, 'admin_panel/packages.html', context)


@login_required
@user_passes_test(is_admin)
def delete_package(request, package_id):
    Package.objects.filter(id=package_id).delete()
    messages.success(request, 'Package deleted')
    return redirect('admin_panel:packages')

@login_required
@user_passes_test(is_admin)
def rooms(request):
    rooms_list = Room.objects.all()
    
    if request.method == 'POST':
        room_id = request.POST.get('room_id')
        room_number = request.POST.get('room_number')
        room_type = request.POST.get('room_type')
        is_available = request.POST.get('is_available') == 'on'
        
        if room_id:
            room = get_object_or_404(Room, id=room_id)
            room.room_number = room_number
            room.room_type = room_type
            room.is_available = is_available
            room.save()
            messages.success(request, 'Room updated')
        else:
            Room.objects.create(room_number=room_number, room_type=room_type, is_available=is_available)
            messages.success(request, 'Room added')
        return redirect('admin_panel:rooms')
    
    context = {'active_page': 'rooms', 'rooms': rooms_list}
    return render(request, 'admin_panel/rooms.html', context)

@login_required
@user_passes_test(is_admin)
def delete_room(request, room_id):
    Room.objects.filter(id=room_id).delete()
    messages.success(request, 'Room deleted')
    return redirect('admin_panel:rooms')

@login_required
@user_passes_test(is_admin)
def bookings(request):
    bookings_list = Booking.objects.select_related('customer', 'service', 'room', 'payment').all().order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        # support legacy status values 'confirmed' -> show under 'verify', 'completed' -> 'complete'
        if status_filter == 'verify':
            bookings_list = bookings_list.filter(status__in=['verify', 'confirmed'])
        elif status_filter == 'complete':
            bookings_list = bookings_list.filter(status__in=['complete', 'completed'])
        else:
            bookings_list = bookings_list.filter(status=status_filter)
    
    context = {
        'active_page': 'bookings',
        'bookings': bookings_list,
        'status_filter': status_filter
    }
    return render(request, 'admin_panel/bookings.html', context)

@login_required
@user_passes_test(is_admin)
def update_booking_status(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    new_status = request.POST.get('new_status') or request.GET.get('new_status')
    allowed_admin_statuses = {'pending', 'verify', 'complete'}
    if new_status in allowed_admin_statuses:
        booking.status = new_status
        booking.save()

        # If admin marks a booking as complete, ensure a Payment exists and is marked verified
        if new_status == 'complete':
            try:
                payment = booking.payment
                if payment.amount != booking.total_amount:
                    payment.amount = booking.total_amount
                if payment.status != 'verified':
                    payment.status = 'verified'
                    payment.verified_by = request.user
                    payment.verified_at = timezone.now()
                payment.save()
            except Payment.DoesNotExist:
                Payment.objects.create(
                    booking=booking,
                    amount=booking.total_amount,
                    payment_method=booking.payment_method or 'cash',
                    status='verified',
                    verified_by=request.user,
                    verified_at=timezone.now()
                )

        # No persistent flash message here; the updated status is shown immediately after redirect.
    return redirect('admin_panel:bookings')

@login_required
@user_passes_test(is_admin)
def payments(request):
    payments_list = Payment.objects.select_related('booking', 'booking__customer').all().order_by('-created_at')
    # Also include bookings that chose cash and have no Payment record yet
    unpaid_cash_bookings = Booking.objects.filter(payment__isnull=True, payment_method='cash').select_related('customer').order_by('-created_at')
    context = {
        'active_page': 'payments',
        'payments': payments_list,
        'unpaid_cash_bookings': unpaid_cash_bookings,
    }
    return render(request, 'admin_panel/payment.html', context)

@login_required
@user_passes_test(is_admin)
def verify_payment(request, payment_id):
    # Require POST for verification to avoid accidental GET-triggered changes
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        payment.status = 'verified'
        payment.verified_by = request.user
        payment.verified_at = timezone.now()
        payment.save()
        payment.booking.status = 'verify'
        payment.booking.save()
        messages.success(request, 'Payment verified and booking marked as verify')
    return redirect('admin_panel:bookings')

@login_required
@user_passes_test(is_admin)
def chat_with_staff(request):
    staff_members = User.objects.filter(role='staff')
    selected_staff_id = request.GET.get('staff')
    messages_list = []
    
    if selected_staff_id:
        try:
            selected_staff = User.objects.get(id=selected_staff_id, role='staff')
            # Get messages between admin and this staff
            messages_list = ChatMessage.objects.filter(
                (Q(sender=request.user) & Q(receiver=selected_staff)) |
                (Q(sender=selected_staff) & Q(receiver=request.user))
            ).order_by('timestamp')
            
            # Mark messages as read
            messages_list.filter(receiver=request.user, is_read=False).update(is_read=True)
        except User.DoesNotExist:
            selected_staff = None
    else:
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

    if selected_customer_id:
        try:
            selected_customer = User.objects.get(id=selected_customer_id, role='customer')
            messages_list = ChatMessage.objects.filter(
                (Q(sender=request.user) & Q(receiver=selected_customer)) |
                (Q(sender=selected_customer) & Q(receiver=request.user))
            ).order_by('timestamp')
            messages_list.filter(receiver=request.user, is_read=False).update(is_read=True)
        except User.DoesNotExist:
            selected_customer = None
    else:
        selected_customer = None

    context = {
        'active_page': 'chat',
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
        
        receiver = None
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