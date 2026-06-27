import argparse
import os
import sys

from providers.perfetto_provider import PerfettoProvider
from core.skill_engine import SkillEngine
from core.fta_engine import FTAEngine

def format_report(skill_name: str, startups_results: list) -> str:
    md = [f"# Báo cáo Phân tích {skill_name.upper()} (Sử dụng Perfetto Stdlib)\n"]
    
    if not startups_results:
        md.append("Không tìm thấy sự kiện khởi chạy (startup) nào trong trace.")
        return "\n".join(md)
        
    for idx, result in enumerate(startups_results, 1):
        metrics = result["metrics"]
        issues = result["issues"]
        
        md.append(f"## Lần khởi chạy #{idx}: `{metrics['package']}` (Type: {metrics['startup_type'].upper()})")
        md.append(f"- **Tổng thời gian (dur):** {metrics['dur_ms']:.1f} ms")
        md.append(f"- **TTID (Time to initial display):** {metrics['ttid_ms']:.1f} ms")
        md.append(f"- **TTFD (Time to full display):** {metrics['ttfd_ms']:.1f} ms")
        md.append("")
        
        md.append("### 1. Dữ liệu Hệ thống Cấp thấp")
        md.append("| Metric | Value |")
        md.append("| :--- | :--- |")
        for k, v in metrics.items():
            if k in ["startup_id", "package", "startup_type", "dur_ms", "ttid_ms", "ttfd_ms"]:
                continue
            if 'mhz' in k:
                md.append(f"| {k} | {v:.1f} MHz |")
            else:
                md.append(f"| {k} | {v:.1f} ms |")
                
        md.append("")
        md.append("### 2. Phân rã Nguyên nhân (Opinionated Breakdown) & Khuyến nghị")
        
        if not issues:
            md.append("*Không phát hiện bất thường đáng kể theo các ngưỡng đã định nghĩa.*")
        else:
            for i, issue in enumerate(issues, 1):
                icon = "🔴" if issue["severity"] == "HIGH" else "🟡"
                md.append(f"#### {icon} {issue['severity']} MCS-{i}: [{issue['code']}] {issue['name']}")
                md.append(f"> **Giá trị thực tế:** {issue['value']:.1f} ms (Ngưỡng cảnh báo: {issue['threshold_medium']:.1f} ms)")
                md.append(f"")
                md.append(f"**Đề xuất:** _{issue['recommendation']}_")
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
        tp_bin = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "trace_processor"))
        if not os.path.exists(tp_bin):
            print(f"Error: trace_processor binary not found at {tp_bin}")
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
