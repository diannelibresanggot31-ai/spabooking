from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='🌸')
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class SliderImage(models.Model):
    title = models.CharField(max_length=100, blank=True)
    subtitle = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='slider/')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title or "Slider Image"

class Service(models.Model):
    CATEGORY_CHOICES = (
        ('massage', 'Massage'),
        ('spa', 'Spa Services'),
        ('body_sculpt', 'Body Sculpt'),
        ('foot', 'Foot Massage'),
        ('traditional', 'Traditional Massage'),
    )
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    service_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='services')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(default=60)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    requires_room = models.BooleanField(default=False)
    likes = models.ManyToManyField('accounts.User', blank=True, related_name='liked_services')

    def __str__(self):
        return f"{self.name} - ₱{self.price}"
    
    @property
    def like_count(self):
        return self.likes.count()

class Package(models.Model):
    name = models.CharField(max_length=100)
    services = models.ManyToManyField(Service, related_name='packages')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount percentage (e.g., 10 for 10%)")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₱{self.price}"

    @property
    def requires_room(self):
        return self.services.filter(requires_room=True).exists()

    @property
    def total_duration_minutes(self):
        return self.services.aggregate(total=models.Sum('duration_minutes'))['total'] or 60

    @property
    def service_count(self):
        return self.services.count()

class Room(models.Model):
    ROOM_TYPES = (
        ('single', 'Single Room'),
        ('couple', 'Couple Room'),
    )
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"Room {self.room_number} ({self.get_room_type_display()})"