import hashlib
import platform
import uuid
import socket
import re
import json
import requests
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from .models import License, LicenseAttempt

logger = logging.getLogger("license_security")


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


def validate_license(
    license_obj, hardware_fingerprint=None, ip_address=None, user_agent=None
):
    if not license_obj:
        logger.warning(
            f"License validation failed: No license found for IP {ip_address}"
        )
        return False, "No license found"

    if not license_obj.verify_integrity():
        logger.critical(f"License integrity check failed for IP {ip_address}")
        return False, "License integrity check failed"

    if license_obj.remotely_revoked:
        logger.warning(
            f"License validation failed: License revoked for IP {ip_address}"
        )
        return False, license_obj.revocation_reason or "License has been revoked"

    if not license_obj.is_active:
        logger.warning(
            f"License validation failed: License inactive for IP {ip_address}"
        )
        return False, "License is inactive"

    if license_obj.is_expired():
        logger.warning(
            f"License validation failed: License expired for IP {ip_address}"
        )
        return False, "License has expired"

    if hardware_fingerprint:
        if not license_obj.hardware_fingerprint:
            license_obj.activation_count += 1
            license_obj.hardware_fingerprint = hardware_fingerprint
            license_obj.save(update_fields=["activation_count", "hardware_fingerprint"])
            logger.info(
                f"New hardware fingerprint registered for license {license_obj.license_key[-8:]}"
            )
        elif license_obj.hardware_fingerprint != hardware_fingerprint:
            if license_obj.activation_count >= license_obj.max_activations:
                logger.warning(
                    f"License validation failed: Maximum activations reached for IP {ip_address}"
                )
                return False, "Maximum activations reached"

            license_obj.activation_count += 1
            license_obj.hardware_fingerprint = hardware_fingerprint
            license_obj.save(update_fields=["activation_count", "hardware_fingerprint"])
            logger.info(
                f"New hardware fingerprint registered for license {license_obj.license_key[-8:]} (activation {license_obj.activation_count}/{license_obj.max_activations})"
            )

    license_obj.last_verified = timezone.now()
    license_obj.save(update_fields=["last_verified"])

    if license_obj.needs_online_verification():
        try:
            if ip_address:
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=True,
                    license_key=license_obj.license_key,
                    user_agent=user_agent,
                    attempt_type="verification",
                )

            online_valid, message = license_obj.verify_online()
            if not online_valid and "offline grace period" not in message:
                logger.warning(
                    f"Online verification failed: {message} for IP {ip_address}"
                )
                return False, message
        except Exception as e:
            logger.error(f"Online verification error: {str(e)} for IP {ip_address}")
            if license_obj.last_online_check:
                days_since_check = (timezone.now() - license_obj.last_online_check).days
                if days_since_check >= license_obj.max_offline_days:
                    return False, f"Online verification required: {str(e)}"

    return True, "License is valid"


def check_license_validity(request):
    ip_address = request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT")

    try:
        license_obj = License.objects.filter(is_active=True).first()

        if not license_obj:
            logger.warning(f"No active license found for IP {ip_address}")
            return False

        hardware_fingerprint = get_hardware_fingerprint()
        is_valid, message = validate_license(
            license_obj, hardware_fingerprint, ip_address, user_agent
        )

        if not is_valid:
            messages.error(request, f"License issue: {message}")
            return False

        return True
    except Exception as e:
        logger.error(f"License validation error: {str(e)} for IP {ip_address}")
        if settings.DEBUG:
            messages.error(request, f"License validation error: {str(e)}")
        return False


def encrypt_license_data(license_obj):
    data = {
        "company_id": str(license_obj.company.uuid),
        "company_name": license_obj.company.name,
        "company_email": license_obj.company.contact_email,
        "tier": license_obj.subscription_tier.name,
        "max_employees": license_obj.subscription_tier.max_employees,
        "max_users": license_obj.subscription_tier.max_users,
        "expiration": license_obj.expiration_date.isoformat(),
        "key": license_obj.license_key,
        "hardware": license_obj.hardware_fingerprint,
        "online_check_required": license_obj.online_check_required,
        "max_offline_days": license_obj.max_offline_days,
        "max_activations": license_obj.max_activations,
    }

    json_data = json.dumps(data)

    if hasattr(settings, "LICENSE_SECRET_KEY") and settings.LICENSE_SECRET_KEY:
        secret = settings.LICENSE_SECRET_KEY.encode()
    else:
        secret = settings.SECRET_KEY.encode()

    import hmac
    import base64

    signature = hmac.new(secret, json_data.encode(), hashlib.sha256).digest()
    encrypted = base64.b64encode(signature).decode()

    return f"{json_data}|{encrypted}"


def decrypt_license_data(encrypted_data):
    try:
        json_data, signature = encrypted_data.split("|")

        if hasattr(settings, "LICENSE_SECRET_KEY") and settings.LICENSE_SECRET_KEY:
            secret = settings.LICENSE_SECRET_KEY.encode()
        else:
            secret = settings.SECRET_KEY.encode()

        import hmac
        import base64

        expected_signature = hmac.new(
            secret, json_data.encode(), hashlib.sha256
        ).digest()
        expected_signature_b64 = base64.b64encode(expected_signature).decode()

        if expected_signature_b64 != signature:
            logger.critical(f"License data tampering detected")
            return None

        return json.loads(json_data)
    except Exception as e:
        logger.error(f"Error decrypting license data: {str(e)}")
        return None


def verify_license_online(
    license_key, hardware_fingerprint, server_url=None, ip_address=None, user_agent=None
):
    if not server_url:
        server_url = settings.LICENSE_VERIFICATION_URL

    if ip_address and not LicenseAttempt.check_rate_limit(ip_address, "verification"):
        backoff_time = LicenseAttempt.get_backoff_time(ip_address, "verification")
        logger.warning(f"Rate limit exceeded for IP {ip_address} (verification)")
        return (
            False,
            f"Too many verification attempts. Please try again in {backoff_time} seconds.",
            None,
        )

    try:
        response = requests.post(
            server_url,
            json={
                "license_key": license_key,
                "hardware_fingerprint": hardware_fingerprint,
            },
            timeout=10,
            verify=True,
        )

        success = response.status_code == 200
        if ip_address:
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=success,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )

        if success:
            data = response.json()
            return data.get("valid", False), data.get("message", ""), data
        else:
            logger.warning(
                f"License verification failed with status code {response.status_code} for IP {ip_address}"
            )
            return False, f"Server returned status code: {response.status_code}", None

    except Exception as e:
        if ip_address:
            LicenseAttempt.log_attempt(
                ip_address=ip_address,
                success=False,
                license_key=license_key,
                user_agent=user_agent,
                attempt_type="verification",
            )
        logger.error(
            f"License verification connection error: {str(e)} for IP {ip_address}"
        )
        return False, f"Connection error: {str(e)}", None
