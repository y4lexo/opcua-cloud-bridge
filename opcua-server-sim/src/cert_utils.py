"""Certificate utilities for OPC UA server security"""

import os
import logging
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

logger = logging.getLogger(__name__)


def generate_self_signed_certificate(cert_dir: str = "certs", 
                                   server_name: str = "OPCUA-Simulation-Server") -> tuple[str, str]:
    """
    Generate self-signed certificate and private key for OPC UA server
    
    Args:
        cert_dir: Directory to store certificates
        server_name: Common name for the certificate
        
    Returns:
        Tuple of (cert_file_path, key_file_path)
    """
    cert_path = Path(cert_dir)
    cert_path.mkdir(exist_ok=True)
    
    cert_file = cert_path / "server_cert.der"
    key_file = cert_path / "server_private_key.pem"
    
    if cert_file.exists() and key_file.exists():
        logger.info("Certificates already exist, skipping generation")
        return str(cert_file), str(key_file)
    
    logger.info("Generating self-signed certificate...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GlobalCorp"),
        x509.NameAttribute(NameOID.COMMON_NAME, server_name),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(server_name),
            x509.DNSName("localhost"),
            x509.IPAddress("127.0.0.1"),
            x509.IPAddress("0.0.0.0"),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # Write certificate to file
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.DER))
    
    # Write private key to file
    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    logger.info(f"Certificate generated: {cert_file}")
    logger.info(f"Private key generated: {key_file}")
    
    return str(cert_file), str(key_file)


def create_trust_store(cert_dir: str = "certs") -> str:
    """
    Create trust store directory for client certificates
    
    Args:
        cert_dir: Directory to store trust store
        
    Returns:
        Path to trust store directory
    """
    trust_path = Path(cert_dir) / "trust"
    trust_path.mkdir(exist_ok=True)
    
    # Create empty trust store file
    trust_file = trust_path / "trust.der"
    if not trust_file.exists():
        trust_file.touch()
        logger.info(f"Created trust store: {trust_file}")
    
    return str(trust_path)
