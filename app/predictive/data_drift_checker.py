import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import json
import os
import logging

logger = logging.getLogger(__name__)

class DataDriftChecker:
    """
    Lightweight utility class to check incoming real-time telemetry averages 
    against background training dataset profiles to detect semantic data drift.
    """
    
    def __init__(self, registry_path: str = "models/registry", baseline_filename: str = "baseline_stats.json"):
        self.registry_path = registry_path
        self.baseline_path = os.path.join(registry_path, baseline_filename)
        self.baseline_stats: Dict[str, Dict[str, float]] = {}
        self._load_baseline()
        
    def _load_baseline(self):
        """Loads baseline statistics from the registry."""
        if os.path.exists(self.baseline_path):
            try:
                with open(self.baseline_path, 'r') as f:
                    self.baseline_stats = json.load(f)
                logger.info(f"Loaded baseline statistics from {self.baseline_path}")
            except Exception as e:
                logger.error(f"Failed to load baseline statistics: {e}")
        else:
            logger.warning(f"Baseline statistics file not found at {self.baseline_path}. Drift checking will be skipped.")
            
    def compute_and_save_baseline(self, df: pd.DataFrame, feature_columns: List[str]):
        """
        Computes baseline mean and standard deviation for the training data
        and saves it to the registry.
        """
        stats = {}
        for col in feature_columns:
            if col in df.columns:
                stats[col] = {
                    "mean": float(df[col].mean()),
                    "std": float(df[col].std())
                }
        
        os.makedirs(self.registry_path, exist_ok=True)
        with open(self.baseline_path, 'w') as f:
            json.dump(stats, f, indent=4)
            
        self.baseline_stats = stats
        logger.info(f"Saved new baseline statistics to {self.baseline_path}")
        
    def check_drift(self, telemetry_data: List[Dict[str, float]], threshold_z_score: float = 3.0) -> Dict[str, Any]:
        """
        Checks real-time telemetry against baseline stats.
        Returns a dictionary containing drift warnings.
        """
        if not self.baseline_stats:
            return {"status": "skipped", "message": "No baseline stats available."}
            
        df_live = pd.DataFrame(telemetry_data)
        warnings = []
        
        for feature, stats in self.baseline_stats.items():
            if feature in df_live.columns:
                live_mean = df_live[feature].mean()
                z_score = abs(live_mean - stats["mean"]) / (stats["std"] + 1e-9)
                
                if z_score > threshold_z_score:
                    msg = f"Data Drift Detected in '{feature}': Live Mean={live_mean:.2f}, Baseline Mean={stats['mean']:.2f}, Z-Score={z_score:.2f}"
                    logger.warning(msg)
                    warnings.append({
                        "feature": feature,
                        "live_mean": live_mean,
                        "baseline_mean": stats["mean"],
                        "z_score": z_score,
                        "threshold": threshold_z_score
                    })
                    
        is_drifting = len(warnings) > 0
        return {
            "status": "drifting" if is_drifting else "stable",
            "warnings": warnings
        }
