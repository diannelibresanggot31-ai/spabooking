from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.old_dashboard, name='dashboard'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('staff-dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('like/<int:service_id>/', views.toggle_like, name='toggle_like'),
    path('login/', views.custom_login, name='login'),
    path('register/', views.register_view, name='register'),
]