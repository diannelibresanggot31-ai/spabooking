from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Staff Management
    path('staff-attendance-review/', views.staff_attendance_review, name='staff_attendance_review'),
    path('delete-attendance/<int:attendance_id>/', views.delete_attendance, name='delete_attendance'),
    
    # Staff Schedule
    path('staff-schedule/', views.staff_schedule_list, name='staff_schedule_list'),
    path('staff-schedule/add/', views.staff_schedule_add, name='staff_schedule_add'),
    path('staff-schedule/edit/<int:schedule_id>/', views.staff_schedule_edit, name='staff_schedule_edit'),
    path('staff-schedule/delete/<int:schedule_id>/', views.staff_schedule_delete, name='staff_schedule_delete'),
    
    # Booking Management
    path('bookings/', views.bookings, name='bookings'),
    path('update-booking/<int:booking_id>/', views.update_booking_status, name='update_booking'),
    
    # Revenue
    path('revenue/', views.revenue, name='revenue'),
    
    # Chat
    path('chat/', views.chat_with_staff, name='chat_with_staff'),
    path('customer-inquiries/', views.customer_inquiries, name='customer_inquiries'),
    path('send-message/', views.send_chat_message, name='send_chat_message'),
    
    # Message Deletion (Soft Delete)
    path('delete-message/<int:message_id>/', views.delete_message, name='delete_message'),
    path('clear-chat/<int:user_id>/', views.clear_chat_history, name='clear_chat_history'),
]