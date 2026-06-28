import React, { useState, useEffect, useRef } from "react";
import ReactECharts from "echarts-for-react";
import {
  Sun,
  Moon,
  FolderOpen,
  Settings,
  Terminal as TerminalIcon,
  Play,
  CheckCircle,
  AlertTriangle,
  FileText,
  Sliders,
  Maximize2
} from "lucide-react";

export default function App() {
  const [theme, setTheme] = useState("dark");
  const [skills, setSkills] = useState([]);
  const [selectedSkillName, setSelectedSkillName] = useState("startup_analysis");
  const [thresholds, setThresholds] = useState({});
  const [dutPath, setDutPath] = useState("");
  const [refPath, setRefPath] = useState("");
  const [maxWorkers, setMaxWorkers] = useState(4);
  const [parserRegex, setParserRegex] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [activeTab, setActiveTab] = useState("summary");
  const [isSavingSettings, setIsSavingSettings] = useState(false);

  const logsEndRef = useRef(null);

  // Sync Theme with HTML element
  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  // Load Skills config on mount
  useEffect(() => {
    fetchSkills();
  }, []);

  const fetchSkills = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/skills");
      if (res.ok) {
        const data = await res.json();
        setSkills(data);
        // Load initial skill thresholds
        const initialSkill = data.find((s) => s.name === selectedSkillName);
        if (initialSkill) {
          setThresholds(initialSkill.thresholds || {});
        }
      }
    } catch (err) {
      console.error("Failed to fetch skills:", err);
    }
  };

  // Update thresholds when selected skill changes
  const handleSkillChange = (name) => {
    setSelectedSkillName(name);
    const skill = skills.find((s) => s.name === name);
    if (skill) {
      setThresholds(skill.thresholds || {});
    }
  };

  // Update threshold slider value locally
  const handleThresholdChange = (key, field, val) => {
    setThresholds((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        [field]: Number(val)
      }
    }));
  };

  // Save thresholds to JSON file via API
  const saveThresholds = async () => {
    setIsSavingSettings(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill_name: selectedSkillName,
          thresholds
        })
      });
      if (res.ok) {
        alert("Threshold settings saved successfully!");
        fetchSkills(); // refresh local store
      } else {
        alert("Failed to save settings.");
      }
    } catch (err) {
      console.error("Save settings error:", err);
      alert("Error saving settings.");
    } finally {
      setIsSavingSettings(false);
    }
  };

  // Desktop folder picker trigger
  const browseDirectory = async (target) => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/browse", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          if (target === "dut") setDutPath(data.path);
          if (target === "ref") setRefPath(data.path);
        }
      }
    } catch (err) {
      console.error("Browse directory error:", err);
    }
  };

  // Execute comparison via WebSocket
  const startComparison = () => {
    if (!dutPath || !refPath) {
      alert("Please select both DUT and REF trace directories.");
      return;
    }

    setIsRunning(true);
    setLogs([]);
    setReport(null);
    setActiveTab("summary");

    const ws = new WebSocket("ws://127.0.0.1:8000/ws/compare");

    ws.onopen = () => {
      // Send parameters payload
      ws.send(
        JSON.stringify({
          dut: dutPath,
          ref: refPath,
          skill: selectedSkillName,
          max_workers: maxWorkers,
          parser_regex: parserRegex || null
        })
      );
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "log") {
        setLogs((prev) => [...prev, data.message]);
        if (logsEndRef.current) {
          logsEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
      } else if (data.type === "result") {
        setReport(data.report);
        setIsRunning(false);
        ws.close();
      } else if (data.type === "error") {
        setLogs((prev) => [...prev, `[ERROR] ${data.message}`]);
        setIsRunning(false);
        ws.close();
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
      setLogs((prev) => [...prev, "[ERROR] Connection lost or failed."]);
      setIsRunning(false);
    };

    ws.onclose = () => {
      setIsRunning(false);
    };
  };

  // ---------------------------------------------------------------------------
  // ECharts Configurations
  // ---------------------------------------------------------------------------

  // Chart colors
  const colors = [
    "#3b82f6", // blue
    "#10b981", // green
    "#f59e0b", // yellow
    "#ef4444", // red
    "#8b5cf6", // purple
    "#ec4899"  // pink
  ];

  // Helper to extract app metrics for graphs
  const getAppCompareChartOptions = (app) => {
    const isDark = theme === "dark";
    const categories = app.metrics.map((m) => m.name);
    const dutData = app.metrics.map((m) => Number(m.dut_median.toFixed(1)));
    const refData = app.metrics.map((m) => Number(m.ref_median.toFixed(1)));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDark ? "#0c0c0f" : "#ffffff",
        borderColor: isDark ? "#1e1e24" : "#e2e8f0",
        textStyle: { color: isDark ? "#fafafa" : "#09090b" }
      },
      legend: {
        data: ["DUT Median", "REF Median"],
        textStyle: { color: isDark ? "#a1a1aa" : "#64748b" }
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "3%",
        containLabel: true
      },
      xAxis: {
        type: "value",
        axisLabel: { color: isDark ? "#a1a1aa" : "#64748b" },
        splitLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)" } }
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: isDark ? "#a1a1aa" : "#64748b", interval: 0 }
      },
      series: [
        {
          name: "DUT Median",
          type: "bar",
          data: dutData,
          itemStyle: { color: "#3b82f6", borderRadius: [0, 4, 4, 0] }
        },
        {
          name: "REF Median",
          type: "bar",
          data: refData,
          itemStyle: { color: "#10b981", borderRadius: [0, 4, 4, 0] }
        }
      ]
    };
  };

  // Waterfall Chart Options indicating timeline of stages
  const getAppWaterfallChartOptions = (app) => {
    const isDark = theme === "dark";

    // Filtering out overall times (dur_ms, ttid_ms, etc.) to get pure breakdowns
    const stages = app.metrics.filter(
      (m) =>
        m.name !== "dur_ms" &&
        m.name !== "ttid_ms" &&
        m.name !== "ttfd_ms" &&
        m.name !== "cpu_freq_mhz"
    );

    const categories = stages.map((m) => m.name);

    // Calculate waterfall timeline heights for DUT
    let dutBase = 0;
    const dutBases = [];
    const dutVals = [];

    stages.forEach((m) => {
      dutBases.push(dutBase);
      dutVals.push(m.dut_median);
      dutBase += m.dut_median;
    });

    // Calculate waterfall timeline heights for REF
    let refBase = 0;
    const refBases = [];
    const refVals = [];

    stages.forEach((m) => {
      refBases.push(refBase);
      refVals.push(m.ref_median);
      refBase += m.ref_median;
    });

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params) => {
          const dut = params[1];
          const ref = params[3];
          return `
            <div style="font-size: 12px;">
              <strong>${dut.name}</strong><br/>
              DUT: ${dut.value} ms<br/>
              REF: ${ref.value} ms
            </div>
          `;
        },
        backgroundColor: isDark ? "#0c0c0f" : "#ffffff",
        borderColor: isDark ? "#1e1e24" : "#e2e8f0",
        textStyle: { color: isDark ? "#fafafa" : "#09090b" }
      },
      legend: {
        data: ["DUT Duration", "REF Duration"],
        textStyle: { color: isDark ? "#a1a1aa" : "#64748b" }
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "3%",
        containLabel: true
      },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { color: isDark ? "#a1a1aa" : "#64748b", rotate: 30, interval: 0 }
      },
      yAxis: {
        type: "value",
        axisLabel: { color: isDark ? "#a1a1aa" : "#64748b" },
        splitLine: { lineStyle: { color: isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.04)" } }
      },
      series: [
        {
          name: "DUT Placeholder",
          type: "bar",
          stack: "DUT",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          data: dutBases
        },
        {
          name: "DUT Duration",
          type: "bar",
          stack: "DUT",
          data: dutVals.map((v) => Number(v.toFixed(1))),
          itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] }
        },
        {
          name: "REF Placeholder",
          type: "bar",
          stack: "REF",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          data: refBases
        },
        {
          name: "REF Duration",
          type: "bar",
          stack: "REF",
          data: refVals.map((v) => Number(v.toFixed(1))),
          itemStyle: { color: "#10b981", borderRadius: [4, 4, 0, 0] }
        }
      ]
    };
  };

  // Collect all flagged issues from report comparison
  const getAllIssues = () => {
    if (!report) return [];
    const issues = [];
    report.apps.forEach((app) => {
      app.metrics.forEach((m) => {
        if (m.issue) {
          issues.push({
            app_name: app.app_name,
            entry_type: app.entry_type,
            metric_name: m.name,
            ...m.issue
          });
        }
      });
    });
    // Sort HIGH severity first
    return issues.sort((a, b) => (a.severity === "HIGH" ? -1 : 1));
  };

  return (
    <div className="min-h-screen flex flex-col transition-colors duration-200">
      {/* ---------------------------------------------------------------------
          HEADER ROW
          --------------------------------------------------------------------- */}
      <header className="border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0c0f] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-extrabold text-lg">
            A
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
              Android-FTA
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Automated App Launch Performance Analyzer
            </p>
          </div>
        </div>

        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>

      {/* ---------------------------------------------------------------------
          MAIN CONTENT SPLIT
          --------------------------------------------------------------------- */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* SETUP PANEL (COL 4) */}
        <section className="lg:col-span-4 bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm space-y-5 flex flex-col justify-between">
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
              <Sliders size={16} /> Analysis Config
            </h2>

            {/* Path Selection */}
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-zinc-500 mb-1.5 block">
                  DUT Trace Directory
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={dutPath}
                    onChange={(e) => setDutPath(e.target.value)}
                    placeholder="E.g., D:\traces\dut"
                    className="flex-1 bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <button
                    onClick={() => browseDirectory("dut")}
                    className="p-2 border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-lg text-zinc-600 dark:text-zinc-200 transition-colors"
                  >
                    <FolderOpen size={16} />
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-zinc-500 mb-1.5 block">
                  REF Trace Directory
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={refPath}
                    onChange={(e) => setRefPath(e.target.value)}
                    placeholder="E.g., D:\traces\ref"
                    className="flex-1 bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <button
                    onClick={() => browseDirectory("ref")}
                    className="p-2 border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-lg text-zinc-600 dark:text-zinc-200 transition-colors"
                  >
                    <FolderOpen size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* Skill Selector */}
            <div>
              <label className="text-xs font-medium text-zinc-500 mb-1.5 block">
                Performance Skill (Scenario)
              </label>
              <select
                value={selectedSkillName}
                onChange={(e) => handleSkillChange(e.target.value)}
                className="w-full bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none"
              >
                {skills.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* General settings */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-zinc-500 mb-1.5 block">
                  Max Workers
                </label>
                <input
                  type="number"
                  value={maxWorkers}
                  onChange={(e) => setMaxWorkers(Number(e.target.value))}
                  className="w-full bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-500 mb-1.5 block">
                  Filename regex (optional)
                </label>
                <input
                  type="text"
                  value={parserRegex}
                  onChange={(e) => setParserRegex(e.target.value)}
                  placeholder="Regex pattern"
                  className="w-full bg-zinc-50 dark:bg-[#09090b] border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-900 dark:text-zinc-100 focus:outline-none"
                />
              </div>
            </div>

            {/* Threshold Parameters */}
            <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-xs font-bold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                  <Settings size={14} /> Delta Thresholds (ms)
                </h3>
                <button
                  onClick={saveThresholds}
                  disabled={isSavingSettings}
                  className="text-[11px] font-semibold text-blue-500 hover:text-blue-600 disabled:opacity-50"
                >
                  Save to Skill
                </button>
              </div>

              <div className="space-y-3 max-h-[220px] overflow-y-auto pr-1 terminal-scrollbar">
                {Object.keys(thresholds).map((key) => {
                  const item = thresholds[key];
                  if (typeof item !== "object" || item.high === undefined) return null;
                  return (
                    <div key={key} className="space-y-1 text-xs">
                      <div className="flex justify-between text-[11px]">
                        <span className="font-semibold text-zinc-600 dark:text-zinc-400">
                          {key}
                        </span>
                        <span className="text-zinc-500">
                          M: {item.delta_medium ?? item.medium}ms | H:{" "}
                          {item.delta_high ?? item.high}ms
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-zinc-400">Med</span>
                          <input
                            type="range"
                            min="0"
                            max="500"
                            value={item.delta_medium ?? item.medium ?? 0}
                            onChange={(e) =>
                              handleThresholdChange(
                                key,
                                item.delta_medium !== undefined ? "delta_medium" : "medium",
                                e.target.value
                              )
                            }
                            className="w-full h-1 bg-zinc-200 dark:bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                          />
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-[10px] text-zinc-400">High</span>
                          <input
                            type="range"
                            min="0"
                            max="500"
                            value={item.delta_high ?? item.high ?? 0}
                            onChange={(e) =>
                              handleThresholdChange(
                                key,
                                item.delta_high !== undefined ? "delta_high" : "high",
                                e.target.value
                              )
                            }
                            className="w-full h-1 bg-zinc-200 dark:bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <button
            onClick={startComparison}
            disabled={isRunning}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 font-semibold text-xs flex items-center justify-center gap-2 transition-colors disabled:opacity-50 shadow-sm"
          >
            {isRunning ? (
              <>
                <div className="h-3 w-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Analyzing Traces...
              </>
            ) : (
              <>
                <Play size={14} /> Run Comparison
              </>
            )}
          </button>
        </section>

        {/* DETAILS/RESULTS PANEL (COL 8) */}
        <section className="lg:col-span-8 flex flex-col gap-6">
          {/* Real-time Logs Console */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex flex-col gap-2 shadow-inner h-[180px]">
            <div className="flex justify-between items-center border-b border-zinc-800 pb-2">
              <span className="text-xs font-bold text-zinc-400 flex items-center gap-2">
                <TerminalIcon size={14} /> Execution Console logs
              </span>
              <button
                onClick={() => setLogs([])}
                className="text-[10px] font-semibold text-zinc-500 hover:text-zinc-300"
              >
                Clear
              </button>
            </div>
            <div className="flex-1 overflow-y-auto font-mono text-[11px] text-zinc-300 space-y-1 terminal-scrollbar">
              {logs.length === 0 && (
                <div className="text-zinc-600 italic">Console idle. Awaiting run request...</div>
              )}
              {logs.map((log, index) => (
                <div key={index} className="leading-5">
                  {log}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* Report Dashboard */}
          <div className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 shadow-sm flex-1 flex flex-col">
            {/* Tabs Header */}
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3 mb-4">
              <div className="flex gap-4">
                {["summary", "comparison", "timeline"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    disabled={!report}
                    className={`text-xs font-semibold pb-1.5 border-b-2 capitalize transition-all ${
                      !report
                        ? "text-zinc-400 dark:text-zinc-600 cursor-not-allowed border-transparent"
                        : activeTab === tab
                        ? "border-blue-500 text-blue-600 dark:text-blue-400"
                        : "border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200"
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <span className="text-[11px] text-zinc-400">
                {report ? `Compared ${report.apps.length} App configurations` : "No active report"}
              </span>
            </div>

            {/* Tabs Content */}
            <div className="flex-1 flex flex-col justify-center">
              {!report ? (
                <div className="text-center py-20 text-zinc-400 dark:text-zinc-600 text-sm">
                  <FileText size={48} className="mx-auto mb-3 opacity-50" />
                  Select directories and click "Run Comparison" to generate visual reports.
                </div>
              ) : (
                <div className="flex-1 space-y-6">
                  {/* TAB 1: SUMMARY */}
                  {activeTab === "summary" && (
                    <div className="space-y-6">
                      {/* Apps Summary KPIs */}
                      {report.apps.map((app) => {
                        const ttidMetric = app.metrics.find((m) => m.name === "ttid_ms") || {};
                        const durMetric = app.metrics.find((m) => m.name === "dur_ms") || {};

                        const ttidDelta = ttidMetric.delta ?? 0;
                        const ttidPct = ttidMetric.delta_pct ?? 0;
                        const durDelta = durMetric.delta ?? 0;
                        const durPct = durMetric.delta_pct ?? 0;

                        return (
                          <div
                            key={`${app.app_name}_${app.entry_type}`}
                            className="border border-zinc-100 dark:border-zinc-800 rounded-lg p-4 space-y-4"
                          >
                            <div className="flex justify-between items-center">
                              <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-100">
                                {app.app_name}{" "}
                                <span className="text-xs font-normal text-zinc-500 capitalize">
                                  ({app.entry_type}-entry)
                                </span>
                              </h3>
                              <span
                                className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                                  app.metrics.some((m) => m.issue?.severity === "HIGH")
                                    ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
                                    : app.metrics.some((m) => m.issue?.severity === "MEDIUM")
                                    ? "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
                                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                                }`}
                              >
                                {app.metrics.some((m) => m.issue?.severity === "HIGH")
                                  ? "HIGH Impact Anomaly"
                                  : app.metrics.some((m) => m.issue?.severity === "MEDIUM")
                                  ? "MEDIUM Impact Anomaly"
                                  : "Healthy Start"}
                              </span>
                            </div>

                            {/* KPI Metrics */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              <div className="bg-zinc-50 dark:bg-[#09090b] border border-zinc-100 dark:border-zinc-900 rounded-lg p-3">
                                <span className="text-[11px] text-zinc-500">TTID Median</span>
                                <div className="text-lg font-extrabold mt-1">
                                  {ttidMetric.dut_median?.toFixed(1)}ms{" "}
                                  <span className="text-xs font-normal text-zinc-500">
                                    (vs {ttidMetric.ref_median?.toFixed(1)}ms REF)
                                  </span>
                                </div>
                                <div
                                  className={`text-xs mt-1.5 flex items-center gap-1 font-semibold ${
                                    ttidDelta > 0 ? "text-rose-500" : "text-emerald-500"
                                  }`}
                                >
                                  {ttidDelta > 0 ? "↑" : "↓"} {Math.abs(ttidDelta).toFixed(1)}ms (
                                  {ttidPct > 0 ? "+" : ""}
                                  {ttidPct.toFixed(1)}%)
                                </div>
                              </div>

                              <div className="bg-zinc-50 dark:bg-[#09090b] border border-zinc-100 dark:border-zinc-900 rounded-lg p-3">
                                <span className="text-[11px] text-zinc-500">Overall Duration</span>
                                <div className="text-lg font-extrabold mt-1">
                                  {durMetric.dut_median?.toFixed(1)}ms{" "}
                                  <span className="text-xs font-normal text-zinc-500">
                                    (vs {durMetric.ref_median?.toFixed(1)}ms REF)
                                  </span>
                                </div>
                                <div
                                  className={`text-xs mt-1.5 flex items-center gap-1 font-semibold ${
                                    durDelta > 0 ? "text-rose-500" : "text-emerald-500"
                                  }`}
                                >
                                  {durDelta > 0 ? "↑" : "↓"} {Math.abs(durDelta).toFixed(1)}ms (
                                  {durPct > 0 ? "+" : ""}
                                  {durPct.toFixed(1)}%)
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      {/* Flagged FTA Issues List */}
                      <div className="space-y-3">
                        <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                          <AlertTriangle size={14} /> Flagged Performance Anomaly (FTA Root Causes)
                        </h4>

                        {getAllIssues().length === 0 ? (
                          <div className="border border-zinc-100 dark:border-zinc-800 rounded-lg p-4 flex items-center gap-3 bg-emerald-50/50 dark:bg-emerald-950/10 text-emerald-800 dark:text-emerald-300">
                            <CheckCircle size={16} />
                            <span className="text-xs font-semibold">
                              All metrics are within acceptable delta parameters. No anomalies flagged.
                            </span>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {getAllIssues().map((issue, idx) => (
                              <div
                                key={idx}
                                className={`border rounded-lg p-4 space-y-2 bg-white dark:bg-[#0c0c0f] ${
                                  issue.severity === "HIGH"
                                    ? "border-rose-200 dark:border-rose-950/40"
                                    : "border-amber-200 dark:border-amber-950/40"
                                }`}
                              >
                                <div className="flex justify-between items-center">
                                  <span className="text-xs font-bold text-zinc-800 dark:text-zinc-200 flex items-center gap-2">
                                    <span
                                      className={`h-2 w-2 rounded-full ${
                                        issue.severity === "HIGH" ? "bg-rose-500" : "bg-amber-500"
                                      }`}
                                    />
                                    [{issue.code}] {issue.name}
                                  </span>
                                  <span
                                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                      issue.severity === "HIGH"
                                        ? "bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400"
                                        : "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
                                    }`}
                                  >
                                    {issue.severity}
                                  </span>
                                </div>
                                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                                  App: <strong className="font-semibold">{issue.app_name}</strong> |
                                  Metric: <code className="font-mono bg-zinc-100 dark:bg-zinc-800 px-1 rounded">{issue.metric_name}</code>
                                </p>
                                <div className="text-xs text-zinc-600 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-950 p-2.5 rounded border border-zinc-100 dark:border-zinc-900 leading-5">
                                  <span className="font-bold">Recommendation:</span>{" "}
                                  <em>{issue.recommendation}</em>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 2: COMPARISON */}
                  {activeTab === "comparison" && (
                    <div className="space-y-6">
                      {report.apps.map((app) => (
                        <div
                          key={`${app.app_name}_${app.entry_type}`}
                          className="bg-white dark:bg-[#0c0c0f] border border-zinc-100 dark:border-zinc-800 rounded-xl p-4 shadow-sm"
                        >
                          <h3 className="text-xs font-bold text-zinc-600 dark:text-zinc-400 mb-4 capitalize">
                            {app.app_name} ({app.entry_type}-entry) - Medians Comparison
                          </h3>
                          <div className="h-[300px]">
                            <ReactECharts
                              option={getAppCompareChartOptions(app)}
                              style={{ height: "100%", width: "100%" }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* TAB 3: TIMELINE */}
                  {activeTab === "timeline" && (
                    <div className="space-y-6">
                      {report.apps.map((app) => (
                        <div
                          key={`${app.app_name}_${app.entry_type}`}
                          className="bg-white dark:bg-[#0c0c0f] border border-zinc-100 dark:border-zinc-800 rounded-xl p-4 shadow-sm"
                        >
                          <h3 className="text-xs font-bold text-zinc-600 dark:text-zinc-400 mb-4 capitalize">
                            {app.app_name} ({app.entry_type}-entry) - Launch Waterfall Sequence
                          </h3>
                          <div className="h-[340px]">
                            <ReactECharts
                              option={getAppWaterfallChartOptions(app)}
                              style={{ height: "100%", width: "100%" }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
