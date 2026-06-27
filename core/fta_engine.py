import json
import os

class FTAEngine:
    def __init__(self, strategies_dir: str):
        self.strategies_dir = strategies_dir

    def load_root_causes(self, skill_name: str) -> list:
        path = os.path.join(self.strategies_dir, "root_causes.json")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(skill_name, [])

    def evaluate(self, skill_name: str, metrics: dict, thresholds: dict) -> list:
        causes = self.load_root_causes(skill_name)
        triggered_issues = []
        
        for cause in causes:
            metric_key = cause["metric"]
            if metric_key not in metrics:
                continue
                
            val = metrics[metric_key]
            thresh = thresholds.get(metric_key, {})
            
            high = thresh.get("high", 0)
            medium = thresh.get("medium", 0)
            compare_mode = thresh.get("compare_mode", "absolute_gt")
            
            severity = "NONE"
            if compare_mode == "absolute_lt":
                if val > 0 and val < medium:
                    severity = "HIGH" if val < high else "MEDIUM"
            else:
                if val > high and high > 0:
                    severity = "HIGH"
                elif val > medium and medium > 0:
                    severity = "MEDIUM"
                    
            if severity != "NONE":
                triggered_issues.append({
                    "code": cause["code"],
                    "name": cause["name"],
                    "severity": severity,
                    "value": val,
                    "threshold_medium": medium,
                    "recommendation": cause["recommendation"]
                })
                
        # Sort by severity (HIGH first, then MEDIUM)
        triggered_issues.sort(key=lambda x: 0 if x["severity"] == "HIGH" else 1)
        return triggered_issues
