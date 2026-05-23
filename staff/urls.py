from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('dashboard/', views.staff_dashboard, name='dashboard'),
    path('attendance/', views.attendance, name='attendance'),
    path('schedule/', views.staff_schedule, name='schedule'),
    path('payments/', views.staff_payments, name='payments'),
    path('chat-messages/', views.chat_messages, name='chat_messages'),
    path('send-message/', views.send_message, name='send_message'),
    path('attendance/checkin/', views.attendance_checkin, name='attendance_checkin'),
    path('logout/', views.staff_logout, name='logout'),
]