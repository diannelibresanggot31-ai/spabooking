from django.urls import path
from . import views

urlpatterns = [
    path('', views.payment_list, name='payment_list'),
    path('staff/', views.staff_payment_overview, name='staff_payment_overview'),
]