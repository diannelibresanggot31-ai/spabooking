from django.db import models
from django.conf import settings
from services.models import Service, Package, Room
import uuid

class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),          # Waiting for payment verification (GCash)
        ('verify', 'Verify'),            # Payment verified, ready for service
        ('complete', 'Complete Session'), # Service completed
        ('cancelled', 'Cancelled'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('gcash', 'GCash'),
        ('cash', 'Cash'),
    )
    
    booking_number = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    booking_date = models.DateField()
    booking_time = models.TimeField()
    duration_minutes = models.IntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    special_requests = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = f"SPA-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Booking {self.booking_number} - {self.customer.username}"
    
    def can_cancel(self):
        return self.status == 'pending' and self.payment_method == 'cash'
    
    def can_view_receipt(self):
        """Customer can view receipt when status is verify or complete"""
        return self.status in ['verify', 'complete']