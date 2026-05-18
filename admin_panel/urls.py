from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('user-history/', views.user_history, name='user_history'),
    path('user-info/', views.user_info, name='user_info'),
    path('staff-attendance/', views.staff_attendance, name='staff_attendance'),
    path('edit-staff/', views.edit_staff, name='edit_staff'),
    path('delete-staff/<int:staff_id>/', views.delete_staff, name='delete_staff'),
    path('revenue/', views.revenue, name='revenue'),
    path('services/', views.services, name='services'),
    path('delete-service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('packages/', views.packages, name='packages'),
    path('delete-package/<int:package_id>/', views.delete_package, name='delete_package'),
    path('rooms/', views.rooms, name='rooms'),
    path('delete-room/<int:room_id>/', views.delete_room, name='delete_room'),
    path('bookings/', views.bookings, name='bookings'),
    path('update-booking/<int:booking_id>/', views.update_booking_status, name='update_booking'),
    path('verify-payment/<int:payment_id>/', views.verify_payment, name='verify_payment'),
    path('chat/', views.chat_with_staff, name='chat_with_staff'),
    path('customer-inquiries/', views.customer_inquiries, name='customer_inquiries'),
    path('send-message/', views.send_chat_message, name='send_chat_message'),
]