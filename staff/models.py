from django.db import models
from django.conf import settings
from django.utils import timezone

class StaffAttendance(models.Model):
    ATTENDANCE_STATUS = (
        ('pending', 'Pending'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
    )
    
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'staff'})
    date = models.DateField(default=timezone.now)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS, default='pending')
    reason = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='attendance/', blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_attendances')
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['staff', 'date']
    
    def __str__(self):
        return f"{self.staff.username} - {self.date}"


class StaffSchedule(models.Model):
    """Staff work schedule - assigned by admin"""
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='schedules', limit_choices_to={'role': 'staff'})
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(null=True, blank=True)  # Remove auto_now_add
    updated_at = models.DateTimeField(null=True, blank=True)  # Remove auto_now
    
    class Meta:
        unique_together = ['staff', 'date']
        ordering = ['date', 'start_time']
    
    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.staff.username} - {self.date} ({self.start_time} to {self.end_time})"

class ChatMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    deleted_by_sender = models.BooleanField(default=False)
    deleted_by_receiver = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.message[:50]}"
    
    def delete_for_user(self, user):
        if user == self.sender:
            self.deleted_by_sender = True
        elif user == self.receiver:
            self.deleted_by_receiver = True
        else:
            return False
        self.save(update_fields=['deleted_by_sender', 'deleted_by_receiver'])
        return True