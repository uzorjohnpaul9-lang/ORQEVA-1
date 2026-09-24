"""
Phase 5: AI Models - Ensemble Model
"""
from typing import Dict, Any, List, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

class AIEnsemble:
    """
    Ensemble of AI models for trading decisions.
    Combines multiple models for better accuracy.
    """
    
    def __init__(self):
        self.models = {}
        self.model_weights = {}
        self.prediction_history = []
        
    def add_model(self, name: str, model: Any, weight: float = 1.0):
        """Add a model to the ensemble."""
        self.models[name] = model
        self.model_weights[name] = weight
        logger.info(f"Added model: {name} with weight {weight}")
    
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get ensemble prediction from all models.
        
        Returns:
            Dictionary with prediction and confidence
        """
        predictions = {}
        
        for name, model in self.models.items():
            try:
                pred = model.predict(features)
                predictions[name] = {
                    "prediction": pred,
                    "weight": self.model_weights[name]
                }
            except Exception as e:
                logger.error(f"Error in model {name}: {e}")
        
        # Combine predictions
        return self._combine_predictions(predictions)
    
    def _combine_predictions(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine predictions from multiple models.
        """
        if not predictions:
            return {"direction": "hold", "confidence": 0.0}
        
        # Weighted average
        total_weight = sum(p["weight"] for p in predictions.values())
        weighted_sum = 0
        
        for name, pred in predictions.items():
            pred_value = 1 if pred["prediction"] == "buy" else -1
            weighted_sum += pred_value * pred["weight"]
        
        avg = weighted_sum / total_weight
        
        if avg > 0.3:
            direction = "buy"
        elif avg < -0.3:
            direction = "sell"
        else:
            direction = "hold"
        
        confidence = abs(avg)
        
        return {
            "direction": direction,
            "confidence": confidence,
            "model_count": len(predictions),
            "individual_predictions": predictions
        }
