import psutil
import platform
import uuid
from django.test import TestCase
from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from .utils import get_hardware_fingerprint
from .models import License


def test_hardware_binding(request):
    verification_url = getattr(settings, "LICENSE_VERIFICATION_URL", "Not found")

    current_fingerprint = get_hardware_fingerprint()
    license_obj = License.objects.filter(
        license_key="1bb587625375c84933d985acef0f28d8bd41ed0d3a3043331c96fcbf6f3867f1"
    ).first()

    if not license_obj:
        return HttpResponse("License not found")

    stored_fingerprint = license_obj.hardware_fingerprint

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

        os_info = f"{platform.system()} {platform.release()} ({platform.version()})"

    except Exception as e:
        cpu_info = "Detection failed"
        ram_info = "Detection failed"
        disk_info = "Detection failed"
        mac_address = "Detection failed"
        os_info = "Detection failed"

    online_verification_success = False
    online_verification_message = "Verification failed"
    if hasattr(license_obj, "last_online_check") and license_obj.last_online_check:
        online_verification_success = True
        online_verification_message = (
            "Last successful verification: "
            + license_obj.last_online_check.strftime("%Y-%m-%d %H:%M:%S")
        )

    context = {
        "current_fingerprint": current_fingerprint,
        "stored_fingerprint": stored_fingerprint,
        "match": current_fingerprint == stored_fingerprint,
        "activation_count": license_obj.activation_count,
        "max_activations": license_obj.max_activations,
        "verification_url": verification_url,
        "last_online_check": license_obj.last_online_check,
        "cpu_info": cpu_info,
        "ram_info": ram_info,
        "disk_info": disk_info,
        "mac_address": mac_address,
        "os_info": os_info,
        "online_verification_success": online_verification_success,
        "online_verification_message": online_verification_message,
    }

    return render(request, "license/test_binding.html", context)
