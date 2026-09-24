"""
Phase 3: Risk Engine - Audit Logger
"""
from datetime import datetime
from typing import Dict, Any, List
import logging
import json

logger = logging.getLogger(__name__)

class AuditLogger:
    """
    Log all risk decisions and actions.
    """
    
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []
        
    def log_trade_decision(self, decision: Any):
        """
        Log trade decision.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "trade_decision",
            "allowed": decision.allowed,
            "checks": [
                {
                    "name": check.name,
                    "allowed": check.allowed,
                    "reason": check.reason
                }
                for check in decision.checks
            ]
        }
        
        self.audit_log.append(log_entry)
        logger.info(f"Trade decision: {'ALLOWED' if decision.allowed else 'REJECTED'}")
    
    def log_risk_breach(self, control: str, details: str):
        """
        Log risk control breach.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "risk_breach",
            "control": control,
            "details": details
        }
        
        self.audit_log.append(log_entry)
        logger.warning(f"Risk breach: {control} - {details}")
    
    def log_kill_switch(self, reason: str):
        """
        Log kill switch activation.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "kill_switch",
            "action": "activated",
            "reason": reason
        }
        
        self.audit_log.append(log_entry)
        logger.critical(f"Kill switch activated: {reason}")
    
    def log_daily_reset(self):
        """
        Log daily reset.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "daily_reset",
            "action": "reset"
        }
        
        self.audit_log.append(log_entry)
        logger.info("Daily metrics reset")
    
    def log_position_opened(self, symbol: str, side: str, quantity: float, price: float):
        """
        Log position opened.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "position",
            "action": "opened",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price
        }
        
        self.audit_log.append(log_entry)
        logger.info(f"Position opened: {side} {quantity} {symbol} @ {price}")
    
    def log_position_closed(self, symbol: str, exit_price: float, pnl: float):
        """
        Log position closed.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "position",
            "action": "closed",
            "symbol": symbol,
            "exit_price": exit_price,
            "pnl": pnl
        }
        
        self.audit_log.append(log_entry)
        logger.info(f"Position closed: {symbol} P&L: ${pnl:.2f}")
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent audit log entries.
        """
        return self.audit_log[-limit:]
    
    def export_audit_log(self, filename: str):
        """
        Export audit log to file.
        """
        with open(filename, 'w') as f:
            json.dump(self.audit_log, f, indent=2)
        logger.info(f"Audit log exported to {filename}")
