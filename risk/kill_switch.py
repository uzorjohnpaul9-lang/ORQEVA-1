"""
Phase 3: Risk Engine - Kill Switch (Persistent)
"""
import os
import json
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

KILL_SWITCH_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "kill_switch.json")


class KillSwitch:
    """Emergency kill switch to immediately halt all trading. State persists across restarts."""

    def __init__(self):
        self.auto_activate_threshold = 0.05
        self._load()

    def _load(self):
        try:
            if os.path.exists(KILL_SWITCH_FILE):
                with open(KILL_SWITCH_FILE) as f:
                    data = json.load(f)
                self.is_active = data.get("is_active", False)
                self.activation_time = data.get("activation_time")
                self.activation_reason = data.get("activation_reason")
                if self.is_active:
                    logger.warning(f"Kill switch restored: ACTIVE - {self.activation_reason}")
                return
        except Exception:
            pass
        self.is_active = False
        self.activation_time = None
        self.activation_reason = None

    def _save(self):
        try:
            os.makedirs(os.path.dirname(KILL_SWITCH_FILE), exist_ok=True)
            with open(KILL_SWITCH_FILE, "w") as f:
                json.dump({
                    "is_active": self.is_active,
                    "activation_time": self.activation_time,
                    "activation_reason": self.activation_reason,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")

    def activate(self, reason: str) -> bool:
        if self.is_active:
            logger.warning("Kill switch already active")
            return False
        self.is_active = True
        self.activation_time = datetime.now().isoformat()
        self.activation_reason = reason
        self._save()
        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        return True

    def deactivate(self) -> bool:
        if not self.is_active:
            logger.warning("Kill switch not active")
            return False
        self.is_active = False
        self.activation_time = None
        self.activation_reason = None
        self._save()
        logger.info("Kill switch deactivated")
        return True

    def check_auto_activate(self, current_drawdown: float) -> bool:
        if current_drawdown >= self.auto_activate_threshold:
            return self.activate(f"Auto-activated: Drawdown {current_drawdown:.2%} exceeded threshold")
        return False

    def get_status(self) -> dict:
        return {
            "active": self.is_active,
            "activation_time": self.activation_time,
            "reason": self.activation_reason,
            "auto_threshold": self.auto_activate_threshold,
        }
