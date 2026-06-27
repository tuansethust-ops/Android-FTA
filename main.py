import argparse
import os
import sys

from providers.perfetto_provider import PerfettoProvider
from core.skill_engine import SkillEngine
from core.fta_engine import FTAEngine

def format_report(skill_name: str, startups_results: list) -> str:
    md = [f"# {skill_name.upper()} Analysis Report (using Perfetto Stdlib)\n"]
    
    if not startups_results:
        md.append("No startup events found in the trace.")
        return "\n".join(md)
        
    for idx, result in enumerate(startups_results, 1):
        metrics = result["metrics"]
        issues = result["issues"]
        
        md.append(f"## Startup Event #{idx}: `{metrics['package']}` (Type: {metrics['startup_type'].upper()})")
        md.append(f"- **Total Duration (dur):** {metrics['dur_ms']:.1f} ms")
        md.append(f"- **TTID (Time to initial display):** {metrics['ttid_ms']:.1f} ms")
        md.append(f"- **TTFD (Time to full display):** {metrics['ttfd_ms']:.1f} ms")
        md.append("")
        
        md.append("### 1. Low-level System Data")
        md.append("| Metric | Value |")
        md.append("| :--- | :--- |")
        for k, v in metrics.items():
            if k in ["startup_id", "package", "startup_type", "dur_ms", "ttid_ms", "ttfd_ms", "top_blockers"]:
                continue
            if 'mhz' in k:
                md.append(f"| {k} | {v:.1f} MHz |")
            else:
                md.append(f"| {k} | {v:.1f} ms |")
                
        md.append("")
        md.append("### 2. Opinionated Breakdown & Recommendations")
        
        if not issues:
            md.append("*No significant anomalies detected based on defined thresholds.*")
        else:
            for i, issue in enumerate(issues, 1):
                icon = "🔴" if issue["severity"] == "HIGH" else "🟡"
                md.append(f"#### {icon} {issue['severity']} MCS-{i}: [{issue['code']}] {issue['name']}")
                md.append(f"> **Actual Value:** {issue['value']:.1f} ms (Warning Threshold: {issue['threshold_medium']:.1f} ms)")
                md.append(f"")
                md.append(f"**Recommendation:** _{issue['recommendation']}_")
                md.append("")
        
        top_blockers = metrics.get("top_blockers", [])
        if top_blockers:
            md.append("### 3. Top 3 External Critical Path Blockers")
            md.append("These are external system processes that blocked the Main Thread during startup:")
            for b in top_blockers:
                md.append(f"- **{b['process']}** (`{b['thread']}`): {b['dur_ms']:.1f} ms")
            md.append("")
        
        md.append("---\n")
        
    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(description="Android App Performance Analyzer (v4 Deep Upgrade)")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("skill", help="Name of the skill to run (e.g. startup_analysis)")
    parser.add_argument("--trace", required=True, help="Path to the perfetto trace file")
    
    args = parser.parse_args()
    
    if args.command == "run":
        # Support both trace_processor (Linux/macOS) and trace_processor.exe (Windows)
        tp_bin_win = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trace_processor.exe"))
        tp_bin_unix = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trace_processor"))
        tp_bin = tp_bin_win if os.path.exists(tp_bin_win) else tp_bin_unix

        if not os.path.exists(tp_bin):
            print(f"Error: trace_processor binary not found.")
            print(f"  Checked: {tp_bin_win}")
            print(f"  Checked: {tp_bin_unix}")
            print("Download from: https://perfetto.dev/docs/contributing/build-instructions")
            sys.exit(1)
            
        provider = PerfettoProvider(tp_bin, args.trace)
        
        skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "knowledge", "skills"))
        engine = SkillEngine(provider, skills_dir)
        
        print(f"Running skill: {args.skill} on trace: {args.trace}...")
        
        # Load thresholds
        skill_def = engine.load_skill(args.skill)
        thresholds = skill_def.get("thresholds", {})
        
        if args.skill == "startup_analysis":
            startups_metrics = engine.run_startup_analysis()
        else:
            print(f"Skill {args.skill} execution not fully implemented yet.")
            sys.exit(1)
            
        strategies_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "knowledge", "strategies"))
        fta = FTAEngine(strategies_dir)
        
        startups_results = []
        for metrics in startups_metrics:
            issues = fta.evaluate(args.skill, metrics, thresholds)
            startups_results.append({
                "metrics": metrics,
                "issues": issues
            })
        
        report = format_report(args.skill, startups_results)
        
        report_path = f"{args.skill}_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
            
        print(f"✅ Analysis complete! Report saved to {report_path}")

if __name__ == "__main__":
    main()
