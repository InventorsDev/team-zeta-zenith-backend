import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .config import get_settings

settings = get_settings()


def _get_encryption_key() -> bytes:
    """Generate encryption key from secret key"""
    password = settings.secret_key.encode()
    salt = b'stable_salt_for_integration_configs'  # In production, use a random salt per organization
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    if not data:
        return data
    
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()
    except Exception:
        # If encryption fails, return original data
        # In production, you might want to raise an exception instead
        return data


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not encrypted_data:
        return encrypted_data
    
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted_data = f.decrypt(decoded_data)
        return decrypted_data.decode()
    except Exception:
        # If decryption fails, return empty string
        # This handles cases where data wasn't encrypted
        return ""


def hash_data(data: str) -> str:
    """Create a hash of data for comparison"""
    if not data:
        return ""
    
    return hashlib.sha256(data.encode()).hexdigest()


def verify_hash(data: str, hash_value: str) -> bool:
    """Verify data against a hash"""
    return hash_data(data) == hash_value
