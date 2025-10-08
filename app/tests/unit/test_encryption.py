"""
Unit tests for Encryption utilities

Tests data encryption, decryption, and hashing
"""

import pytest
from app.core.encryption import encrypt_data, decrypt_data, hash_data, verify_hash


@pytest.mark.unit
@pytest.mark.security
class TestEncryption:
    """Test suite for encryption functions"""

    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypting and decrypting data"""
        original_data = "sensitive-api-key-12345"

        encrypted = encrypt_data(original_data)
        assert encrypted != original_data
        assert len(encrypted) > len(original_data)  # Includes salt + encryption overhead

        decrypted = decrypt_data(encrypted)
        assert decrypted == original_data

    def test_encrypt_with_organization_id(self):
        """Test encryption with organization-specific salt"""
        original_data = "org-specific-secret"
        org_id = 123

        encrypted = encrypt_data(original_data, organization_id=org_id)
        assert encrypted != original_data

        # Can decrypt with same org_id
        decrypted = decrypt_data(encrypted, organization_id=org_id)
        assert decrypted == original_data

        # Cannot decrypt with different org_id
        wrong_decrypted = decrypt_data(encrypted, organization_id=456)
        assert wrong_decrypted == ""  # Returns empty string on decryption failure

    def test_encrypt_empty_string(self):
        """Test encrypting empty string"""
        encrypted = encrypt_data("")
        assert encrypted == ""

        decrypted = decrypt_data("")
        assert decrypted == ""

    def test_encrypt_none(self):
        """Test encrypting None"""
        encrypted = encrypt_data(None)
        assert encrypted is None

        decrypted = decrypt_data(None)
        assert decrypted is None

    def test_encrypt_large_data(self):
        """Test encrypting large data (should use compression)"""
        # Create data larger than compression threshold (1KB)
        large_data = "A" * 2000

        encrypted = encrypt_data(large_data, compress=True)
        assert encrypted != large_data

        decrypted = decrypt_data(encrypted)
        assert decrypted == large_data

    def test_encrypt_without_compression(self):
        """Test encrypting without compression"""
        data = "some data to encrypt"

        encrypted = encrypt_data(data, compress=False)
        decrypted = decrypt_data(encrypted)

        assert decrypted == data

    def test_hash_data(self):
        """Test hashing data"""
        data = "password123"

        hashed = hash_data(data)
        assert hashed != data
        assert len(hashed) == 64  # SHA256 produces 64 hex characters

        # Same data produces same hash
        hashed2 = hash_data(data)
        assert hashed == hashed2

        # Different data produces different hash
        hashed3 = hash_data("differentdata")
        assert hashed != hashed3

    def test_verify_hash(self):
        """Test hash verification"""
        data = "testdata"
        hashed = hash_data(data)

        assert verify_hash(data, hashed)
        assert not verify_hash("wrongdata", hashed)

    def test_hash_empty_string(self):
        """Test hashing empty string"""
        hashed = hash_data("")
        assert hashed == ""

    def test_different_encryptions_produce_different_ciphertexts(self):
        """Test that same data encrypted twice produces different ciphertexts (due to random salt)"""
        data = "same data"

        encrypted1 = encrypt_data(data)
        encrypted2 = encrypt_data(data)

        # Should be different (random salt)
        assert encrypted1 != encrypted2

        # But both decrypt to same value
        assert decrypt_data(encrypted1) == data
        assert decrypt_data(encrypted2) == data

    def test_decrypt_invalid_data(self):
        """Test decrypting invalid data returns empty string"""
        invalid_data = "this-is-not-encrypted-data"
        result = decrypt_data(invalid_data)
        assert result == ""

    def test_encrypt_unicode_data(self):
        """Test encrypting Unicode characters"""
        unicode_data = "Hello 世界 🌍 Привет"

        encrypted = encrypt_data(unicode_data)
        decrypted = decrypt_data(encrypted)

        assert decrypted == unicode_data
