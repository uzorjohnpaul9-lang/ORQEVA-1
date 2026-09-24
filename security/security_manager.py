"""
Phase 8: Security Manager
Real encryption via Fernet, bcrypt-style password hashing, audit logging.
"""
import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "security_audit.json")


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def _read_env_master_key() -> str:
    """Parse .env directly, last occurrence wins (dotenv first-wins hides appended keys)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return ""
    value = ""
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("ENCRYPTION_KEY="):
                value = line.split("=", 1)[1].strip()
    return value


def _write_env_master_key(new_key: str):
    """Replace any existing ENCRYPTION_KEY lines in .env with a single valid key."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("ENCRYPTION_KEY=")]
    lines.append(f"ENCRYPTION_KEY={new_key}")
    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _get_master_fernet() -> Fernet:
    master = _read_env_master_key() or os.getenv("ENCRYPTION_KEY", "")
    if not master or master.startswith("change_this"):
        master = Fernet.generate_key().decode()
        _write_env_master_key(master)
        logger.warning("Generated new ENCRYPTION_KEY and wrote it to .env")
    salt = b"ai-trading-salt-v1"
    return Fernet(_derive_key(master, salt))


class SecurityManager:
    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
        self.audit_log: list = []
        self._fernet = _get_master_fernet()
        self._load_audit_log()

    # ---- API Key Management ----

    def generate_api_key(self, user_id: str) -> Dict[str, Any]:
        api_key = f"ak_{secrets.token_hex(16)}"
        api_secret = secrets.token_hex(32)

        self.api_keys[api_key] = {
            "user_id": user_id,
            "secret_hash": self._hash_secret(api_secret),
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "is_active": True,
        }
        self._log_audit(user_id, "api_key_generated", f"Key: {api_key[:8]}...")

        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "created_at": datetime.now().isoformat(),
        }

    def validate_api_key(self, api_key: str, api_secret: str) -> bool:
        if api_key not in self.api_keys:
            return False
        key_data = self.api_keys[api_key]
        if not key_data["is_active"]:
            return False
        if not self._verify_secret(api_secret, key_data["secret_hash"]):
            return False
        key_data["last_used"] = datetime.now().isoformat()
        return True

    def revoke_api_key(self, api_key: str) -> bool:
        if api_key in self.api_keys:
            self.api_keys[api_key]["is_active"] = False
            self._log_audit(self.api_keys[api_key]["user_id"], "api_key_revoked", f"Key: {api_key[:8]}...")
            return True
        return False

    # ---- Password Hashing (PBKDF2-SHA256 with salt) ----

    @staticmethod
    def _hash_secret(secret: str) -> str:
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 480000)
        return f"{salt.hex()}${dk.hex()}"

    @staticmethod
    def _verify_secret(secret: str, stored: str) -> bool:
        try:
            salt_hex, dk_hex = stored.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, 480000)
            return secrets.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False

    # ---- Fernet Encryption ----

    def encrypt_data(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        return self._fernet.decrypt(encrypted_data.encode()).decode()

    def encrypt_dict(self, data: dict) -> str:
        return self.encrypt_data(json.dumps(data))

    def decrypt_dict(self, encrypted_data: str) -> dict:
        return json.loads(self.decrypt_data(encrypted_data))

    # ---- Broker Credential Storage ----

    def encrypt_broker_credentials(self, user_id: str, broker: str, api_key: str, api_secret: str) -> str:
        payload = {"user_id": user_id, "broker": broker, "api_key": api_key, "api_secret": api_secret}
        return self.encrypt_dict(payload)

    def decrypt_broker_credentials(self, encrypted: str) -> dict:
        return self.decrypt_dict(encrypted)

    # ---- Audit Logging ----

    def _log_audit(self, user_id: str, action: str, details: str):
        entry = {
            "user_id": user_id,
            "action": action,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self.audit_log.append(entry)
        self._save_audit_log()

    def _save_audit_log(self):
        try:
            os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
            with open(AUDIT_LOG_PATH, "w") as f:
                json.dump(self.audit_log[-500:], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def _load_audit_log(self):
        try:
            if os.path.exists(AUDIT_LOG_PATH):
                with open(AUDIT_LOG_PATH) as f:
                    self.audit_log = json.load(f)
        except Exception:
            self.audit_log = []

    def get_audit_log(self, limit: int = 50) -> list:
        return self.audit_log[-limit:]
