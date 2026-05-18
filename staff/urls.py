from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.staff_dashboard, name='staff_dashboard'),
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/checkin/', views.attendance_checkin, name='attendance_checkin'),
    path('chat/messages/', views.chat_messages, name='chat_messages'),
    path('chat/send/', views.send_message, name='send_message'),
    path('payments/', views.staff_payments, name='staff_payments'),
    path('schedule/', views.staff_schedule, name='staff_schedule'),
    path('logout/', views.staff_logout, name='staff_logout'),
]