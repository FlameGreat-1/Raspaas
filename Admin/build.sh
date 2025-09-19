#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Creating migrations..."
python manage.py makemigrations accounts
python manage.py makemigrations core
python manage.py makemigrations employees
python manage.py makemigrations attendance
python manage.py makemigrations payroll
python manage.py makemigrations expenses
python manage.py makemigrations accounting
python manage.py makemigrations License

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running database migrations..."
python manage.py migrate --fake-initial

echo "Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
admin_email = os.environ.get('ADMIN_EMAIL', 'admin@Raspaas.com')
admin_password = 'admin123'  

if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        employee_code='admin',
        email=admin_email,
        password=admin_password,
        first_name='Admin',
        last_name='User'
    )
    print('Superuser created successfully')
else:
    print('Superuser already exists')
    # Update password for existing superuser
    superuser = User.objects.filter(is_superuser=True).first()
    superuser.set_password(admin_password)
    superuser.save()
    print('Superuser password updated')
"

echo "Build completed successfully!"
