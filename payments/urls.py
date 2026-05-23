from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('verify/<int:payment_id>/', views.verify_payment_direct, name='verify_payment_direct'),
    path('admin-verify/<int:payment_id>/', views.verify_payment_admin, name='verify_payment_admin'),
    path('list/', views.payment_list, name='payment_list'),
    path('staff-overview/', views.staff_payment_overview, name='staff_payment_overview'),
]