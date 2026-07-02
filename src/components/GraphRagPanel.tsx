"use client";

import React, { useState } from "react";
import { useTelemetry } from "@/contexts/TelemetryContext";
import { Search, Database, Share2, HelpCircle, ArrowRight } from "lucide-react";

interface GraphNode {
  id: string;
  label: string;
  type: "asset" | "component" | "anomaly" | "procedure" | "record";
  x: number;
  y: number;
  details: string;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
  highlighted: boolean;
}

const MOCK_KNOWLEDGE_BASE = {
  vibration: {
    answer: "Graph RAG query resolved. Telemetry logs and structural schematics show that Gas Turbine G-101 (Turbine-01) is exhibiting elevated vibrations (5.2 mm/s) localized at Bearing B1. A matching maintenance record from Q3 2025 indicates a similar anomaly was caused by shaft misalignment. Recommended mitigation is executing SOP-MECH-042 (re-alignment and synthetic lubrication).",
    logs: [
      "Vector search initiated: 'vibration spike turbine-01'",
      "Match found: Node 'Gas Turbine G-101' (similarity: 0.94)",
      "Traversing edges: 'has_part' -> 'Bearing B1', 'suffers' -> 'Bearing Wear'",
      "Retrieved procedure document: 'SOP-MECH-042' (Lubrication & Alignment)",
      "Retrieved historical logs: 'Q3-2025 Maintenance Work-Order #9921'",
      "Synthesizing response context via LLM..."
    ],
    highlightedNodes: ["g101", "bearing-b1", "bearing-wear", "sop-mech", "maint-q3"],
    highlightedEdges: ["g101-b1", "b1-wear", "wear-sop", "b1-q3"]
  },
  lubrication: {
    answer: "Standard Operating Procedure SOP-MECH-042 retrieved. Bearing B1 requires high-temperature synthetic Mobil-SHC-320 polyalphaolefin lubricant. Target cycle: every 4,000 hours, or reactively if casing temperature exceeds 82°C. Injection volume is 45ml, to be administered under 1,000 RPM idle speed to prevent air entrainment.",
    logs: [
      "Vector search initiated: 'lubrication procedure bearing b1'",
      "Match found: Node 'Bearing B1' (similarity: 0.89)",
      "Traversing edges: 'guided_by' -> 'SOP-MECH-042'",
      "Resolving lubricant specifications...",
      "Synthesizing response context via LLM..."
    ],
    highlightedNodes: ["bearing-b1", "sop-mech", "lubricant-type"],
    highlightedEdges: ["b1-sop", "sop-lub"]
  },
  history: {
    answer: "Retrieval report for Centrifugal Compressor C-204. Primary failure mode is 'Compressor Surge' associated with downstream pressure blockages. Historic maintenance logs report two surge events: Oct 2025 (Severe vibration spike, anti-surge valve replaced) and Jan 2026 (Minor surge, bypass valve calibrated). Anti-surge recycling valve (ASV-204) acts as the active mitigation system.",
    logs: [
      "Vector search initiated: 'compressor-02 history failure modes'",
      "Match found: Node 'Compressor C-204' (similarity: 0.91)",
      "Traversing edges: 'exhibits' -> 'Compressor Surge', 'mitigated_by' -> 'Anti-Surge Valve'",
      "Retrieved events: 'Oct-25 Failure Event', 'Jan-26 Failure Event'",
      "Synthesizing response context via LLM..."
    ],
    highlightedNodes: ["c204", "comp-surge", "asv-204", "oct-25", "jan-26"],
    highlightedEdges: ["c204-surge", "surge-asv", "c204-oct", "c204-jan"]
  }
};

const GRAPH_NODES: GraphNode[] = [
  { id: "g101", label: "G-101 (Gas Turbine)", type: "asset", x: 60, y: 110, details: "Asset status: Warning. Telemetry stream: Active." },
  { id: "bearing-b1", label: "Bearing B1", type: "component", x: 160, y: 70, details: "Casing temp: 88.5°C. Vibration: 5.2 mm/s." },
  { id: "bearing-wear", label: "Bearing Wear (F-02)", type: "anomaly", x: 260, y: 40, details: "Confidence: 91%. Wear signature matching telemetry." },
  { id: "sop-mech", label: "SOP-MECH-042", type: "procedure", x: 380, y: 80, details: "Lubrication & Rotor Alignment Procedure v2.1" },
  { id: "maint-q3", label: "Q3-25 Alignment Record", type: "record", x: 180, y: 150, details: "Shaft offset adjusted by +0.12mm. Lubricant flushed." },
  { id: "lubricant-type", label: "Mobil SHC 320", type: "procedure", x: 450, y: 150, details: "Synthetic high-viscosity polyalphaolefin grease." },
  
  { id: "c204", label: "C-204 (Compressor)", type: "asset", x: 60, y: 220, details: "Asset status: OK. Telemetry stream: Active." },
  { id: "comp-surge", label: "Compressor Surge (F-09)", type: "anomaly", x: 180, y: 270, details: "High surge risk. Dynamic pressure instability hazard." },
  { id: "asv-204", label: "Anti-Surge Valve", type: "component", x: 300, y: 220, details: "Pneumatic recycle valve actuator. Status: Operational." },
  { id: "oct-25", label: "Oct-25 Failure Log", type: "record", x: 280, y: 290, details: "Surge event caused by high discharge pressure. 4h downtime." },
  { id: "jan-26", label: "Jan-26 Failure Log", type: "record", x: 380, y: 270, details: "Minor pressure drop surge. Calibrated valve bypass controller." }
];

const GRAPH_EDGES: GraphEdge[] = [
  { source: "g101", target: "bearing-b1", label: "has_part", highlighted: false },
  { source: "bearing-b1", target: "bearing-wear", label: "suffers_from", highlighted: false },
  { source: "bearing-wear", target: "sop-mech", label: "mitigated_by", highlighted: false },
  { source: "bearing-b1", target: "sop-mech", label: "guided_by", highlighted: false },
  { source: "bearing-b1", target: "maint-q3", label: "serviced_in", highlighted: false },
  { source: "g101", target: "maint-q3", label: "recorded_event", highlighted: false },
  { source: "sop-mech", target: "lubricant-type", label: "specifies", highlighted: false },
  
  { source: "c204", target: "comp-surge", label: "vulnerable_to", highlighted: false },
  { source: "comp-surge", target: "asv-204", label: "mitigated_by", highlighted: false },
  { source: "c204", target: "asv-204", label: "controls", highlighted: false },
  { source: "c204", target: "oct-25", label: "history_log", highlighted: false },
  { source: "c204", target: "jan-26", label: "history_log", highlighted: false }
];

export const GraphRagPanel: React.FC = () => {
  const { features } = useTelemetry();
  const [query, setQuery] = useState("");
  const [loadingLogs, setLoadingLogs] = useState<string[]>([]);
  const [logsComplete, setLogsComplete] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [highlightedEdges, setHighlightedEdges] = useState<string[]>([]);
  const [inspectedNode, setInspectedNode] = useState<GraphNode | null>(null);

  if (!features.graphRag) {
    return (
      <div className="border border-industrial-border-dark bg-industrial-panel-dark rounded p-md flex flex-col items-center justify-center text-center py-2xl h-full">
        <HelpCircle className="w-12 h-12 text-industrial-status-offline mb-md" />
        <h3 className="text-lg font-bold font-mono">Graph RAG Disabled</h3>
        <p className="text-sm text-industrial-status-offline max-w-sm mt-xs">Enable Graph RAG feature flags in environment variables to run semantic inspections.</p>
      </div>
    );
  }

  const handleSuggestionClick = (type: "vibration" | "lubrication" | "history") => {
    const data = MOCK_KNOWLEDGE_BASE[type];
    
    // Set query text
    if (type === "vibration") setQuery("Why did the vibration on Turbine-01 spike?");
    else if (type === "lubrication") setQuery("Explain the lubrication procedure for bearing B1");
    else setQuery("List history and failure modes of Compressor-02");

    setLoadingLogs([]);
    setLogsComplete(false);
    setAnswer(null);
    setHighlightedNodes([]);
    setHighlightedEdges([]);

    // Run animation steps
    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < data.logs.length) {
        setLoadingLogs((prev) => [...prev, data.logs[currentStep]]);
        currentStep++;
      } else {
        clearInterval(interval);
        setLogsComplete(true);
        setAnswer(data.answer);
        setHighlightedNodes(data.highlightedNodes);
        setHighlightedEdges(data.highlightedEdges);
      }
    }, 450);
  };

  const handleNodeClick = (node: GraphNode) => {
    setInspectedNode(node);
  };

  const getNodeColor = (type: string, isHighlighted: boolean) => {
    if (isHighlighted) {
      switch (type) {
        case "asset": return "fill-industrial-status-ok stroke-industrial-bg-contrast";
        case "component": return "fill-blue-500 stroke-industrial-bg-contrast";
        case "anomaly": return "fill-industrial-status-critical stroke-industrial-bg-contrast";
        case "procedure": return "fill-industrial-status-warning stroke-industrial-bg-contrast";
        default: return "fill-industrial-status-offline stroke-industrial-bg-contrast";
      }
    } else {
      switch (type) {
        case "asset": return "fill-industrial-status-ok/30 stroke-industrial-status-ok/60";
        case "component": return "fill-blue-500/20 stroke-blue-500/50";
        case "anomaly": return "fill-industrial-status-critical/20 stroke-industrial-status-critical/50";
        case "procedure": return "fill-industrial-status-warning/20 stroke-industrial-status-warning/50";
        default: return "fill-industrial-status-offline/20 stroke-industrial-status-offline/50";
      }
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-md h-full">
      {/* Query Terminal Panel (Left Side) */}
      <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col gap-md">
        <div>
          <span className="text-xs uppercase tracking-wider text-industrial-status-offline font-semibold">Semantic Query Engine</span>
          <h2 className="text-lg font-bold font-mono text-industrial-bg-light">Graph RAG Panel</h2>
          <p className="text-xs text-industrial-status-offline">Query structured knowledge-graph networks linked to asset operational procedures.</p>
        </div>

        {/* Query Input Box */}
        <div className="relative">
          <input
            type="text"
            className="w-full bg-industrial-bg-dark border border-industrial-border-dark rounded px-md py-sm pl-10 font-mono text-sm text-industrial-bg-light focus:outline-none focus:border-industrial-status-warning"
            placeholder="Search operational logs, engineering manuals, history..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Search className="absolute left-3 top-3 w-4 h-4 text-industrial-status-offline" />
        </div>

        {/* Suggestion tags */}
        <div className="flex flex-col gap-xs">
          <span className="text-[10px] text-industrial-status-offline font-mono font-bold uppercase">Sample Queries:</span>
          <div className="flex flex-col gap-sm">
            <button
              onClick={() => handleSuggestionClick("vibration")}
              className="text-left text-xs bg-industrial-bg-dark hover:bg-industrial-bg-dark/80 hover:border-industrial-status-ok/30 border border-industrial-border-dark p-sm rounded font-mono text-industrial-status-ok flex justify-between items-center group transition"
            >
              <span>Why did the vibration on Turbine-01 spike?</span>
              <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition translate-x-[-4px] group-hover:translate-x-0" />
            </button>
            <button
              onClick={() => handleSuggestionClick("lubrication")}
              className="text-left text-xs bg-industrial-bg-dark hover:bg-industrial-bg-dark/80 hover:border-industrial-status-warning/30 border border-industrial-border-dark p-sm rounded font-mono text-industrial-status-warning flex justify-between items-center group transition"
            >
              <span>Explain the lubrication procedure for bearing B1</span>
              <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition translate-x-[-4px] group-hover:translate-x-0" />
            </button>
            <button
              onClick={() => handleSuggestionClick("history")}
              className="text-left text-xs bg-industrial-bg-dark hover:bg-industrial-bg-dark/80 hover:border-industrial-status-offline/40 border border-industrial-border-dark p-sm rounded font-mono text-industrial-bg-light flex justify-between items-center group transition"
            >
              <span>List history and failure modes of Compressor-02</span>
              <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition translate-x-[-4px] group-hover:translate-x-0" />
            </button>
          </div>
        </div>

        {/* Retrieval Logs terminal */}
        <div className="flex-grow bg-industrial-bg-dark border border-industrial-border-dark rounded p-sm font-mono text-xs overflow-y-auto min-h-[150px] max-h-[220px]">
          <div className="flex justify-between border-b border-industrial-border-dark pb-xs mb-xs text-[10px] text-industrial-status-offline">
            <span>RAG PIPELINE TERMINAL</span>
            <Database className="w-3 h-3" />
          </div>
          {loadingLogs.map((log, idx) => (
            <div key={idx} className="flex gap-sm items-start text-industrial-status-ok py-0.5">
              <span className="text-industrial-status-offline select-none">&gt;&gt;</span>
              <span>{log}</span>
            </div>
          ))}
          {loadingLogs.length > 0 && !logsComplete && (
            <div className="flex gap-sm items-start text-industrial-status-warning py-0.5 animate-pulse">
              <span className="text-industrial-status-offline">&gt;&gt;</span>
              <span>Executing pipeline step...</span>
            </div>
          )}
          {loadingLogs.length === 0 && (
            <div className="text-industrial-status-offline text-center py-md italic">
              Awaiting query execution...
            </div>
          )}
        </div>

        {/* Generated Answer Display */}
        {answer && (
          <div className="border border-industrial-status-ok/20 bg-industrial-status-ok/5 p-sm rounded">
            <span className="text-[10px] font-mono font-bold uppercase text-industrial-status-ok flex items-center gap-xs mb-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-industrial-status-ok" />
              Retrieved Answer Synthesis
            </span>
            <p className="text-xs font-mono leading-relaxed text-industrial-bg-light">{answer}</p>
          </div>
        )}
      </div>

      {/* Network Knowledge Graph Visualizer (Right Side) */}
      <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between min-h-[400px] relative">
        <div className="flex justify-between items-center border-b border-industrial-border-dark pb-sm mb-sm">
          <div>
            <span className="text-[10px] font-mono text-industrial-status-offline font-semibold uppercase">Knowledge Mesh</span>
            <h3 className="font-bold text-sm font-mono">Semantic Graph Database Schema</h3>
          </div>
          <Share2 className="w-4 h-4 text-industrial-status-offline" />
        </div>

        {/* Graph representation */}
        <div className="flex-grow flex items-center justify-center relative overflow-hidden bg-industrial-bg-dark/40 border border-industrial-border-dark/50 rounded">
          <svg className="w-full h-full min-h-[300px] max-h-[350px] overflow-visible" viewBox="0 0 500 320">
            {/* Draw Links/Edges */}
            {GRAPH_EDGES.map((edge, idx) => {
              const srcNode = GRAPH_NODES.find((n) => n.id === edge.source);
              const tgtNode = GRAPH_NODES.find((n) => n.id === edge.target);
              if (!srcNode || !tgtNode) return null;

              const isHighlighted = highlightedEdges.includes(`${edge.source}-${edge.target}`) || highlightedEdges.includes(`${edge.target}-${edge.source}`);

              return (
                <g key={idx}>
                  <line
                    x1={srcNode.x}
                    y1={srcNode.y}
                    x2={tgtNode.x}
                    y2={tgtNode.y}
                    stroke={isHighlighted ? "#f59e0b" : "#2a303c"}
                    strokeWidth={isHighlighted ? "2" : "1"}
                    strokeDasharray={isHighlighted ? "none" : "3 3"}
                  />
                  {/* Small edge label on hover */}
                  {isHighlighted && (
                    <text
                      x={(srcNode.x + tgtNode.x) / 2}
                      y={(srcNode.y + tgtNode.y) / 2 - 4}
                      textAnchor="middle"
                      className="fill-industrial-status-warning font-mono text-[7px]"
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Draw Nodes */}
            {GRAPH_NODES.map((node) => {
              const isHighlighted = highlightedNodes.includes(node.id);
              const isInspected = inspectedNode?.id === node.id;
              
              return (
                <g
                  key={node.id}
                  className="cursor-pointer group"
                  onClick={() => handleNodeClick(node)}
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.type === "asset" ? "14" : "10"}
                    className={`${getNodeColor(node.type, isHighlighted)} transition-colors duration-300`}
                    strokeWidth={isInspected ? "2.5" : "1.5"}
                  />
                  {/* Inside circle label */}
                  {node.type === "asset" && (
                    <circle cx={node.x} cy={node.y} r="4" className="fill-industrial-bg-dark" />
                  )}
                  {/* Outer label */}
                  <text
                    x={node.x}
                    y={node.y + (node.type === "asset" ? 22 : 18)}
                    textAnchor="middle"
                    className={`font-mono text-[8px] font-bold ${
                      isHighlighted ? "fill-industrial-bg-light" : "fill-industrial-status-offline"
                    } group-hover:fill-industrial-status-warning`}
                  >
                    {node.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Node detail inspect drawer overlay */}
          {inspectedNode && (
            <div className="absolute bottom-2 left-2 right-2 bg-industrial-bg-dark/95 border border-industrial-status-warning/40 p-sm rounded font-mono text-[10px] flex justify-between items-start">
              <div>
                <span className="text-[8px] uppercase px-sm py-0.5 rounded bg-industrial-status-warning/10 text-industrial-status-warning font-bold mr-sm">
                  {inspectedNode.type}
                </span>
                <span className="font-bold text-industrial-bg-light">{inspectedNode.label}</span>
                <p className="text-industrial-status-offline mt-xs">{inspectedNode.details}</p>
              </div>
              <button
                onClick={() => setInspectedNode(null)}
                className="text-industrial-status-offline hover:text-industrial-status-critical font-bold text-xs px-xs"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-sm justify-center border-t border-industrial-border-dark pt-sm text-[8px] font-mono text-industrial-status-offline">
          <div className="flex items-center gap-xs">
            <span className="w-2 h-2 rounded-full bg-industrial-status-ok/30 border border-industrial-status-ok" /> Assets
          </div>
          <div className="flex items-center gap-xs">
            <span className="w-2 h-2 rounded-full bg-blue-500/20 border border-blue-500" /> Components
          </div>
          <div className="flex items-center gap-xs">
            <span className="w-2 h-2 rounded-full bg-industrial-status-critical/20 border border-industrial-status-critical" /> Anomaly Signs
          </div>
          <div className="flex items-center gap-xs">
            <span className="w-2 h-2 rounded-full bg-industrial-status-warning/20 border border-industrial-status-warning" /> Procedures
          </div>
          <div className="flex items-center gap-xs">
            <span className="w-2 h-2 rounded-full bg-industrial-status-offline/20 border border-industrial-status-offline" /> Records
          </div>
        </div>
      </div>
    </div>
  );
};
