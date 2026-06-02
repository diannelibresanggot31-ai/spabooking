import re
from django import forms
from .models import User

class CustomUserCreationForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        error_messages={
            'required': 'Please enter your email address.',
            'invalid': 'Please enter a valid email address.',
        }
    )
    phone = forms.CharField(
        max_length=13,
        required=True,
        error_messages={'required': 'Please enter your phone number.'}
    )
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput,
        error_messages={'required': 'Please enter a password.'}
    )
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput,
        error_messages={'required': 'Please confirm your password.'}
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'password1', 'password2')
        error_messages = {
            'username': {
                'required': 'Please enter your username.',
                'unique': 'This username is already taken. Please choose another one.',
            },
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken. Please choose another one.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered. Please use another email or log in.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not re.match(r'^(09|\+639)\d{9}$', phone):
            raise forms.ValidationError('Please enter a valid Philippine mobile number, like 09XXXXXXXXX or +639XXXXXXXXX.')
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Passwords do not match. Please type the same password again.')

        return cleaned_data
    
    def save(self, commit=True):
        user = User(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            phone=self.cleaned_data['phone'],
        )
        user.set_password(self.cleaned_data['password1'])
        user.role = 'customer'  # All new registrations are customers
        user.is_active = True   # Make sure user is active
        if commit:
            user.save()
        return user
