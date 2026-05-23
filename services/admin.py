# services/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Service, Package, Room, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'duration_minutes', 'is_active')
    search_fields = ('name',)
    list_per_page = 25
    list_editable = ('price', 'is_active')

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'discount_percentage', 'is_active')
    list_editable = ('price', 'is_active')
    search_fields = ('name',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'is_available')
    search_fields = ('room_number',)
    list_editable = ('is_available',)