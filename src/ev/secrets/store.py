"""Encrypted local secret store for Hi-EV.

Secrets are stored in a JSON vault file. The encryption key is retrieved from
the OS credential store (keyring) when available, otherwise from a user
supplied master password. This is not a high-assurance vault, but it keeps
API keys off disk in plain text for a local-first personal OS.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "Hi-EV"
KEYRING_USERNAME = "vault-key"


class SecretsError(Exception):
    """Raised when the secret store cannot be unlocked or written."""


class EncryptedSecretStore:
    """A simple Fernet-backed vault for Hi-EV secrets."""

    def __init__(self, vault_path: Path | str | None = None):
        self.vault_path = Path(vault_path or self._default_vault_path())
        self._fernet: Fernet | None = None

    @staticmethod
    def _default_vault_path() -> Path:
        return Path(os.environ.get("EV_VAULT_PATH") or Path.home() / ".hiev" / ".env.vault")

    def _get_or_create_key(self) -> bytes:
        """Return a 32-byte urlsafe-base64 Fernet key.

        Prefer keyring; fall back to a key derived from EV_MASTER_PASSWORD.
        """
        keyring_key = self._load_keyring_key()
        if keyring_key:
            return keyring_key

        password = os.environ.get("EV_MASTER_PASSWORD")
        if password:
            return self._derive_key_from_password(password)

        raise SecretsError(
            "No vault key available. Set EV_MASTER_PASSWORD or install keyring and run 'ev secrets init'."
        )

    def _load_keyring_key(self) -> bytes | None:
        try:
            import keyring  # type: ignore[import-untyped]

            value = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if value:
                return value.encode("utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.debug("keyring unavailable: %s", exc)
        return None

    def _derive_key_from_password(self, password: str) -> bytes:
        """Deterministically derive a Fernet key from a password.

        This is intended for headless / CI scenarios. A real deployment should
        use keyring so the key is not recoverable from a password alone.
        """
        import hashlib

        digest = hashlib.sha256(password.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def exists(self) -> bool:
        return self.vault_path.exists()

    def _read_vault(self) -> dict[str, str]:
        if not self.exists():
            return {}
        try:
            with self.vault_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise SecretsError(f"Vault file is corrupt: {self.vault_path}") from exc

    def _write_vault(self, data: dict[str, str]) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with self.vault_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def set(self, name: str, value: str) -> None:
        """Encrypt and store a secret."""
        vault = self._read_vault()
        encrypted = self._get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
        vault[name] = encrypted
        self._write_vault(vault)

    def get(self, name: str) -> str:
        """Decrypt and return a secret."""
        vault = self._read_vault()
        if name not in vault:
            raise SecretsError(f"Secret '{name}' not found in vault")
        encrypted = vault[name].encode("utf-8")
        return self._get_fernet().decrypt(encrypted).decode("utf-8")

    def delete(self, name: str) -> bool:
        """Remove a secret from the vault."""
        vault = self._read_vault()
        if name not in vault:
            return False
        del vault[name]
        self._write_vault(vault)
        return True

    def list(self) -> list[str]:
        """Return the names of all stored secrets."""
        return sorted(self._read_vault().keys())

    def load_into_env(self, names: list[str] | None = None) -> None:
        """Decrypt secrets and expose them as environment variables.

        This lets `ev.config.get_settings()` pick them up the same way it picks
        up values from `.env`.
        """
        if not self.exists():
            return
        vault = self._read_vault()
        keys = names or vault.keys()
        for name in keys:
            if name not in vault:
                continue
            try:
                os.environ[name] = self._get_fernet().decrypt(vault[name].encode("utf-8")).decode("utf-8")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not decrypt secret %s: %s", name, exc)
