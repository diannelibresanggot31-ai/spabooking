from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('', views.home, name='home'),

    # Redirect legacy URLs
    path('dashboard/', lambda request: redirect('/admin-panel/'), name='dashboard'),
    path('admin-dashboard/', lambda request: redirect('/admin-panel/'), name='admin_dashboard'),
    
    # Redirect old staff-dashboard to new staff app
    path('staff-dashboard/', lambda request: redirect('/staff/dashboard/'), name='staff_dashboard_redirect'),

    # Customer
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/dashboard/',  views.customer_dashboard, name='customer_dashboard_alt'),

    # Messenger
    path('messages/', views.messenger, name='messenger'),
    path('send-message/', views.send_message, name='send_message'),

    # Booking actions
    path('create-booking/',                  views.create_booking,    name='create_booking'),
    path('select-room/<int:booking_id>/',     views.select_room,      name='select_room'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking,    name='cancel_booking'),
    path('booking-receipt/<int:booking_id>/',views.booking_receipt,   name='booking_receipt'),

    # Slot availability APIs
    path('available-slots/', views.available_slots_api, name='available_slots_api'),
    path('available-rooms/', views.available_rooms_api, name='available_rooms_api'),
    path('booked-slots/', views.booked_slots_api, name='booked_slots_api'),

    # Like
    path('like/<int:service_id>/', views.toggle_like, name='toggle_like'),

    # Auth
    path('login/',    views.custom_login,   name='login'),
    path('register/', views.register_view,  name='register'),
    path('logout/',   views.logout_view,    name='logout'),
]