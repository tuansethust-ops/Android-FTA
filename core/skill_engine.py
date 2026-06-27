import json
import os

class SkillEngine:
    def __init__(self, provider, skills_dir: str):
        self.provider = provider
        self.skills_dir = skills_dir

    def load_skill(self, skill_name: str) -> dict:
        path = os.path.join(self.skills_dir, f"{skill_name}.json")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run_startup_analysis(self):
        skill = self.load_skill("startup_analysis")
        queries = skill["queries"]
        
        # 1. Get all startups
        startups_data = self.provider.query(queries["startups"])
        if not startups_data:
            return []
            
        results = []
        for s in startups_data:
            startup_id = s["startup_id"]
            
            metrics = {
                "startup_id": startup_id,
                "package": s.get("package", "unknown"),
                "startup_type": s.get("startup_type", "unknown"),
                "dur_ms": float(s.get("dur_ms") or 0.0),
                "ttid_ms": float(s.get("ttid_ms") or 0.0) if s.get("ttid_ms") != "[NULL]" else 0.0,
                "ttfd_ms": float(s.get("ttfd_ms") or 0.0) if s.get("ttfd_ms") != "[NULL]" else 0.0,
                "thread_runnable_ms": 0.0,
                "thread_sleeping_ms": 0.0,
                "thread_uninterruptible_ms": 0.0,
                "cpu_freq_mhz": 0.0
            }
            
            # 2. Breakdown Analysis
            sql_breakdown = queries["breakdown"].replace("{startup_id}", str(startup_id))
            breakdown_data = self.provider.query(sql_breakdown)
            for row in breakdown_data:
                reason = row["reason"]
                dur = float(row.get("total_dur_ms", 0) or 0)
                metrics[reason] = dur
                
            # 3. Thread states
            sql_ts = queries["thread_states"].replace("{startup_id}", str(startup_id))
            states_data = self.provider.query(sql_ts)
            for row in states_data:
                state = row["state"]
                dur = float(row.get("total_dur_ms", 0) or 0)
                if 'R' in state: metrics["thread_runnable_ms"] += dur
                elif 'S' in state: metrics["thread_sleeping_ms"] += dur
                elif 'D' in state: metrics["thread_uninterruptible_ms"] += dur
                
            # 4. CPU Freq
            sql_freq = queries["cpu_freq"].replace("{startup_id}", str(startup_id))
            freq_data = self.provider.query(sql_freq)
            if freq_data and freq_data[0].get("avg_freq_mhz") and freq_data[0]["avg_freq_mhz"] != "[NULL]":
                metrics["cpu_freq_mhz"] = float(freq_data[0]["avg_freq_mhz"])
                
            # 5. Top External Blockers (Critical Path)
            sql_cp = queries.get("top_external_blockers")
            metrics["top_blockers"] = []
            if sql_cp:
                sql_cp = sql_cp.replace("{startup_id}", str(startup_id))
                cp_data = self.provider.query(sql_cp)
                for row in cp_data:
                    metrics["top_blockers"].append({
                        "process": row["blocker_process"],
                        "thread": row["blocker_thread"],
                        "dur_ms": float(row["total_block_dur_ms"])
                    })
                
            results.append(metrics)
            
        return results
