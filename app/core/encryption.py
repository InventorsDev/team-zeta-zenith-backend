import base64
import hashlib
import os
from typing import Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .config import get_settings

settings = get_settings()


def _get_encryption_key(salt: bytes) -> bytes:
    """
    Generate encryption key from secret key and salt

    Args:
        salt: Cryptographic salt (must be at least 16 bytes)

    Returns:
        Encryption key suitable for Fernet
    """
    password = settings.secret_key.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key


def encrypt_data(data: str, organization_id: int = None) -> str:
    """
    Encrypt sensitive data with a random salt

    The encrypted format is: base64(salt + encrypted_data)
    This allows each encryption to use a unique salt for better security

    Args:
        data: Plain text data to encrypt
        organization_id: Optional organization ID for org-specific encryption

    Returns:
        Base64-encoded string containing salt and encrypted data
    """
    if not data:
        return data

    try:
        # Generate a random 32-byte salt for this encryption
        salt = os.urandom(32)

        # If organization_id provided, mix it into the salt for org-specific encryption
        if organization_id is not None:
            org_bytes = str(organization_id).encode()
            # Mix org ID into salt using XOR
            salt = bytes(a ^ b for a, b in zip(salt, (org_bytes * (32 // len(org_bytes) + 1))[:32]))

        # Generate encryption key from salt
        key = _get_encryption_key(salt)
        f = Fernet(key)

        # Encrypt the data
        encrypted_data = f.encrypt(data.encode())

        # Combine salt + encrypted data
        combined = salt + encrypted_data

        # Encode as base64 for storage
        return base64.urlsafe_b64encode(combined).decode()

    except Exception as e:
        # Log the error but don't expose details
        import logging
        logging.error(f"Encryption failed: {e}")
        raise ValueError("Failed to encrypt data")


def decrypt_data(encrypted_data: str, organization_id: int = None) -> str:
    """
    Decrypt sensitive data that was encrypted with encrypt_data

    Args:
        encrypted_data: Base64-encoded string containing salt and encrypted data
        organization_id: Optional organization ID (must match encryption)

    Returns:
        Decrypted plain text string
    """
    if not encrypted_data:
        return encrypted_data

    try:
        # Decode from base64
        combined = base64.urlsafe_b64decode(encrypted_data.encode())

        # Extract salt (first 32 bytes)
        salt = combined[:32]
        encrypted_bytes = combined[32:]

        # If organization_id was used during encryption, apply same mixing
        if organization_id is not None:
            org_bytes = str(organization_id).encode()
            salt = bytes(a ^ b for a, b in zip(salt, (org_bytes * (32 // len(org_bytes) + 1))[:32]))

        # Generate decryption key from salt
        key = _get_encryption_key(salt)
        f = Fernet(key)

        # Decrypt the data
        decrypted_data = f.decrypt(encrypted_bytes)
        return decrypted_data.decode()

    except Exception as e:
        # Log the error
        import logging
        logging.error(f"Decryption failed: {e}")
        # Return empty string for backwards compatibility with old unencrypted data
        return ""


def hash_data(data: str) -> str:
    """Create a hash of data for comparison"""
    if not data:
        return ""
    
    return hashlib.sha256(data.encode()).hexdigest()


def verify_hash(data: str, hash_value: str) -> bool:
    """Verify data against a hash"""
    return hash_data(data) == hash_value
