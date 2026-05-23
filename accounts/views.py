from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login, authenticate
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from services.models import Service, Category
from bookings.models import Booking
from payments.models import Payment
from accounts.models import User
from accounts.forms import CustomUserCreationForm

def home(request):
    categories = Category.objects.filter(is_active=True)
    return render(request, 'core/home.html', {
        'categories': categories
    })

def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Redirect based on role
            if user.role == 'admin':
                messages.success(request, f'Welcome Admin {user.username}!')
                return redirect('/admin/')
            elif user.role == 'staff':
                messages.success(request, f'Welcome Staff {user.username}!')
                return redirect('staff_dashboard')
            else:  # customer
                messages.success(request, f'Welcome {user.username}!')
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
            # Log the user in immediately after registration
            login(request, user)
            messages.success(request, f'Registration successful! Welcome {user.username}!')
            return redirect('customer_dashboard')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def customer_dashboard(request):
    user = request.user
    
    # Only customers can access this
    if user.role != 'customer':
        messages.error(request, 'Access denied. Customers only.')
        if user.role == 'admin':
            return redirect('/admin/')
        return redirect('home')
    
    user_bookings = Booking.objects.filter(customer=user).order_by('-created_at')
    all_services = Service.objects.filter(is_active=True)
    liked_services = user.liked_services.all()
    categories = Category.objects.filter(is_active=True)
    
    return render(request, 'core/customer_dashboard.html', {
        'bookings': user_bookings,
        'all_services': all_services,
        'liked_services': liked_services,
        'categories': categories,
        'user': user
    })

@login_required
def staff_dashboard(request):
    user = request.user
    
    # Only staff can access this
    if user.role != 'staff':
        messages.error(request, 'Access denied. Staff only.')
        if user.role == 'admin':
            return redirect('/admin/')
        return redirect('home')
    
    today = timezone.now().date()
    today_bookings = Booking.objects.filter(booking_date=today)
    return render(request, 'core/staff_dashboard.html', {
        'bookings': today_bookings,
        'user': user
    })

def old_dashboard(request):
    user = request.user
    if user.role == 'admin':
        return redirect('/admin/')
    elif user.role == 'staff':
        return redirect('staff_dashboard')
    else:
        return redirect('customer_dashboard')

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

def logout_view(request):
    logout(request)
    return redirect('home')