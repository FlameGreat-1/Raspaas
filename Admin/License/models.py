import os
from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
import hashlib
from datetime import datetime, timedelta
import requests
import logging
import hmac
import base64
import psutil
import platform
from .hardware import get_hardware_fingerprint
logger = logging.getLogger("license_security")


class Company(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    date_registered = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ["-date_registered"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["uuid"]),
        ]


class SubscriptionTier(models.Model):
    TIER_CHOICES = [
        ("basic", "Basic"),
        ("standard", "Standard"),
        ("premium", "Premium"),
    ]

    DURATION_CHOICES = [
        (1, "Monthly"),
        (3, "3 Months"),
        (6, "6 Months"),
        (12, "1 Year"),
    ]

    name = models.CharField(max_length=50, choices=TIER_CHOICES)
    description = models.TextField()
    max_employees = models.IntegerField(default=50)
    max_users = models.IntegerField(default=5)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_quarterly = models.DecimalField(max_digits=10, decimal_places=2)
    price_biannual = models.DecimalField(max_digits=10, decimal_places=2)
    price_annual = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_name_display()}"

    class Meta:
        verbose_name = "Subscription Tier"
        verbose_name_plural = "Subscription Tiers"
        ordering = ["price_monthly"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def get_price_for_duration(self, duration_months):
        if duration_months == 1:
            return self.price_monthly
        elif duration_months == 3:
            return self.price_quarterly
        elif duration_months == 6:
            return self.price_biannual
        elif duration_months == 12:
            return self.price_annual
        return None


class LicenseAttempt(models.Model):
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    license_key = models.CharField(max_length=100, blank=True, null=True)
    attempt_type = models.CharField(
        max_length=20,
        choices=[
            ("activation", "Activation"),
            ("verification", "Verification"),
            ("login", "Login"),
            ("renewal", "Renewal"),
            ("revocation", "Revocation"),
        ],
    )
    cpu_info = models.CharField(max_length=255, blank=True, null=True)
    ram_info = models.CharField(max_length=100, blank=True, null=True)
    disk_info = models.CharField(max_length=255, blank=True, null=True)
    mac_address = models.CharField(max_length=100, blank=True, null=True)
    os_info = models.CharField(max_length=255, blank=True, null=True)
    hardware_fingerprint = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["ip_address", "timestamp"]),
            models.Index(fields=["license_key", "timestamp"]),
            models.Index(fields=["hardware_fingerprint"]),
        ]

    @classmethod
    def check_rate_limit(cls, ip_address, attempt_type="activation"):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        attempts = cls.objects.filter(
            ip_address=ip_address,
            timestamp__gte=one_hour_ago,
            attempt_type=attempt_type,
        ).count()

        is_allowed = attempts < 5

        if not is_allowed:
            logger.warning(f"Rate limit exceeded for IP {ip_address} ({attempt_type})")

        return is_allowed

    @classmethod
    def get_backoff_time(cls, ip_address, attempt_type="activation"):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        attempts = cls.objects.filter(
            ip_address=ip_address,
            timestamp__gte=one_hour_ago,
            attempt_type=attempt_type,
        ).count()

        if attempts >= 5:
            return 30 * (2 ** (attempts - 5))
        return 0

    @classmethod
    def log_attempt(
        cls,
        ip_address,
        success,
        license_key=None,
        user_agent=None,
        attempt_type="activation",
    ):
        try:
            try:
                cpu_info = f"{platform.processor()} ({psutil.cpu_count()} cores)"

                ram = psutil.virtual_memory()
                ram_info = f"{round(ram.total / (1024**3), 2)} GB"

                disk = psutil.disk_usage("/")
                disk_info = f"{round(disk.total / (1024**3), 2)} GB total, {round(disk.free / (1024**3), 2)} GB free"

                mac_address = ":".join(
                    [
                        "{:02x}".format((uuid.getnode() >> elements) & 0xFF)
                        for elements in range(0, 48, 8)
                    ][::-1]
                )

                os_info = (
                    f"{platform.system()} {platform.release()} ({platform.version()})"
                )

                hardware_fingerprint = get_hardware_fingerprint()

            except Exception as e:
                logger.error(f"Error collecting hardware info: {str(e)}")
                cpu_info = "Detection failed"
                ram_info = "Detection failed"
                disk_info = "Detection failed"
                mac_address = "Detection failed"
                os_info = "Detection failed"
                hardware_fingerprint = "Detection failed"

            cls.objects.create(
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                license_key=license_key,
                attempt_type=attempt_type,
                cpu_info=cpu_info,
                ram_info=ram_info,
                disk_info=disk_info,
                mac_address=mac_address,
                os_info=os_info,
                hardware_fingerprint=hardware_fingerprint,
            )

            if not success:
                logger.warning(
                    f"Failed {attempt_type} attempt from IP {ip_address} for key ending in {license_key[-8:] if license_key else 'N/A'}"
                )
        except Exception as e:
            logger.error(f"Error logging license attempt: {str(e)}")

    @classmethod
    def get_backoff_time(cls, ip_address, attempt_type="activation"):
        one_hour_ago = timezone.now() - timedelta(hours=1)
        attempts = cls.objects.filter(
            ip_address=ip_address,
            timestamp__gte=one_hour_ago,
            success=False,
            attempt_type=attempt_type,
        ).count()

        return min(2**attempts, 3600)


class License(models.Model):
    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, related_name="license"
    )
    subscription_tier = models.ForeignKey(
        SubscriptionTier, on_delete=models.PROTECT, related_name="licenses"
    )
    license_key = models.CharField(max_length=100, unique=True, editable=False)
    issue_date = models.DateField(auto_now_add=True)
    start_date = models.DateField()
    expiration_date = models.DateField()
    duration_months = models.IntegerField(choices=SubscriptionTier.DURATION_CHOICES)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    hardware_fingerprint = models.CharField(max_length=255, blank=True, null=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    last_online_check = models.DateTimeField(null=True, blank=True)
    online_check_required = models.BooleanField(default=True)
    max_offline_days = models.IntegerField(default=30)
    remotely_revoked = models.BooleanField(default=False)
    was_revoked = models.BooleanField(default=False)
    revocation_reason = models.CharField(max_length=255, blank=True, null=True)
    activation_count = models.IntegerField(default=0)
    max_activations = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    license_server_url = models.URLField(blank=True)
    integrity_signature = models.CharField(max_length=255, blank=True, null=True)
    last_failed_verification = models.DateTimeField(null=True, blank=True)
    failed_verification_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.company.name} - {self.subscription_tier.name} - {self.license_key[-8:]}"

    class Meta:
        verbose_name = "License"
        verbose_name_plural = "Licenses"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["license_key"]),
            models.Index(fields=["expiration_date"]),
        ]

    def save(self, *args, **kwargs):
        if not self.license_key:
            base = f"{self.company.uuid}-{self.subscription_tier.name}-{self.expiration_date}-{uuid.uuid4()}"
            self.license_key = hashlib.sha256(base.encode()).hexdigest()

        if not self.license_server_url:
            self.license_server_url = settings.LICENSE_VERIFICATION_URL

        self.generate_integrity_signature()

        super().save(*args, **kwargs)

    def generate_integrity_signature(self):
        if hasattr(settings, "LICENSE_SECRET_KEY") and settings.LICENSE_SECRET_KEY:
            secret = settings.LICENSE_SECRET_KEY.encode()
        else:
            secret = settings.SECRET_KEY.encode()

        data = f"{self.license_key}|{self.company.uuid}|{self.expiration_date}|{self.is_active}|{self.remotely_revoked}"
        signature = hmac.new(secret, data.encode(), hashlib.sha256).digest()
        self.integrity_signature = base64.b64encode(signature).decode()

    def verify_integrity(self):
        if not self.integrity_signature:
            logger.warning(
                f"License {self.license_key[-8:]} has no integrity signature"
            )
            return False

        current = self.integrity_signature
        self.generate_integrity_signature()
        expected = self.integrity_signature
        self.integrity_signature = current

        if expected != current:
            logger.critical(
                f"License integrity check failed for {self.license_key[-8:]} - possible tampering detected"
            )
            return False
        return True

    def is_expired(self):
        return self.expiration_date < timezone.now().date()

    def days_until_expiration(self):
        if self.is_expired():
            return 0
        delta = self.expiration_date - timezone.now().date()
        return delta.days

    def has_feature(self, feature_name):
        if not self.is_active or self.is_expired() or self.remotely_revoked:
            return False
        return True

    def needs_online_verification(self):
        if not self.online_check_required:
            return False

        if not self.last_online_check:
            return True

        days_since_check = (timezone.now() - self.last_online_check).days
        return days_since_check >= self.max_offline_days

    def verify_online(self):
        if not self.online_check_required:
            return True, "Online verification not required"

        if not self.license_server_url:
            self.license_server_url = settings.LICENSE_VERIFICATION_URL
            self.save(update_fields=["license_server_url"])

        if not self.verify_integrity():
            self.failed_verification_count += 1
            self.last_failed_verification = timezone.now()
            self.save(
                update_fields=["failed_verification_count", "last_failed_verification"]
            )
            return False, "License integrity check failed"

        try:
            response = requests.post(
                self.license_server_url,
                json={
                    "license_key": self.license_key,
                    "hardware_fingerprint": self.hardware_fingerprint,
                    "company_name": self.company.name,
                    "company_email": self.company.contact_email,
                },
                timeout=10,
                verify=True,
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("revoked", False):
                    self.remotely_revoked = True
                    self.was_revoked = True
                    self.revocation_reason = data.get(
                        "reason", "License revoked by vendor"
                    )
                    self.save(
                        update_fields=[
                            "remotely_revoked",
                            "was_revoked",
                            "revocation_reason",
                            "last_online_check",
                        ]
                    )
                    return False, self.revocation_reason

                self.last_online_check = timezone.now()
                self.save(update_fields=["last_online_check"])
                return True, "License verified online"
            else:
                return False, f"Online verification failed: {response.status_code}"

        except Exception as e:
            if self.last_online_check:
                days_since_check = (timezone.now() - self.last_online_check).days
                if days_since_check < self.max_offline_days:
                    return (
                        True,
                        f"Using offline grace period ({days_since_check}/{self.max_offline_days} days)",
                    )
                else:
                    return (
                        False,
                        f"Offline grace period expired ({days_since_check} days, max {self.max_offline_days})",
                    )
            return False, f"Online verification error: {str(e)}"

    def validate(self, hardware_fingerprint=None):
        if self.remotely_revoked:
            return False, self.revocation_reason or "License has been revoked"

        if not self.is_active:
            return False, "License is inactive"

        if self.is_expired():
            return False, "License has expired"

        if hardware_fingerprint and self.hardware_fingerprint:
            if hardware_fingerprint != self.hardware_fingerprint:
                if self.activation_count >= self.max_activations:
                    return False, "Maximum activations reached"
                self.activation_count += 1
                self.hardware_fingerprint = hardware_fingerprint
                self.save(update_fields=["activation_count", "hardware_fingerprint"])

        if self.needs_online_verification():
            online_valid, message = self.verify_online()
            if not online_valid:
                return False, message

        self.last_verified = timezone.now()
        self.save(update_fields=["last_verified"])

        return True, "License is valid"

    def revoke(self, reason=None):
        self.is_active = False
        self.remotely_revoked = True
        self.was_revoked = True
        if reason:
            self.revocation_reason = reason
        self.save(
            update_fields=[
                "is_active",
                "remotely_revoked",
                "was_revoked",
                "revocation_reason",
            ]
        )

    def renew(self, duration_months, new_tier=None):
        start_date = self.expiration_date
        if start_date < timezone.now().date():
            start_date = timezone.now().date()

        self.start_date = start_date
        self.expiration_date = start_date + timedelta(days=duration_months * 30)
        self.duration_months = duration_months
        self.is_active = True
        self.remotely_revoked = False
        self.revocation_reason = None

        if new_tier:
            self.subscription_tier = new_tier

        self.amount_paid = self.subscription_tier.get_price_for_duration(
            duration_months
        )
        self.save()

    @classmethod
    def activate_license(
        cls, license_key, hardware_fingerprint, ip_address=None, user_agent=None
    ):

        is_central_server = True

        if ip_address and not LicenseAttempt.check_rate_limit(ip_address, "activation"):
            backoff_time = LicenseAttempt.get_backoff_time(ip_address, "activation")
            return (
                False,
                None,
                f"Too many activation attempts. Please try again in {backoff_time} seconds.",
            )

        if is_central_server:
            try:
                license_obj = cls.objects.get(license_key=license_key)

                if ip_address:
                    LicenseAttempt.log_attempt(
                        ip_address=ip_address,
                        success=True,
                        license_key=license_key,
                        user_agent=user_agent,
                        attempt_type="activation",
                    )

                if not license_obj.is_expired() and not license_obj.remotely_revoked:
                    if license_obj.was_revoked:
                        license_obj.was_revoked = False
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.activation_count = 1
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "was_revoked",
                                "hardware_fingerprint",
                                "activation_count",
                                "is_active",
                            ]
                        )
                        return (
                            True,
                            license_obj,
                            "Previously revoked license reactivated",
                        )
                    elif not license_obj.hardware_fingerprint:
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.activation_count = 1
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "hardware_fingerprint",
                                "activation_count",
                                "is_active",
                            ]
                        )
                        return True, license_obj, "License activated successfully"
                    elif license_obj.hardware_fingerprint == hardware_fingerprint:
                        license_obj.is_active = True
                        license_obj.save(update_fields=["is_active"])
                        return (
                            True,
                            license_obj,
                            "License already activated for this device",
                        )
                    elif license_obj.activation_count < license_obj.max_activations:
                        license_obj.activation_count += 1
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "activation_count",
                                "hardware_fingerprint",
                                "is_active",
                            ]
                        )
                        return True, license_obj, "License activated on new device"
                    else:
                        return False, None, "Maximum activations reached"
                else:
                    return False, None, "License is expired or revoked"
            except cls.DoesNotExist:
                if ip_address:
                    LicenseAttempt.log_attempt(
                        ip_address=ip_address,
                        success=False,
                        license_key=license_key,
                        user_agent=user_agent,
                        attempt_type="activation",
                    )
                return False, None, "License not found"

        activation_url = settings.LICENSE_ACTIVATION_URL
        try:
            response = requests.post(
                activation_url,
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
                    attempt_type="activation",
                )

            if success:
                data = response.json()

                company, _ = Company.objects.get_or_create(
                    name=data["company_name"],
                    defaults={
                        "contact_email": data["company_email"],
                        "contact_phone": data.get("company_phone", ""),
                        "address": data.get("company_address", ""),
                    },
                )

                tier, _ = SubscriptionTier.objects.get_or_create(
                    name=data["tier_name"],
                    defaults={
                        "description": data.get("tier_description", ""),
                        "max_employees": data.get("max_employees", 50),
                        "max_users": data.get("max_users", 5),
                        "price_monthly": data.get("price_monthly", 0),
                        "price_quarterly": data.get("price_quarterly", 0),
                        "price_biannual": data.get("price_biannual", 0),
                        "price_annual": data.get("price_annual", 0),
                    },
                )

                license_obj, created = cls.objects.get_or_create(
                    license_key=license_key,
                    defaults={
                        "company": company,
                        "subscription_tier": tier,
                        "start_date": datetime.strptime(
                            data["start_date"], "%Y-%m-%d"
                        ).date(),
                        "expiration_date": datetime.strptime(
                            data["expiration_date"], "%Y-%m-%d"
                        ).date(),
                        "duration_months": data.get("duration_months", 12),
                        "amount_paid": data.get("amount_paid", 0),
                        "hardware_fingerprint": hardware_fingerprint,
                        "max_activations": data.get("max_activations", 1),
                        "online_check_required": data.get(
                            "online_check_required", True
                        ),
                        "max_offline_days": data.get("max_offline_days", 30),
                        "is_active": True,
                        "last_online_check": timezone.now(),
                    },
                )

                if not created:
                    license_obj.hardware_fingerprint = hardware_fingerprint
                    license_obj.last_online_check = timezone.now()
                    if license_obj.was_revoked:
                        license_obj.was_revoked = False
                        license_obj.remotely_revoked = False
                        license_obj.revocation_reason = None
                        license_obj.activation_count = 1
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "hardware_fingerprint",
                                "last_online_check",
                                "was_revoked",
                                "remotely_revoked",
                                "revocation_reason",
                                "activation_count",
                                "is_active",
                            ]
                        )
                    else:
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "hardware_fingerprint",
                                "last_online_check",
                                "is_active",
                            ]
                        )

                return True, license_obj, "License activated successfully"
            else:
                return False, None, f"Activation failed: {response.status_code}"

        except Exception as e:
            if ip_address:
                LicenseAttempt.log_attempt(
                    ip_address=ip_address,
                    success=False,
                    license_key=license_key,
                    user_agent=user_agent,
                    attempt_type="activation",
                )

            try:
                license_obj = cls.objects.get(license_key=license_key)

                if not license_obj.is_expired() and not license_obj.remotely_revoked:
                    if license_obj.was_revoked:
                        license_obj.was_revoked = False
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.activation_count = 1
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "was_revoked",
                                "hardware_fingerprint",
                                "activation_count",
                                "is_active",
                            ]
                        )
                        return (
                            True,
                            license_obj,
                            "Previously revoked license reactivated",
                        )
                    elif not license_obj.hardware_fingerprint:
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=["hardware_fingerprint", "is_active"]
                        )
                        return True, license_obj, "License activated offline"
                    elif license_obj.hardware_fingerprint == hardware_fingerprint:
                        license_obj.is_active = True
                        license_obj.save(update_fields=["is_active"])
                        return (
                            True,
                            license_obj,
                            "License already activated for this device",
                        )
                    elif license_obj.activation_count < license_obj.max_activations:
                        license_obj.activation_count += 1
                        license_obj.hardware_fingerprint = hardware_fingerprint
                        license_obj.is_active = True
                        license_obj.save(
                            update_fields=[
                                "activation_count",
                                "hardware_fingerprint",
                                "is_active",
                            ]
                        )
                        return True, license_obj, "License activated on new device"
                    else:
                        return False, None, "Maximum activations reached"
                else:
                    return False, None, "License is expired or revoked"
            except cls.DoesNotExist:
                return False, None, f"Activation error: {str(e)}"
