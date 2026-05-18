from django.db import models
from django.conf import settings
from django.utils import timezone

class StaffAttendance(models.Model):
    ATTENDANCE_STATUS = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
    )
    
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'staff'})
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS, default='absent')
    reason = models.TextField(blank=True, null=True, help_text="Reason for absence (only required when status is 'absent')")
    photo = models.ImageField(upload_to='attendance/', blank=True, null=True)
    
    class Meta:
        unique_together = ['staff', 'date']
    
    def __str__(self):
        return f"{self.staff.username} - {self.date}"

class StaffSchedule(models.Model):
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='schedules', limit_choices_to={'role': 'staff'})
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['staff', 'date', 'start_time']
    
    def __str__(self):
        return f"{self.staff.username} - {self.date}"

class ChatMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.message[:50]}"