from django.contrib import admin
from django.utils.html import format_html
from .models import StaffAttendance, StaffSchedule, ChatMessage

@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'check_in_time', 'check_out_time', 'status_badge')
    list_filter = ('status', 'date')
    search_fields = ('staff__username',)
    date_hierarchy = 'date'
    readonly_fields = ('check_in', 'check_out', 'photo_preview')
    
    def check_in_time(self, obj):
        return obj.check_in.strftime('%I:%M %p') if obj.check_in else '—'
    check_in_time.short_description = "Time In"

    def check_out_time(self, obj):
        return obj.check_out.strftime('%I:%M %p') if obj.check_out else '—'
    check_out_time.short_description = "Time Out"

    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'present': '#28a745', 'late': '#ffc107', 'absent': '#dc3545', 'half_day': '#17a2b8'}
        return format_html('<span style="background:{}; color:white; padding:4px 12px; border-radius:20px">{}</span>', 
                          colors.get(obj.status, '#6c757d'), obj.status.upper())
    status_badge.short_description = "Status"
    
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width: 100px; border-radius: 8px;" />', obj.photo.url)
        return "No photo"
    photo_preview.short_description = "Photo"


@admin.register(StaffSchedule)
class StaffScheduleAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'start_time', 'end_time', 'is_available_badge', 'view_bookings')
    list_filter = ('is_available', 'date', 'staff')
    search_fields = ('staff__username', 'staff__email')
    date_hierarchy = 'date'
    # Remove list_editable or add 'is_available' to list_display
    # list_editable = ('is_available',)  # Comment this out or remove it
    list_per_page = 50
    
    fieldsets = (
        ('Staff Information', {
            'fields': ('staff',)
        }),
        ('Schedule Details', {
            'fields': ('date', 'start_time', 'end_time', 'is_available')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('wide',),
        }),
    )
    
    def is_available_badge(self, obj):
        if obj.is_available:
            return format_html('<span style="color: #28a745;">✅ Available</span>')
        return format_html('<span style="color: #dc3545;">❌ Unavailable</span>')
    is_available_badge.short_description = "Status"
    
    def view_bookings(self, obj):
        from django.urls import reverse
        count = obj.staff.bookings.filter(booking_date=obj.date, status__in=['pending', 'verify']).count()
        if count > 0:
            url = reverse('admin:bookings_booking_changelist') + f'?booking_date={obj.date}&customer__id__exact={obj.staff.id}'
            return format_html('<a href="{}" target="_blank">📅 {} booking(s)</a>', url, count)
        return "No bookings"
    view_bookings.short_description = "Bookings"


# Optionally register ChatMessage
# @admin.register(ChatMessage)
# class ChatMessageAdmin(admin.ModelAdmin):
#     list_display = ('sender', 'receiver', 'timestamp', 'is_read')
#     list_filter = ('is_read', 'timestamp')
#     search_fields = ('sender__username', 'receiver__username', 'message')