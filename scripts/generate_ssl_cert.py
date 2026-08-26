"""Generate a self-signed TLS certificate for the local server.

Produces certs/cert.pem and certs/key.pem inside the app directory.
The certificate includes SAN entries for localhost, 127.0.0.1 and all
LAN IPv4 addresses so phone browsers connecting via the LAN IP will
recognize the host (the "not secure" warning can be bypassed once, then
geolocation over HTTPS becomes available).

Usage:
    python scripts/generate_ssl_cert.py
"""
import datetime
import ipaddress
import os
import socket

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
CERTS_DIR = os.path.join(ROOT, "certs")
CERT_FILE = os.path.join(CERTS_DIR, "cert.pem")
KEY_FILE = os.path.join(CERTS_DIR, "key.pem")


def _lan_addresses():
    addresses = set()
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        ip = info[4][0]
        if ip and not ip.startswith("127."):
            addresses.add(ip)
    if not addresses:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            addresses.add(s.getsockname()[0])
            s.close()
        except Exception:
            pass
    return sorted(addresses)


def main():
    os.makedirs(CERTS_DIR, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "DynamicPro Local Server"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dynamic Pro ERP"),
    ])

    san_entries = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    for ip in _lan_addresses():
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            pass

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    with open(KEY_FILE, "wb") as fh:
        fh.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(CERT_FILE, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))

    san_text = []
    for e in san_entries:
        if isinstance(e.value, str):
            san_text.append("DNS " + e.value)
        else:
            san_text.append("IP " + str(e.value))
    lines = [
        "OK - certificates generated:",
        "  cert: %s" % CERT_FILE,
        "  key:  %s" % KEY_FILE,
        "SAN hosts: %s" % ", ".join(san_text),
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
