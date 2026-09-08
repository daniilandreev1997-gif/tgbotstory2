"""Credential encryption/decryption via Fernet (symmetric).

Used to safely store platform credentials in the database.
Encrypted JSON blobs are decrypted at runtime before passing to extractors.
"""

import json
import logging

logger = logging.getLogger(__name__)


class CredentialEncryption:
    """Encrypt/decrypt credential JSON blobs with Fernet."""

    @staticmethod
    def decrypt_string(encrypted_data: str, encryption_key: str) -> dict:
        """Decrypt a Fernet-encrypted JSON string and return the parsed dict.

        Args:
            encrypted_data: Fernet token (base64-encoded encrypted bytes).
            encryption_key: Fernet key (32-byte url-safe base64-encoded).

        Returns:
            dict: Parsed credential dictionary (e.g. {"user_token": "..."}).

        Raises:
            ValueError: If decryption or JSON parsing fails.
        """
        if not encryption_key:
            # Backward compatibility: try plain JSON if no key configured
            try:
                return json.loads(encrypted_data)
            except json.JSONDecodeError:
                raise ValueError(
                    "No encryption_key configured and credential_data is not valid JSON. "
                    "Set ENCRYPTION_KEY in .env or re-encrypt credentials."
                )

        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError(
                "cryptography package is required for credential decryption. "
                "Install with: pip install cryptography"
            )

        try:
            f = Fernet(encryption_key.encode("utf-8"))
            decrypted_bytes = f.decrypt(encrypted_data.encode("utf-8"))
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            logger.error("credential_decrypt_failed", error=str(e))
            raise ValueError(f"Failed to decrypt credential data: {e}") from e
