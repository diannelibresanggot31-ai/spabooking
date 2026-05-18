from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', views.home, name='home'),

    # Redirect legacy URLs
    path('dashboard/', lambda request: redirect('/admin-panel/'), name='dashboard'),
    path('admin-dashboard/', lambda request: redirect('/admin-panel/'), name='admin_dashboard'),

    # Customer
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/dashboard/',  views.customer_dashboard, name='customer_dashboard_alt'),
    path('book-services/',       views.book_services,      name='book_services'),

    # Booking actions
    path('create-booking/',                  views.create_booking,    name='create_booking'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking,    name='cancel_booking'),
    path('booking-receipt/<int:booking_id>/',views.booking_receipt,   name='booking_receipt'),

    # Slot availability API
    path('available-slots/', views.available_slots_api, name='available_slots_api'),

    # Staff
    path('staff-dashboard/',            views.staff_dashboard, name='staff_dashboard'),
    path('staff/attendance/checkin/',   views.staff_checkin,   name='staff_checkin'),

    # Like
    path('like/<int:service_id>/', views.toggle_like, name='toggle_like'),

    # Auth
    path('login/',    views.custom_login,   name='login'),
    path('register/', views.register_view,  name='register'),
    path('logout/',   views.logout_view,    name='logout'),
]
