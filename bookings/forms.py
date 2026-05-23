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
        
    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        booking_time = cleaned_data.get('booking_time')
        service = cleaned_data.get('service')
        
        # Check if booking date is not Sunday
        if booking_date and booking_date.weekday() == 6:  # Sunday = 6
            raise forms.ValidationError("We are closed on Sundays. Please select a date from Monday to Saturday.")
        
        # Check if booking time is within business hours
        if booking_time:
            hour = booking_time.hour
            if hour < 8 or hour >= 17 or (hour == 12):
                raise forms.ValidationError("Business hours are 8 AM - 5 PM (closed 12 PM - 1 PM for lunch).")
        
        return cleaned_data