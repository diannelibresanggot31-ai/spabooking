from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login, authenticate
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta
from services.models import Service, Category, SliderImage, Room, Package
from staff.models import ChatMessage, StaffAttendance
from bookings.models import Booking
from payments.models import Payment
from accounts.models import User
from accounts.forms import CustomUserCreationForm
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


# ── HOME ──────────────────────────────────────────────────────────────────────
def home(request):
    slider_images = SliderImage.objects.filter(is_active=True)
    categories = Category.objects.filter(is_active=True).annotate(
        active_services_count=Count('services', filter=Q(services__is_active=True))
    )
    return render(request, 'core/home.html', {
        'slider_images': slider_images,
        'categories': categories
    })


# ── AUTH ──────────────────────────────────────────────────────────────────────
def custom_login(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username_or_email, password=password)
        if user is None:
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        if user is not None:
            login(request, user)
            if user.role == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'staff':
                return redirect('staff_dashboard')
            else:
                return redirect('customer_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('login')
    return render(request, 'accounts/login.html')


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


# ── HELPER: booked slots for a date ───────────────────────────────────────────
def _get_booked_slots(date_str):
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return set()
    booked = Booking.objects.filter(
        booking_date=date_obj,
        status__in=['pending', 'confirmed', 'completed']
    ).values_list('booking_time', flat=True)
    return {str(t)[:5] for t in booked if t}


# ── AVAILABLE SLOTS API ────────────────────────────────────────────────────────
@login_required
def available_slots_api(request):
    date_str = request.GET.get('date', '')
    all_slots = ['09:00','10:00','11:00','12:00','13:00',
                 '14:00','15:00','16:00','17:00','18:00','19:00','20:00']
    booked = _get_booked_slots(date_str)
    available = [s for s in all_slots if s not in booked]
    return JsonResponse({'booked': list(booked), 'available': available})


# ── BOOKING RECEIPT API ────────────────────────────────────────────────────────
@login_required
def booking_receipt(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    if booking.status not in ['confirmed', 'completed']:
        return JsonResponse({'error': 'Receipt unavailable until booking is confirmed.'}, status=403)
    payment = Payment.objects.filter(booking=booking).first()
    data = {
        'booking_id':       booking.id,
        'service_name':     booking.service.name if booking.service else (booking.package.name if hasattr(booking, 'package') and booking.package else 'Service'),
        'booking_date':     str(booking.booking_date),
        'booking_time':     str(booking.booking_time)[:5] if booking.booking_time else '--:--',
        'total_amount':     str(booking.total_amount),
        'duration':         booking.duration_minutes if hasattr(booking, 'duration_minutes') else '--',
        'special_requests': booking.special_requests or 'None',
        'booking_status':   booking.status,
        'payment_method':   booking.payment_method,
        'created_at':       booking.created_at.strftime('%B %d, %Y %I:%M %p') if hasattr(booking, 'created_at') and booking.created_at else '--',
        'payment_status':   payment.status if payment else 'no_payment',
        'gcash_reference':  payment.gcash_reference if payment else '',
        'has_proof':        bool(payment and payment.proof_image),
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

    user_bookings = Booking.objects.filter(customer=user).order_by('-created_at')
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

    # Attach payment to each booking
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
    })


# ── BOOK SERVICES PAGE ─────────────────────────────────────────────────────────
@login_required
def book_services(request):
    user = request.user
    if user.role != 'customer':
        if user.role == 'admin':
            return redirect('admin_dashboard')
        messages.error(request, 'Access denied.')
        return redirect('home')
    all_services = Service.objects.filter(is_active=True).order_by('-created_at')
    categories = Category.objects.filter(is_active=True)
    packages = Package.objects.filter(is_active=True)
    return render(request, 'core/book_services.html', {
        'all_services': all_services,
        'categories': categories,
        'packages': packages,
        'user': user
    })


# ── CREATE BOOKING ─────────────────────────────────────────────────────────────
@login_required
def create_booking(request):
    if request.method != 'POST':
        return redirect('customer_dashboard')
    try:
        service_id       = request.POST.get('service_id')
        booking_date     = request.POST.get('booking_date')
        booking_time     = request.POST.get('booking_time')
        special_requests = request.POST.get('special_requests', '')
        payment_method   = request.POST.get('payment_method', 'cash')
        gcash_reference  = request.POST.get('gcash_reference', '').strip()
        payment_proof    = request.FILES.get('payment_proof')

        if not service_id:
            messages.error(request, 'Please select a service.')
            return redirect('customer_dashboard')
        if not booking_date or not booking_time:
            messages.error(request, 'Please select a date and time.')
            return redirect('customer_dashboard')

        service = get_object_or_404(Service, id=service_id)

        if payment_method == 'gcash':
            if not gcash_reference:
                messages.error(request, 'Please enter your GCash reference number.')
                return redirect('customer_dashboard')
            if not payment_proof:
                messages.error(request, 'Please upload your GCash payment screenshot.')
                return redirect('customer_dashboard')

        # Slot conflict: one booking per hour globally
        slot = booking_time[:5]
        conflict = Booking.objects.filter(
            booking_date=booking_date,
            booking_time__startswith=slot,
            status__in=['pending', 'confirmed', 'completed']
        ).exists()
        if conflict:
            messages.error(request, f'The {slot} slot on {booking_date} is already taken. Please choose another time.')
            return redirect('customer_dashboard')

        # Prevent same customer double booking
        own_conflict = Booking.objects.filter(
            customer=request.user,
            booking_date=booking_date,
            booking_time__startswith=slot,
            status__in=['pending', 'confirmed']
        ).exists()
        if own_conflict:
            messages.error(request, 'You already have a booking at this time. Please choose another slot.')
            return redirect('customer_dashboard')

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
            gcash_reference=gcash_reference if payment_method == 'gcash' else '',
            proof_image=payment_proof if payment_method == 'gcash' else None,
            status='pending'
        )

        if payment_method == 'gcash':
            messages.success(request, f'Booking #{booking.id} submitted! Your GCash payment is being verified.')
        else:
            messages.success(request, f'Booking #{booking.id} confirmed! Please pay on arrival.')
        return redirect('customer_dashboard')

    except Exception as e:
        messages.error(request, f'Booking error: {str(e)}')
        return redirect('customer_dashboard')


# ── CANCEL BOOKING ─────────────────────────────────────────────────────────────
@login_required
def cancel_booking(request, booking_id):
    if request.method != 'POST':
        return redirect('customer_dashboard')
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    if booking.payment_method == 'gcash':
        messages.error(request, 'GCash payments cannot be cancelled. Please contact support if you need assistance.')
    elif booking.status == 'pending':
        Payment.objects.filter(booking=booking).delete()
        booking.delete()
        messages.success(request, f'Booking #{booking_id} has been removed.')
    else:
        messages.error(request, 'This booking cannot be cancelled once it is confirmed.')
    return redirect('customer_dashboard')


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
        status__in=['pending', 'confirmed']
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
        'confirmed_today':       today_bookings.filter(status='confirmed').count(),
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
        attendance.status   = 'late' if now.hour >= 9 else 'present'
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


@csrf_exempt
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
