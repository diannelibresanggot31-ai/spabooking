from django.contrib.auth import get_user_model
import secrets
import string

User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    pwd = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    User.objects.create_superuser('admin', 'admin@example.com', pwd)
    print('CREATED_SUPERUSER', pwd)
else:
    print('SUPERUSER_EXISTS')
