"""
Phase 8: Monetization Manager
"""
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Subscription Tiers
TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "features": [
            "paper_trading",
            "basic_signals",
            "3_symbols",
            "conservative_only",
            "email_support"
        ],
        "limits": {
            "symbols": 3,
            "portfolio_value": 10000,
            "trades_per_day": 5,
            "ai_models": 1
        }
    },
    "premium": {
        "name": "Premium",
        "price": 49,
        "features": [
            "live_trading",
            "advanced_signals",
            "10_symbols",
            "all_risk_profiles",
            "telegram_alerts",
            "priority_support"
        ],
        "limits": {
            "symbols": 10,
            "portfolio_value": 25000,
            "trades_per_day": 20,
            "ai_models": 5
        }
    },
    "pro": {
        "name": "Pro",
        "price": 199,
        "features": [
            "live_trading",
            "all_signals",
            "25_symbols",
            "all_risk_profiles",
            "telegram_alerts",
            "custom_strategies",
            "backtesting",
            "priority_support",
            "api_access"
        ],
        "limits": {
            "symbols": 25,
            "portfolio_value": 100000,
            "trades_per_day": 100,
            "ai_models": 11
        }
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 499,
        "features": [
            "unlimited_trading",
            "all_features",
            "unlimited_symbols",
            "custom_ai_models",
            "white_label",
            "dedicated_support",
            "sla_guarantee",
            "custom_integrations"
        ],
        "limits": {
            "symbols": -1,  # Unlimited
            "portfolio_value": -1,  # Unlimited
            "trades_per_day": -1,  # Unlimited
            "ai_models": -1  # Unlimited
        }
    }
}

class MonetizationManager:
    """
    Manage subscriptions and feature gating.
    """
    
    def __init__(self):
        self.subscriptions = {}
        self.feature_gates = {}
        
    def get_user_tier(self, user_id: str) -> str:
        """
        Get user's subscription tier.
        
        Returns:
            Tier name (free, premium, pro, enterprise)
        """
        return self.subscriptions.get(user_id, {}).get("tier", "free")
    
    def subscribe_user(self, user_id: str, tier: str) -> Dict[str, Any]:
        """
        Subscribe user to a tier.
        
        Returns:
            Subscription details
        """
        if tier not in TIERS:
            raise ValueError(f"Invalid tier: {tier}")
        
        self.subscriptions[user_id] = {
            "tier": tier,
            "subscribed_at": datetime.now(),
            "status": "active"
        }
        
        logger.info(f"User {user_id} subscribed to {tier}")
        
        return {
            "user_id": user_id,
            "tier": tier,
            "features": TIERS[tier]["features"],
            "limits": TIERS[tier]["limits"]
        }
    
    def check_feature_access(self, user_id: str, feature: str) -> bool:
        """
        Check if user has access to a feature.
        
        Returns:
            True if user has access
        """
        tier = self.get_user_tier(user_id)
        return feature in TIERS[tier]["features"]
    
    def check_limit(self, user_id: str, limit_type: str, current_usage: int) -> bool:
        """
        Check if user is within limits.
        
        Returns:
            True if within limit
        """
        tier = self.get_user_tier(user_id)
        limit = TIERS[tier]["limits"].get(limit_type, 0)
        
        # -1 means unlimited
        if limit == -1:
            return True
        
        return current_usage < limit
    
    def get_upgrade_suggestion(self, user_id: str) -> Optional[str]:
        """
        Suggest upgrade based on usage.
        
        Returns:
            Suggested tier or None
        """
        current_tier = self.get_user_tier(user_id)
        tier_order = ["free", "premium", "pro", "enterprise"]
        
        current_index = tier_order.index(current_tier)
        
        if current_index < len(tier_order) - 1:
            return tier_order[current_index + 1]
        
        return None
