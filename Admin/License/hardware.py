import hashlib
import platform
import uuid
import socket
import re


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
