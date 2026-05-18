from django import forms
from .models import Booking
from services.models import Service, Room

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['service', 'room', 'booking_date', 'booking_time', 'special_requests', 'payment_method']
        widgets = {
            'booking_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'booking_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'special_requests': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['room'].queryset = Room.objects.filter(is_available=True)
        self.fields['room'].required = False