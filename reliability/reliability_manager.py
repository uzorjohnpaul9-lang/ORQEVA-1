"""
Phase 8: Reliability Manager
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time = None
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Returns:
            Function result or raises CircuitBreakerOpen exception
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).seconds
        return time_since_failure >= self.recovery_timeout

class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass

class ReliabilityManager:
    """
    System reliability management.
    """
    
    def __init__(self):
        self.circuit_breakers = {}
        self.health_checks = {}
        self.recovery_scripts = {}
        
    def register_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ):
        """Register a circuit breaker for a component."""
        self.circuit_breakers[name] = CircuitBreaker(
            failure_threshold,
            recovery_timeout
        )
    
    def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function."""
        self.health_checks[name] = check_func
    
    def run_health_checks(self) -> Dict[str, bool]:
        """Run all health checks."""
        results = {}
        
        for name, check_func in self.health_checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results[name] = False
        
        return results
    
    def execute_with_circuit_breaker(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.
        """
        if name not in self.circuit_breakers:
            self.register_circuit_breaker(name)
        
        breaker = self.circuit_breakers[name]
        return breaker.call(func, *args, **kwargs)
