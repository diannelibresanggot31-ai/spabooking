from django.contrib.auth import get_user_model
import secrets
import string

User = get_user_model()
pwd = ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(12))
user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
user.is_staff = True
user.is_superuser = True
user.set_password(pwd)
user.save()
print('ADMIN_USERNAME admin')
print('ADMIN_PASSWORD', pwd)
