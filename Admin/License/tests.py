from django.test import TestCase
from django.http import HttpResponse
from django.shortcuts import render
from django.conf import settings
from .utils import get_hardware_fingerprint
from .models import License


def test_hardware_binding(request):
    # Debug settings
    verification_url = getattr(settings, "LICENSE_VERIFICATION_URL", "Not found")

    current_fingerprint = get_hardware_fingerprint()
    license_obj = License.objects.filter(
        license_key="1bb587625375c84933d985acef0f28d8bd41ed0d3a3043331c96fcbf6f3867f1"
    ).first()

    if not license_obj:
        return HttpResponse("License not found")

    stored_fingerprint = license_obj.hardware_fingerprint

    context = {
        "current_fingerprint": current_fingerprint,
        "stored_fingerprint": stored_fingerprint,
        "match": current_fingerprint == stored_fingerprint,
        "activation_count": license_obj.activation_count,
        "max_activations": license_obj.max_activations,
        "verification_url": verification_url,  
    }

    return render(request, "license/test_binding.html", context)
