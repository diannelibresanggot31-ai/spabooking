from django.contrib import admin
from django.utils.html import format_html
from .models import StaffAttendance, StaffSchedule, ChatMessage

@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'check_in_time', 'check_out_time', 'status_badge')
    list_filter = ('status', 'date')
    search_fields = ('staff__username',)
    date_hierarchy = 'date'
    
    def check_in_time(self, obj):
        return obj.check_in.strftime('%I:%M %p') if obj.check_in else '—'
    check_in_time.short_description = "Check In"
    
    def check_out_time(self, obj):
        return obj.check_out.strftime('%I:%M %p') if obj.check_out else '—'
    check_out_time.short_description = "Check Out"
    
    def status_badge(self, obj):
        colors = {'present': '#28a745', 'late': '#ffc107', 'absent': '#dc3545', 'half_day': '#17a2b8'}
        return format_html('<span style="background:{}; color:white; padding:4px 12px; border-radius:20px">{}</span>', 
                          colors.get(obj.status, '#6c757d'), obj.status.upper())
    status_badge.short_description = "Status"

@admin.register(StaffSchedule)
class StaffScheduleAdmin(admin.ModelAdmin):
    list_display = ('staff', 'date', 'start_time', 'end_time', 'is_available')
    list_filter = ('is_available', 'date')
    search_fields = ('staff__username',)
    date_hierarchy = 'date'

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'receiver__username', 'message')
    readonly_fields = ('timestamp', 'sender', 'receiver', 'message')