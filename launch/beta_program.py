"""
Phase 9: Beta Program Manager
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class BetaProgram:
    """
    Manage beta testing program.
    """
    
    BETA_CONFIG = {
        "duration_days": 14,
        "max_beta_users": 10,
        "max_portfolio_per_user": 5000,
        "risk_profile": "conservative",
        "max_positions": 3,
        "max_position_size": 1500,
        "max_daily_loss": 100,
        "required_stop_loss": 0.02
    }
    
    def __init__(self):
        self.beta_users = {}
        self.feedback = {}
        self.metrics = {}
        
    def onboard_beta_user(self, user_id: str, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Onboard a new beta tester.
        
        Returns:
            Onboarding details
        """
        if len(self.beta_users) >= self.BETA_CONFIG["max_beta_users"]:
            return {"error": "Beta program is full"}
        
        self.beta_users[user_id] = {
            "user_info": user_info,
            "start_date": datetime.now(),
            "status": "active",
            "config": self.BETA_CONFIG.copy()
        }
        
        logger.info(f"Beta user onboarded: {user_id}")
        
        return {
            "user_id": user_id,
            "status": "active",
            "config": self.BETA_CONFIG,
            "duration_days": self.BETA_CONFIG["duration_days"]
        }
    
    def collect_feedback(self, user_id: str, feedback: Dict[str, Any]):
        """
        Collect feedback from beta user.
        """
        self.feedback[user_id] = {
            "feedback": feedback,
            "submitted_at": datetime.now()
        }
        logger.info(f"Feedback collected from {user_id}")
    
    def generate_beta_report(self) -> Dict[str, Any]:
        """
        Generate beta program report.
        """
        active_users = sum(
            1 for u in self.beta_users.values()
            if u["status"] == "active"
        )
        
        return {
            "total_users": len(self.beta_users),
            "active_users": active_users,
            "feedback_count": len(self.feedback),
            "config": self.BETA_CONFIG,
            "start_date": datetime.now() - timedelta(days=self.BETA_CONFIG["duration_days"]),
            "end_date": datetime.now()
        }
