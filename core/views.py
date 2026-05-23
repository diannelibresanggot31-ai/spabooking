from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout, login, authenticate
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta
from services.models import Service, Category, Room, Package
from staff.models import ChatMessage, StaffAttendance
from bookings.models import Booking
from payments.models import Payment
from accounts.models import User
from accounts.forms import CustomUserCreationForm
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json


# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


def is_staff(user):
    return user.is_authenticated and user.role == 'staff'


def is_customer(user):
    return user.is_authenticated and user.role == 'customer'


# core/views.py - Updated custom_login function

def custom_login(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        
        # Try to authenticate with username first
        user = authenticate(request, username=username_or_email, password=password)
        
        # If failed, try with email
        if user is None:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user is not None:
            login(request, user)
            
            # Redirect based on user role
            if user.role == 'admin':
                return redirect('admin_panel:dashboard')
            elif user.role == 'staff':
                return redirect('/staff/dashboard/')  # Direct URL to staff dashboard
            else:
                # Customer
                return redirect('/')
        else:
            messages.error(request, 'Invalid username/email or password.')
            return redirect('login')
    
    # Use the existing accounts/login.html template
    return render(request, 'accounts/login.html')

# ── HOME ──────────────────────────────────────────────────────────────────────
def home(request):
    categories = Category.objects.filter(is_active=True).annotate(
        active_services_count=Count('services', filter=Q(services__is_active=True))
    )
    return render(request, 'core/home.html', {
        'categories': categories
    })


# ── REGISTRATION ──────────────────────────────────────────────────────────────
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.username}!')
            return redirect('customer_dashboard')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


# ── CUSTOMER DASHBOARD ────────────────────────────────────────────────────────
@login_required
def customer_dashboard(request):
    user = request.user
    if user.role != 'customer':
        if user.role == 'admin':
            return redirect('admin_panel:dashboard')
        elif user.role == 'staff':
            return redirect('/staff/dashboard/')
        messages.error(request, 'Access denied.')
        return redirect('home')

    selected_partner_id = request.GET.get('conv_with')
    admin_user = User.objects.filter(role='admin').first()
    staff_users = User.objects.filter(role='staff').order_by('username')
    selected_chat_partner = None

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        receiver_id = request.POST.get('receiver_id')
        if receiver_id:
            try:
                selected_chat_partner = User.objects.get(id=receiver_id, role__in=['admin', 'staff'])
            except User.DoesNotExist:
                selected_chat_partner = None
        if not selected_chat_partner:
            selected_chat_partner = admin_user
        if not selected_chat_partner:
            messages.error(request, 'No admin or staff account available.')
            return redirect('customer_dashboard')
        if not message_text:
            messages.error(request, 'Please enter a message before sending.')
            return redirect(f"{reverse('customer_dashboard')}?conv_with={selected_chat_partner.id}")
        ChatMessage.objects.create(sender=user, receiver=selected_chat_partner, message=message_text)
        messages.success(request, f'Message sent to {selected_chat_partner.username}.')
        return redirect(f"{reverse('customer_dashboard')}?conv_with={selected_chat_partner.id}")

    if selected_partner_id:
        try:
            selected_chat_partner = User.objects.get(id=selected_partner_id, role__in=['admin', 'staff'])
        except User.DoesNotExist:
            selected_chat_partner = None
    if not selected_chat_partner:
        selected_chat_partner = admin_user or staff_users.first()

    user_bookings = Booking.objects.filter(customer=user).select_related('service', 'package', 'room').order_by('-created_at')
    selected_category = request.GET.get('category', '').strip()
    all_services = Service.objects.filter(is_active=True)
    if selected_category:
        all_services = all_services.filter(
            Q(service_category__name__iexact=selected_category) |
            Q(category__iexact=selected_category)
        )
    liked_services = user.liked_services.all()
    categories = Category.objects.filter(is_active=True)
    packages = Package.objects.filter(is_active=True)

    bookings_with_payment = []
    for b in user_bookings:
        pay = Payment.objects.filter(booking=b).first()
        bookings_with_payment.append({'booking': b, 'payment': pay})

    if selected_chat_partner:
        customer_messages = ChatMessage.objects.filter(
            (Q(sender=user) & Q(receiver=selected_chat_partner)) |
            (Q(sender=selected_chat_partner) & Q(receiver=user))
        ).order_by('timestamp')
        unread_messages_count = ChatMessage.objects.filter(receiver=user, is_read=False).count()
        ChatMessage.objects.filter(sender=selected_chat_partner, receiver=user, is_read=False).update(is_read=True)
    else:
        customer_messages = ChatMessage.objects.none()
        unread_messages_count = 0

    chat_partners = []
    if admin_user:
        chat_partners.append(admin_user)
    chat_partners.extend(staff_users)

    rooms = Room.objects.filter(is_available=True)

    return render(request, 'core/customer_dashboard.html', {
        'bookings': user_bookings,
        'bookings_with_payment': bookings_with_payment,
        'all_services': all_services,
        'liked_services': liked_services,
        'categories': categories,
        'packages': packages,
        'selected_category': selected_category,
        'user': user,
        'customer_messages': customer_messages,
        'unread_messages_count': unread_messages_count,
        'chat_partners': chat_partners,
        'selected_chat_partner': selected_chat_partner,
        'admin_user': admin_user,
        'staff_users': staff_users,
        'rooms': rooms,
    })


# ── STAFF DASHBOARD ──────────────────────────────────────────────────────────
@login_required
def staff_dashboard(request):
    user = request.user
    if user.role != 'staff':
        if user.role == 'admin':
            return redirect('admin_panel:dashboard')
        messages.error(request, 'Access denied.')
        return redirect('home')

    today = timezone.now().date()
    today_bookings = Booking.objects.filter(
        booking_date=today,
        status__in=['pending', 'verify']
    ).select_related('customer', 'service').order_by('booking_time')

    attendances = StaffAttendance.objects.filter(staff=user).order_by('-date')[:30]
    this_month = timezone.now().replace(day=1)
    monthly_att = StaffAttendance.objects.filter(staff=user, date__gte=this_month)
    present_count = monthly_att.filter(status='present').count()
    late_count = monthly_att.filter(status='late').count()
    absent_count = monthly_att.filter(status='absent').count()
    today_attendance = StaffAttendance.objects.filter(staff=user, date=today).first()

    selected_partner_id = request.GET.get('conv_with')
    admin_user = User.objects.filter(role='admin').first()
    customer_users = User.objects.filter(role='customer').order_by('username')
    selected_chat_partner = None

    if request.method == 'POST' and request.POST.get('message'):
        message_text = request.POST.get('message', '').strip()
        receiver_id = request.POST.get('receiver_id')
        if receiver_id and message_text:
            try:
                receiver = User.objects.get(id=receiver_id, role__in=['admin', 'customer'])
                ChatMessage.objects.create(sender=user, receiver=receiver, message=message_text)
                messages.success(request, 'Message sent.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        return redirect(f"{reverse('staff_dashboard')}?conv_with={receiver_id or ''}")

    if selected_partner_id:
        try:
            selected_chat_partner = User.objects.get(id=selected_partner_id, role__in=['admin', 'customer'])
        except User.DoesNotExist:
            selected_chat_partner = None
    if not selected_chat_partner:
        selected_chat_partner = admin_user or customer_users.first()

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

    chat_partners = []
    if admin_user:
        chat_partners.append(admin_user)
    chat_partners.extend(customer_users)

    return render(request, 'core/staff_dashboard.html', {
        'bookmarks_today': today_bookings,
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
        'total_today': today_bookings.count(),
        'confirmed_today': today_bookings.filter(status='verify').count(),
        'pending_today': today_bookings.filter(status='pending').count(),
    })


# ── LOGOUT ────────────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


# ── CREATE BOOKING (SIMPLIFIED VERSION) ───────────────────────────────────────
@login_required
def create_booking(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
    
    try:
        service_id = request.POST.get('service')
        booking_date = request.POST.get('booking_date')
        booking_time = request.POST.get('booking_time')
        special_requests = request.POST.get('special_requests', '')
        payment_method = request.POST.get('payment_method', 'cash')
        
        if not service_id or not booking_date or not booking_time:
            return JsonResponse({'success': False, 'error': 'Please fill all required fields.'}, status=400)
        
        service = get_object_or_404(Service, id=service_id)
        
        booking = Booking.objects.create(
            customer=request.user,
            service=service,
            booking_date=booking_date,
            booking_time=booking_time,
            total_amount=service.price,
            duration_minutes=service.duration_minutes,
            special_requests=special_requests,
            payment_method=payment_method,
            status='pending'
        )
        
        Payment.objects.create(
            booking=booking,
            amount=service.price,
            payment_method=payment_method,
            status='pending'
        )
        
        return JsonResponse({'success': True, 'booking_id': booking.id, 'message': 'Booking created successfully!'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ── AVAILABLE SLOTS API ───────────────────────────────────────────────────────
@login_required
def available_slots_api(request):
    date_str = request.GET.get('date', '')
    
    if not date_str:
        return JsonResponse({'booked_slots': [], 'all_slots': []})
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Generate all time slots (9 AM to 5 PM)
        all_slots = []
        for hour in range(9, 17):
            all_slots.append(f"{hour:02d}:00")
            all_slots.append(f"{hour:02d}:30")
        
        # Get booked slots
        booked = Booking.objects.filter(
            booking_date=date_obj,
            status__in=['pending', 'verify', 'complete']
        ).values_list('booking_time', flat=True)
        
        booked_slots = {str(t)[:5] for t in booked}
        
        return JsonResponse({
            'booked_slots': list(booked_slots),
            'all_slots': all_slots
        })
        
    except Exception as e:
        return JsonResponse({'booked_slots': [], 'all_slots': [], 'error': str(e)})


# ── AVAILABLE ROOMS API ────────────────────────────────────────────────────────
@login_required
def available_rooms_api(request):
    """Get available rooms for a specific date and time"""
    date_str = request.GET.get('date')
    time_str = request.GET.get('time')
    
    if not date_str or not time_str:
        return JsonResponse({
            'available_rooms': [], 
            'total_rooms': 0, 
            'booked_count': 0,
            'available_count': 0
        })
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        hour = int(time_str[:2])
        minute = int(time_str[3:5])
        
        all_rooms = Room.objects.filter(is_available=True)
        total_rooms = all_rooms.count()
        
        booked_room_ids = Booking.objects.filter(
            booking_date=date_obj,
            booking_time__hour=hour,
            booking_time__minute=minute,
            status__in=['pending', 'verify', 'complete'],
            room__isnull=False
        ).values_list('room_id', flat=True)
        
        available_rooms = all_rooms.exclude(id__in=booked_room_ids)
        
        rooms_data = [{
            'id': room.id,
            'room_number': room.room_number,
            'room_type': room.room_type,
            'room_type_display': room.get_room_type_display()
        } for room in available_rooms]
        
        return JsonResponse({
            'available_rooms': rooms_data,
            'total_rooms': total_rooms,
            'booked_count': len(booked_room_ids),
            'available_count': available_rooms.count()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e), 'available_rooms': []}, status=400)


# ── BOOKED SLOTS API ────────────────────────────────────────────────────────
@login_required
def booked_slots_api(request):
    """Get booked time slots for a specific date and service"""
    date_str = request.GET.get('date')
    duration = int(request.GET.get('duration', 60))
    service_id = request.GET.get('service_id')
    
    if not date_str:
        return JsonResponse({'booked_slots': []})
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        requires_room = False
        if service_id and not str(service_id).startswith('pkg_'):
            try:
                service = Service.objects.get(id=service_id)
                requires_room = service.requires_room
            except:
                pass
        
        bookings = Booking.objects.filter(
            booking_date=date_obj,
            status__in=['pending', 'verify', 'complete']
        )
        
        start_minutes = 8 * 60
        end_minutes = 17 * 60
        break_start = 12 * 60
        break_end = 13 * 60
        step = duration
        
        all_slots = []
        for t in range(start_minutes, end_minutes - step + 1, step):
            if t < break_end and t + step > break_start:
                continue
            h = t // 60
            m = t % 60
            slot = f"{h:02d}:{m:02d}"
            all_slots.append(slot)
        
        booked_slots = set()
        
        if requires_room:
            total_rooms = Room.objects.filter(is_available=True).count()
            
            for slot in all_slots:
                hour = int(slot[:2])
                minute = int(slot[3:5])
                
                booked_count = Booking.objects.filter(
                    booking_date=date_obj,
                    booking_time__hour=hour,
                    booking_time__minute=minute,
                    status__in=['pending', 'verify', 'complete'],
                    room__isnull=False
                ).count()
                
                if total_rooms > 0 and booked_count >= total_rooms:
                    booked_slots.add(slot)
        else:
            for booking in bookings:
                if not booking.room:
                    booking_time_str = booking.booking_time.strftime('%H:%M')
                    if booking_time_str in all_slots:
                        booked_slots.add(booking_time_str)
        
        return JsonResponse({'booked_slots': list(booked_slots)})
        
    except Exception as e:
        return JsonResponse({'booked_slots': [], 'error': str(e)})


# ── BOOKING RECEIPT API ────────────────────────────────────────────────────────
@login_required
def booking_receipt(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    # Customer can view receipt when status is 'verify' or 'complete'
    if booking.status not in ['verify', 'complete']:
        return JsonResponse({'error': 'Receipt will be available after payment verification.'}, status=403)
    
    payment = Payment.objects.filter(booking=booking).first()
    
    payment_status_display = 'Pending Verification'
    if payment:
        if payment.status == 'verified':
            payment_status_display = 'Verified ✓'
        elif payment.status == 'pending':
            payment_status_display = 'Pending Verification'
    
    data = {
        'booking_id': booking.id,
        'booking_number': booking.booking_number,
        'service_name': booking.service.name if booking.service else (booking.package.name if booking.package else 'Service'),
        'booking_date': booking.booking_date.strftime('%B %d, %Y'),
        'booking_time': booking.booking_time.strftime('%I:%M %p'),
        'total_amount': str(booking.total_amount),
        'duration': booking.duration_minutes,
        'special_requests': booking.special_requests or 'None',
        'booking_status': booking.get_status_display(),
        'payment_method': booking.get_payment_method_display(),
        'created_at': booking.created_at.strftime('%B %d, %Y %I:%M %p'),
        'room_number': booking.room.room_number if booking.room else 'Not assigned',
        'room_type': booking.room.get_room_type_display() if booking.room else 'N/A',
        'payment_status': payment_status_display,
        'gcash_reference': payment.gcash_reference if payment and payment.gcash_reference else '',
        'has_proof': bool(payment and payment.proof_image),
    }
    
    return JsonResponse(data)


# ── CUSTOMER DASHBOARD ────────────────────────────────────────────────────────
@login_required
def customer_dashboard(request):
    user = request.user
    if user.role != 'customer':
        if user.role == 'admin':
            return redirect('admin_dashboard')
        messages.error(request, 'Access denied.')
        return redirect('home')

    selected_partner_id = request.GET.get('conv_with')
    admin_user = User.objects.filter(role='admin').first()
    staff_users = User.objects.filter(role='staff').order_by('username')
    selected_chat_partner = None

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()
        receiver_id = request.POST.get('receiver_id')
        if receiver_id:
            try:
                selected_chat_partner = User.objects.get(id=receiver_id, role__in=['admin', 'staff'])
            except User.DoesNotExist:
                selected_chat_partner = None
        if not selected_chat_partner:
            selected_chat_partner = admin_user
        if not selected_chat_partner:
            messages.error(request, 'No admin or staff account available.')
            return redirect('customer_dashboard')
        if not message_text:
            messages.error(request, 'Please enter a message before sending.')
            return redirect(f"{reverse('customer_dashboard')}?conv_with={selected_chat_partner.id}")
        ChatMessage.objects.create(sender=user, receiver=selected_chat_partner, message=message_text)
        messages.success(request, f'Message sent to {selected_chat_partner.username}.')
        return redirect(f"{reverse('customer_dashboard')}?conv_with={selected_chat_partner.id}")

    if selected_partner_id:
        try:
            selected_chat_partner = User.objects.get(id=selected_partner_id, role__in=['admin', 'staff'])
        except User.DoesNotExist:
            selected_chat_partner = None
    if not selected_chat_partner:
        selected_chat_partner = admin_user or staff_users.first()

    user_bookings = Booking.objects.filter(customer=user).select_related('service', 'package', 'room').order_by('-created_at')
    selected_category = request.GET.get('category', '').strip()
    all_services = Service.objects.filter(is_active=True)
    if selected_category:
        all_services = all_services.filter(
            Q(service_category__name__iexact=selected_category) |
            Q(category__iexact=selected_category)
        )
    liked_services = user.liked_services.all()
    categories = Category.objects.filter(is_active=True)
    packages = Package.objects.filter(is_active=True)

    bookings_with_payment = []
    for b in user_bookings:
        pay = Payment.objects.filter(booking=b).first()
        bookings_with_payment.append({'booking': b, 'payment': pay})

    if selected_chat_partner:
        customer_messages = ChatMessage.objects.filter(
            (Q(sender=user) & Q(receiver=selected_chat_partner)) |
            (Q(sender=selected_chat_partner) & Q(receiver=user))
        ).order_by('timestamp')
        unread_messages_count = ChatMessage.objects.filter(receiver=user, is_read=False).count()
        ChatMessage.objects.filter(sender=selected_chat_partner, receiver=user, is_read=False).update(is_read=True)
    else:
        customer_messages = ChatMessage.objects.none()
        unread_messages_count = 0

    chat_partners = []
    if admin_user:
        chat_partners.append(admin_user)
    chat_partners.extend(staff_users)

    rooms = Room.objects.filter(is_available=True)

    return render(request, 'core/customer_dashboard.html', {
        'bookings': user_bookings,
        'bookings_with_payment': bookings_with_payment,
        'all_services': all_services,
        'liked_services': liked_services,
        'categories': categories,
        'packages': packages,
        'selected_category': selected_category,
        'user': user,
        'customer_messages': customer_messages,
        'unread_messages_count': unread_messages_count,
        'chat_partners': chat_partners,
        'selected_chat_partner': selected_chat_partner,
        'admin_user': admin_user,
        'staff_users': staff_users,
        'rooms': rooms,
    })


# ── CREATE BOOKING ─────────────────────────────────────────────────────────────
@login_required
def create_booking(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
    
    try:
        service_id       = request.POST.get('service')
        booking_date     = request.POST.get('booking_date')
        booking_time     = request.POST.get('booking_time')
        special_requests = request.POST.get('special_requests', '')
        payment_method   = request.POST.get('payment_method', 'cash')
        gcash_reference  = request.POST.get('gcash_reference', '').strip()
        payment_proof    = request.FILES.get('payment_proof')
        room_id          = request.POST.get('room', '').strip()
        
        if not service_id:
            return JsonResponse({'success': False, 'error': 'Please select a service.'}, status=400)
        if not booking_date or not booking_time:
            return JsonResponse({'success': False, 'error': 'Please select a date and time.'}, status=400)
        
        try:
            date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            if date_obj.weekday() == 6:
                return JsonResponse({'success': False, 'error': 'We are closed on Sundays.'}, status=400)
        except:
            pass

        service = None
        package = None
        requires_room = False
        booking_duration = 60
        total_amount = 0
        category_name = None

        if str(service_id).startswith('pkg_'):
            package_id = service_id.split('pkg_', 1)[-1]
            package = get_object_or_404(Package, id=package_id)
            requires_room = package.requires_room
            total_duration = package.services.aggregate(total=Sum('duration_minutes'))['total']
            booking_duration = total_duration if total_duration else 60
            total_amount = package.price
            first_service = package.services.first()
            if first_service:
                category_name = first_service.service_category.name if first_service.service_category else first_service.category
        else:
            service = get_object_or_404(Service, id=service_id)
            requires_room = service.requires_room
            booking_duration = service.duration_minutes
            total_amount = service.price
            category_name = service.service_category.name if service.service_category else service.category

        hour = int(booking_time[:2])
        minute = int(booking_time[3:5])
        
        room = None
        if requires_room:
            if not room_id:
                return JsonResponse({'success': False, 'error': 'Please select a room.'}, status=400)
            
            room = get_object_or_404(Room, id=room_id, is_available=True)
            
            room_conflict = Booking.objects.filter(
                room=room,
                booking_date=booking_date,
                booking_time__hour=hour,
                booking_time__minute=minute,
                status__in=['pending', 'verify', 'complete']
            ).exists()
            
            if room_conflict:
                return JsonResponse({'success': False, 'error': f'Room {room.room_number} is already booked at {booking_time}.'}, status=400)

        if payment_method == 'gcash':
            if not gcash_reference:
                return JsonResponse({'success': False, 'error': 'Please enter your GCash reference number.'}, status=400)
            if not payment_proof:
                return JsonResponse({'success': False, 'error': 'Please upload your GCash payment screenshot.'}, status=400)

        if requires_room:
            total_rooms = Room.objects.filter(is_available=True).count()
            if total_rooms == 0:
                return JsonResponse({'success': False, 'error': 'No rooms available.'}, status=400)
            
            booked_rooms_count = Booking.objects.filter(
                booking_date=booking_date,
                booking_time__hour=hour,
                booking_time__minute=minute,
                status__in=['pending', 'verify', 'complete'],
                room__isnull=False
            ).count()
            
            if booked_rooms_count >= total_rooms:
                return JsonResponse({'success': False, 'error': f'All rooms are fully booked at {booking_time}.'}, status=400)
        else:
            all_bookings_at_time = Booking.objects.filter(
                booking_date=booking_date,
                booking_time__hour=hour,
                booking_time__minute=minute,
                status__in=['pending', 'verify', 'complete'],
                room__isnull=True
            ).select_related('service', 'package')
            
            same_category_conflict = False
            
            for existing_booking in all_bookings_at_time:
                existing_category = None
                if existing_booking.service:
                    existing_category = existing_booking.service.service_category.name if existing_booking.service.service_category else existing_booking.service.category
                elif existing_booking.package:
                    first_pkg_service = existing_booking.package.services.first()
                    if first_pkg_service:
                        existing_category = first_pkg_service.service_category.name if first_pkg_service.service_category else first_pkg_service.category
                
                if existing_category and existing_category == category_name:
                    same_category_conflict = True
                    break
            
            if same_category_conflict:
                return JsonResponse({
                    'success': False, 
                    'error': f'A service in {category_name} is already booked at {booking_time}. Only one booking per category at a time.'
                }, status=400)

        if requires_room and room:
            own_conflict = Booking.objects.filter(
                customer=request.user,
                booking_date=booking_date,
                booking_time__hour=hour,
                booking_time__minute=minute,
                status__in=['pending', 'verify'],
                room=room
            ).exists()
            
            if own_conflict:
                return JsonResponse({'success': False, 'error': f'You already booked Room {room.room_number} at this time.'}, status=400)
        else:
            own_bookings = Booking.objects.filter(
                customer=request.user,
                booking_date=booking_date,
                booking_time__hour=hour,
                booking_time__minute=minute,
                status__in=['pending', 'verify'],
                room__isnull=True
            ).select_related('service', 'package')
            
            same_category_own_conflict = False
            
            for existing_booking in own_bookings:
                existing_category = None
                if existing_booking.service:
                    existing_category = existing_booking.service.service_category.name if existing_booking.service.service_category else existing_booking.service.category
                elif existing_booking.package:
                    first_pkg_service = existing_booking.package.services.first()
                    if first_pkg_service:
                        existing_category = first_pkg_service.service_category.name if first_pkg_service.service_category else first_pkg_service.category
                
                if existing_category and existing_category == category_name:
                    same_category_own_conflict = True
                    break
            
            if same_category_own_conflict:
                return JsonResponse({
                    'success': False, 
                    'error': f'You already have a booking in {category_name} at this time. Please choose a different category or time.'
                }, status=400)

        if payment_method == 'cash':
            booking_status = 'verify'
        else:
            booking_status = 'pending'

        booking = Booking.objects.create(
            customer=request.user,
            service=service,
            package=package,
            booking_date=booking_date,
            booking_time=booking_time,
            total_amount=total_amount,
            duration_minutes=booking_duration,
            special_requests=special_requests,
            payment_method=payment_method,
            room=room,
            status=booking_status
        )

        if payment_method == 'cash':
            payment_status = 'verified'
        else:
            payment_status = 'pending'

        Payment.objects.create(
            booking=booking,
            amount=total_amount,
            payment_method=payment_method,
            gcash_reference=gcash_reference if payment_method == 'gcash' else '',
            proof_image=payment_proof if payment_method == 'gcash' else None,
            status=payment_status
        )

        return JsonResponse({'success': True, 'booking_id': booking.id, 'message': 'Booking created successfully!'})

    except Exception as e:
        print(f"Booking error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def select_room(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    requires_room = False
    if booking.service:
        requires_room = booking.service.requires_room
    elif booking.package:
        requires_room = booking.package.requires_room

    if not requires_room:
        messages.error(request, 'This booking does not require a room.')
        return redirect('customer_dashboard')

    if booking.room:
        messages.info(request, 'A room has already been assigned to this booking.')
        return redirect('customer_dashboard')

    room_conflict_qs = Booking.objects.filter(
        booking_date=booking.booking_date,
        booking_time__hour=booking.booking_time.hour,
        booking_time__minute=booking.booking_time.minute,
        status__in=['pending', 'verify', 'complete'],
        room__isnull=False
    ).exclude(id=booking.id)
    booked_room_ids = list(room_conflict_qs.values_list('room_id', flat=True))
    all_rooms = Room.objects.filter(is_available=True)
    available_rooms = all_rooms.exclude(id__in=booked_room_ids)

    if request.method == 'POST':
        selected_room_id = request.POST.get('room_id')
        if not selected_room_id:
            messages.error(request, 'Please select a room.')
            return redirect('select_room', booking_id=booking.id)

        room = get_object_or_404(Room, id=selected_room_id, is_available=True)
        if Booking.objects.filter(
            booking_date=booking.booking_date,
            booking_time__hour=booking.booking_time.hour,
            booking_time__minute=booking.booking_time.minute,
            room=room,
            status__in=['pending', 'verify', 'complete']
        ).exclude(id=booking.id).exists():
            messages.error(request, f'Room {room.room_number} is already booked at that time. Please choose another room.')
            return redirect('select_room', booking_id=booking.id)

        booking.room = room
        if booking.payment_method == 'cash' and booking.status == 'pending':
            booking.status = 'verify'
        booking.save()

        if booking.payment_method == 'cash':
            payment = Payment.objects.filter(booking=booking).first()
            if payment and payment.status != 'verified':
                payment.status = 'verified'
                payment.verified_at = timezone.now()
                payment.save()

        messages.success(request, f'Room {room.room_number} assigned to booking #{booking.id}.')
        return redirect('customer_dashboard')

    return render(request, 'core/select_room.html', {
        'booking': booking,
        'all_rooms': all_rooms,
        'available_rooms': available_rooms,
        'booked_room_ids': booked_room_ids,
    })


# ── CANCEL BOOKING ─────────────────────────────────────────────────────────────
@login_required
def cancel_booking(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)
    
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    if booking.status != 'pending':
        return JsonResponse({'success': False, 'error': 'This booking cannot be cancelled. Only pending bookings can be cancelled.'}, status=400)
    
    if booking.payment_method == 'gcash':
        return JsonResponse({'success': False, 'error': 'GCash payments cannot be cancelled. Please contact support for assistance.'}, status=400)
    
    try:
        Payment.objects.filter(booking=booking).delete()
        booking.delete()
        
        return JsonResponse({'success': True, 'message': 'Booking cancelled successfully!'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ── ADMIN UPDATE BOOKING STATUS ────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def update_booking_status(request, booking_id):
    """Admin: Update booking status - FIXED VERSION"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_panel:bookings')
    
    new_status = request.POST.get('new_status')
    
    # Valid statuses based on your Booking model
    valid_statuses = ['pending', 'verify', 'complete', 'cancelled']
    
    if new_status not in valid_statuses:
        messages.error(request, f'Invalid status: {new_status}')
        return redirect('admin_panel:bookings')
    
    old_status = booking.status
    
    # Prevent changing to same status
    if old_status == new_status:
        messages.info(request, f'Booking #{booking.id} is already {booking.get_status_display()}')
        return redirect('admin_panel:bookings')
    
    # Update booking status
    booking.status = new_status
    booking.save()
    
    # Handle payment status updates based on booking status change
    payment = Payment.objects.filter(booking=booking).first()
    
    # Clear any existing messages to prevent duplicates
    storage = messages.get_messages(request)
    storage.used = True
    
    if new_status == 'verify' and old_status == 'pending':
        # GCash payment verified
        if payment and payment.payment_method == 'gcash':
            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.save()
        messages.success(request, f'✅ Booking #{booking.id} has been VERIFIED. Customer can now view their receipt.')
    
    elif new_status == 'complete':
        # Service completed
        if payment and payment.payment_method == 'cash':
            payment.status = 'verified'
            payment.save()
        messages.success(request, f'🎉 Booking #{booking.id} marked as COMPLETE SESSION.')
    
    elif new_status == 'cancelled':
        messages.warning(request, f'❌ Booking #{booking.id} has been CANCELLED.')
    
    else:
        messages.info(request, f'📋 Booking #{booking.id} status updated to {booking.get_status_display()}')
    
    return redirect('admin_panel:bookings')

# ── STAFF DASHBOARD ────────────────────────────────────────────────────────────
@login_required
def staff_dashboard(request):
    user = request.user
    if user.role != 'staff':
        if user.role == 'admin':
            return redirect('admin_dashboard')
        messages.error(request, 'Access denied.')
        return redirect('home')

    today = timezone.now().date()
    today_bookings = Booking.objects.filter(
        booking_date=today,
        status__in=['pending', 'verify']
    ).select_related('customer', 'service').order_by('booking_time')

    attendances = StaffAttendance.objects.filter(staff=user).order_by('-date')[:30]
    this_month = timezone.now().replace(day=1)
    monthly_att = StaffAttendance.objects.filter(staff=user, date__gte=this_month)
    present_count = monthly_att.filter(status='present').count()
    late_count    = monthly_att.filter(status='late').count()
    absent_count  = monthly_att.filter(status='absent').count()
    today_attendance = StaffAttendance.objects.filter(staff=user, date=today).first()

    selected_partner_id = request.GET.get('conv_with')
    admin_user = User.objects.filter(role='admin').first()
    customer_users = User.objects.filter(role='customer').order_by('username')
    selected_chat_partner = None

    if request.method == 'POST' and request.POST.get('message'):
        message_text = request.POST.get('message', '').strip()
        receiver_id  = request.POST.get('receiver_id')
        if receiver_id and message_text:
            try:
                receiver = User.objects.get(id=receiver_id, role__in=['admin', 'customer'])
                ChatMessage.objects.create(sender=user, receiver=receiver, message=message_text)
                messages.success(request, 'Message sent.')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        return redirect(f"{reverse('staff_dashboard')}?conv_with={receiver_id or ''}")

    if selected_partner_id:
        try:
            selected_chat_partner = User.objects.get(id=selected_partner_id, role__in=['admin', 'customer'])
        except User.DoesNotExist:
            selected_chat_partner = None
    if not selected_chat_partner:
        selected_chat_partner = admin_user or customer_users.first()

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

    chat_partners = []
    if admin_user:
        chat_partners.append(admin_user)
    chat_partners.extend(customer_users)

    return render(request, 'core/staff_dashboard.html', {
        'bookings':              today_bookings,
        'attendances':           attendances,
        'my_present_count':      present_count,
        'my_late_count':         late_count,
        'my_absent_count':       absent_count,
        'today_attendance':      today_attendance,
        'user':                  user,
        'chat_partners':         chat_partners,
        'selected_chat_partner': selected_chat_partner,
        'chat_messages':         chat_messages,
        'unread_messages_count': unread_messages_count,
        'admin_user':            admin_user,
        'total_today':           today_bookings.count(),
        'confirmed_today':       today_bookings.filter(status='verify').count(),
        'pending_today':         today_bookings.filter(status='pending').count(),
    })


# ── STAFF CHECK-IN/OUT ─────────────────────────────────────────────────────────
@login_required
def staff_checkin(request):
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required.'}, status=405)

    today  = timezone.now().date()
    action = request.POST.get('action')
    now    = timezone.now().time()

    attendance, _ = StaffAttendance.objects.get_or_create(
        staff=request.user, date=today,
        defaults={'status': 'present'}
    )

    if action == 'check_in':
        if attendance.check_in:
            return JsonResponse({'success': False, 'message': 'Already checked in.'})
        photo = request.FILES.get('photo')
        if not photo:
            return JsonResponse({'success': False, 'message': 'Photo required for check-in.'})
        
        attendance.check_in = now
        
        from datetime import time as dt_time
        morning_threshold = dt_time(8, 0)
        afternoon_threshold = dt_time(13, 0)
        
        if now < dt_time(12, 30):
            attendance.status = 'late' if now > morning_threshold else 'present'
        else:
            attendance.status = 'late' if now > afternoon_threshold else 'present'
        
        if hasattr(attendance, 'photo'):
            attendance.photo = photo
        attendance.save()
        return JsonResponse({'success': True, 'time_in': now.strftime('%I:%M %p'), 'message': 'Checked in.'})

    elif action == 'check_out':
        if not attendance.check_in:
            return JsonResponse({'success': False, 'message': 'Not checked in yet.'})
        if attendance.check_out:
            return JsonResponse({'success': False, 'message': 'Already checked out.'})
        attendance.check_out = now
        attendance.save()
        return JsonResponse({'success': True, 'time_out': now.strftime('%I:%M %p'), 'message': 'Checked out.'})

    return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)


# ── TOGGLE LIKE ─────────────────────────────────────────────────────────────────
@login_required
def toggle_like(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.user in service.likes.all():
        service.likes.remove(request.user)
        liked = False
    else:
        service.likes.add(request.user)
        liked = True
    return JsonResponse({'liked': liked, 'like_count': service.likes.count()})


# ── LOGOUT ──────────────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('/')


@require_http_methods(["GET", "POST"])
def admin_logout_fix(request):
    logout(request)
    return redirect('/')


# ── ADMIN DASHBOARD ────────────────────────────────────────────────────────────
@login_required
def admin_dashboard(request):
    user = request.user
    if user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('home')

    today = timezone.now().date()
    total_bookings         = Booking.objects.count()
    total_revenue          = Payment.objects.filter(status='verified').aggregate(total=Sum('amount'))['total'] or 0
    pending_payments_count = Payment.objects.filter(status='pending').count()
    pending_payments_list  = Payment.objects.filter(status='pending').select_related('booking', 'booking__customer')[:10]
    today_revenue          = Payment.objects.filter(status='verified', created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0
    recent_bookings        = Booking.objects.all().order_by('-created_at')[:10]
    total_customers        = User.objects.filter(role='customer').count()
    active_today           = StaffAttendance.objects.filter(date=today, check_in__isnull=False).count()
    pending_bookings       = Booking.objects.filter(status='pending').count()

    return render(request, 'core/admin_dashboard.html', {
        'total_bookings':        total_bookings,
        'total_revenue':         int(total_revenue),
        'pending_payments':      pending_payments_count,
        'pending_payments_list': pending_payments_list,
        'today_revenue':         int(today_revenue),
        'recent_bookings':       recent_bookings,
        'total_customers':       total_customers,
        'active_today':          active_today,
        'pending_bookings':      pending_bookings,
    })


# ── MESSENGER ──────────────────────────────────────────────────────────────────
@login_required
def messenger(request):
    """Dedicated messenger page for staff and customers."""
    user = request.user
    
    if user.role == 'customer':
        contacts = User.objects.filter(role__in=['admin', 'staff']).order_by('role', 'username')
    elif user.role == 'staff':
        contacts = User.objects.filter(role__in=['admin', 'customer']).order_by('role', 'username')
    else:
        contacts = User.objects.exclude(id=user.id).order_by('role', 'username')
    
    contact_id = request.GET.get('contact_id')
    selected_contact = None
    
    if contact_id:
        try:
            selected_contact = User.objects.get(id=contact_id)
        except User.DoesNotExist:
            selected_contact = contacts.first()
    else:
        selected_contact = contacts.first()
    
    messages_list = []
    if selected_contact:
        messages_list = ChatMessage.objects.filter(
            (Q(sender=user) & Q(receiver=selected_contact)) |
            (Q(sender=selected_contact) & Q(receiver=user))
        ).order_by('timestamp')
        ChatMessage.objects.filter(sender=selected_contact, receiver=user, is_read=False).update(is_read=True)
    
    unread_counts = {}
    for contact in contacts:
        unread_count = ChatMessage.objects.filter(
            sender=contact,
            receiver=user,
            is_read=False
        ).count()
        if unread_count > 0:
            unread_counts[contact.id] = unread_count
    
    for contact in contacts:
        contact.unread_count = unread_counts.get(contact.id, 0)
    
    context = {
        'contacts': contacts,
        'selected_contact': selected_contact,
        'selected_contact_id': selected_contact.id if selected_contact else None,
        'messages_list': messages_list,
        'unread_counts': unread_counts,
    }
    
    return render(request, 'core/messenger.html', context)


# ── SEND MESSAGE ───────────────────────────────────────────────────────────────
@require_http_methods(["POST"])
@login_required
def send_message(request):
    """Send a message to another user."""
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