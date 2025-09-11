import hashlib
import platform
import uuid
import socket
import re
import json
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from .models import License

def generate_license_key(company_uuid, tier_name, expiration_date, salt=None):
    if not salt:
        salt = uuid.uuid4().hex

    base = f"{company_uuid}-{tier_name}-{expiration_date}-{salt}"
    license_key = hashlib.sha256(base.encode()).hexdigest()

    return license_key


def format_license_key(license_key):
    chunks = [license_key[i : i + 5] for i in range(0, len(license_key), 5)]
    return "-".join(chunks[:5])


def get_hardware_fingerprint():
    system_info = platform.uname()

    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
    except:
        hostname = "unknown"
        ip_address = "0.0.0.0"

    try:
        mac_address = ":".join(re.findall("..", "%012x" % uuid.getnode()))
    except:
        mac_address = "00:00:00:00:00:00"

    cpu_info = system_info.processor
    machine_type = system_info.machine

    fingerprint_data = (
        f"{hostname}-{ip_address}-{mac_address}-{cpu_info}-{machine_type}"
    )
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()

    return fingerprint


def validate_license(license_obj, hardware_fingerprint=None):
    if not license_obj:
        return False, "No license found"

    if license_obj.remotely_revoked:
        return False, license_obj.revocation_reason or "License has been revoked"

    if not license_obj.is_active:
        return False, "License is inactive"

    if license_obj.is_expired():
        return False, "License has expired"

    if hardware_fingerprint:
        if not license_obj.hardware_fingerprint:
            license_obj.activation_count += 1
            license_obj.hardware_fingerprint = hardware_fingerprint
            license_obj.save(update_fields=["activation_count", "hardware_fingerprint"])
        elif license_obj.hardware_fingerprint != hardware_fingerprint:
            if license_obj.activation_count >= license_obj.max_activations:
                return False, "Maximum activations reached"

            license_obj.activation_count += 1
            license_obj.hardware_fingerprint = hardware_fingerprint
            license_obj.save(update_fields=["activation_count", "hardware_fingerprint"])

    license_obj.last_verified = timezone.now()
    license_obj.save(update_fields=["last_verified"])

    if license_obj.needs_online_verification():
        try:
            online_valid, message = license_obj.verify_online()
            if not online_valid and "offline grace period" not in message:
                return False, message
        except Exception as e:
            if license_obj.last_online_check:
                days_since_check = (timezone.now() - license_obj.last_online_check).days
                if days_since_check >= license_obj.max_offline_days:
                    return False, f"Online verification required: {str(e)}"

    return True, "License is valid"


def check_license_validity(request):
    try:
        license_obj = License.objects.filter(is_active=True).first()

        if not license_obj:
            return False

        hardware_fingerprint = get_hardware_fingerprint()
        is_valid, message = validate_license(license_obj, hardware_fingerprint)

        if not is_valid:
            messages.error(request, f"License issue: {message}")
            return False

        return True
    except Exception as e:
        if settings.DEBUG:
            messages.error(request, f"License validation error: {str(e)}")
        return False


def encrypt_license_data(license_obj):
    data = {
        'company_id': str(license_obj.company.uuid),
        'company_name': license_obj.company.name,
        'company_email': license_obj.company.contact_email,
        'tier': license_obj.subscription_tier.name,
        'max_employees': license_obj.subscription_tier.max_employees,
        'max_users': license_obj.subscription_tier.max_users,
        'expiration': license_obj.expiration_date.isoformat(),
        'key': license_obj.license_key,
        'hardware': license_obj.hardware_fingerprint,
        'online_check_required': license_obj.online_check_required,
        'max_offline_days': license_obj.max_offline_days,
        'max_activations': license_obj.max_activations,
    }
    
    json_data = json.dumps(data)
    encrypted = hashlib.sha256(json_data.encode()).hexdigest()
    
    return f"{json_data}|{encrypted}"


def decrypt_license_data(encrypted_data):
    try:
        json_data, hash_value = encrypted_data.split('|')
        
        calculated_hash = hashlib.sha256(json_data.encode()).hexdigest()
        if calculated_hash != hash_value:
            return None
            
        return json.loads(json_data)
    except:
        return None


def verify_license_online(license_key, hardware_fingerprint, server_url=None):
    if not server_url:
        server_url = settings.LICENSE_VERIFICATION_URL

    try:
        response = requests.post(
            server_url,
            json={
                'license_key': license_key,
                'hardware_fingerprint': hardware_fingerprint
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('valid', False), data.get('message', ''), data
        else:
            return False, f"Server returned status code: {response.status_code}", None

    except Exception as e:
        return False, f"Connection error: {str(e)}", None
