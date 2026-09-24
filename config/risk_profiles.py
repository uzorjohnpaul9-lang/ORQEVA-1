from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RiskProfile:
    name: str
    risk_per_trade: float
    max_daily_loss: float
    max_position_size: float
    max_positions: int
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float
    max_drawdown: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "risk_per_trade": self.risk_per_trade,
            "max_daily_loss": self.max_daily_loss,
            "max_position_size": self.max_position_size,
            "max_positions": self.max_positions,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "trailing_stop_pct": self.trailing_stop_pct,
            "max_drawdown": self.max_drawdown
        }

# Risk Profiles
CONSERVATIVE = RiskProfile(
    name="conservative",
    risk_per_trade=0.01,
    max_daily_loss=0.03,
    max_position_size=0.10,
    max_positions=5,
    stop_loss_pct=0.02,
    take_profit_pct=0.06,
    trailing_stop_pct=0.02,
    max_drawdown=0.10
)

MODERATE = RiskProfile(
    name="moderate",
    risk_per_trade=0.02,
    max_daily_loss=0.05,
    max_position_size=0.15,
    max_positions=8,
    stop_loss_pct=0.03,
    take_profit_pct=0.09,
    trailing_stop_pct=0.03,
    max_drawdown=0.15
)

AGGRESSIVE = RiskProfile(
    name="aggressive",
    risk_per_trade=0.03,
    max_daily_loss=0.08,
    max_position_size=0.20,
    max_positions=12,
    stop_loss_pct=0.04,
    take_profit_pct=0.12,
    trailing_stop_pct=0.04,
    max_drawdown=0.25
)

RISK_PROFILES = {
    "conservative": CONSERVATIVE,
    "moderate": MODERATE,
    "aggressive": AGGRESSIVE
}

def get_risk_profile(profile_name: str) -> RiskProfile:
    """Get risk profile by name."""
    if profile_name not in RISK_PROFILES:
        raise ValueError(f"Unknown risk profile: {profile_name}")
    return RISK_PROFILES[profile_name]
