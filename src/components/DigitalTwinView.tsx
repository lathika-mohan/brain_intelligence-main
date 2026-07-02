"use client";

import React, { useState } from "react";
import { useTelemetry } from "@/contexts/TelemetryContext";
import { Activity, Gauge, ShieldAlert } from "lucide-react";

export const DigitalTwinView: React.FC = () => {
  const { assets, selectedAssetId, activeAnomaly } = useTelemetry();
  const currentAsset = assets.find((a) => a.id === selectedAssetId);
  const [hoveredComponent, setHoveredComponent] = useState<string | null>(null);

  if (!currentAsset) return null;

  const { telemetry, history } = currentAsset;

  // Helpers to draw custom historical SVG charts
  const renderMiniChart = (
    dataKey: keyof typeof telemetry,
    colorClass: string,
    minVal: number,
    maxVal: number
  ) => {
    const width = 240;
    const height = 48;
    const padding = 2;
    
    if (history.length < 2) return null;

    const points = history.map((reading, index) => {
      const val = Number(reading[dataKey]) || 0;
      const x = padding + (index / (history.length - 1)) * (width - padding * 2);
      // Normalize y: invert since SVG coordinates are top-to-bottom
      const range = maxVal - minVal || 1;
      const normalizedVal = (val - minVal) / range;
      const clampedVal = Math.max(0, Math.min(1, normalizedVal));
      const y = height - padding - clampedVal * (height - padding * 2);
      return `${x},${y}`;
    }).join(" ");

    return (
      <svg className="w-full h-12 overflow-visible" viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id={`gradient-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.25" className={colorClass} />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.0" className={colorClass} />
          </linearGradient>
        </defs>
        <path
          d={`M ${padding},${height - padding} L ${points} L ${width - padding},${height - padding} Z`}
          fill={`url(#gradient-${dataKey})`}
          className={colorClass}
        />
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          points={points}
          className={colorClass}
        />
        {/* Draw latest point pulsing indicator */}
        {history.length > 0 && (
          <circle
            cx={width - padding}
            cy={height - padding - ((Number(telemetry[dataKey]) || 0) - minVal) / (maxVal - minVal || 1) * (height - padding * 2)}
            r="3"
            className={`${colorClass} fill-current animate-ping`}
          />
        )}
      </svg>
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ok": return "text-industrial-status-ok border-industrial-status-ok/30 bg-industrial-status-ok/5";
      case "warning": return "text-industrial-status-warning border-industrial-status-warning/40 bg-industrial-status-warning/10";
      case "critical": return "text-industrial-status-critical border-industrial-status-critical/40 bg-industrial-status-critical/10";
      default: return "text-industrial-status-offline border-industrial-status-offline/30 bg-industrial-status-offline/5";
    }
  };

  // Helper to retrieve flow line class depending on speed
  const getPipeFlowClass = () => {
    if (telemetry.status === "critical") return "stroke-industrial-status-critical pipe-flow-slow";
    if (telemetry.status === "warning") return "stroke-industrial-status-warning pipe-flow-slow";
    const speedVal = telemetry.speed;
    if (speedVal > 4000) return "stroke-industrial-status-ok pipe-flow-fast";
    if (speedVal > 2500) return "stroke-industrial-status-ok pipe-flow-medium";
    return "stroke-industrial-status-ok pipe-flow-slow";
  };

  return (
    <div className="flex flex-col gap-md h-full">
      {/* Asset Heading & Summary Status */}
      <div className={`flex justify-between items-center border p-md rounded bg-industrial-panel-dark border-industrial-border-dark`}>
        <div>
          <span className="text-xs uppercase tracking-wider text-industrial-status-offline font-semibold">Asset Telemetry</span>
          <h2 className="text-xl font-bold font-mono text-industrial-bg-light">{currentAsset.name}</h2>
          <p className="text-xs text-industrial-status-offline">ID: {currentAsset.id.toUpperCase()} | Type: {currentAsset.type}</p>
        </div>
        <div className={`flex items-center gap-xs border px-md py-sm rounded ${getStatusColor(currentAsset.status)}`}>
          <span className={`w-3 h-3 rounded-full ${
            currentAsset.status === "ok" ? "bg-industrial-status-ok glow-ok" :
            currentAsset.status === "warning" ? "bg-industrial-status-warning glow-warning" :
            currentAsset.status === "critical" ? "bg-industrial-status-critical glow-critical" :
            "bg-industrial-status-offline"
          }`} />
          <span className="font-mono text-sm font-bold uppercase tracking-wider">{currentAsset.status}</span>
        </div>
      </div>

      {/* Main Grid: Visual Digital Twin + Parameter Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-md flex-grow">
        {/* Dynamic SVG Schematic (Col span 2) */}
        <div className="lg:col-span-2 border border-industrial-border-dark bg-industrial-panel-dark rounded p-md flex flex-col justify-between grid-mesh relative crt-scanlines min-h-[400px]">
          <div className="flex justify-between items-start z-10">
            <div>
              <span className="text-xs font-mono font-semibold tracking-wider text-industrial-status-ok uppercase flex items-center gap-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-industrial-status-ok animate-pulse" />
                Live Digital Twin Streaming
              </span>
              <p className="text-xs text-industrial-status-offline mt-xs">Hover component nodes to inspect sensor readings.</p>
            </div>
            {hoveredComponent && (
              <div className="text-xs bg-industrial-bg-dark border border-industrial-border-dark px-sm py-xs rounded font-mono text-industrial-status-warning">
                Inspecting: <span className="text-industrial-bg-light uppercase">{hoveredComponent}</span>
              </div>
            )}
          </div>

          {/* Asset Visual Renderers */}
          <div className="flex-grow flex items-center justify-center py-lg">
            {currentAsset.id === "turbine-01" && (
              <svg className="w-full max-w-[500px] h-auto overflow-visible text-industrial-bg-light" viewBox="0 0 500 220">
                {/* Background flow pipes */}
                <path d="M 20,110 L 150,110" fill="none" strokeWidth="6" className={getPipeFlowClass()} />
                <path d="M 350,110 L 480,110" fill="none" strokeWidth="8" className={getPipeFlowClass()} />
                
                {/* Fuel intake */}
                <path d="M 210,20 L 210,65" fill="none" strokeWidth="4" className={`${telemetry.status !== "critical" ? "stroke-industrial-status-ok pipe-flow-medium" : "stroke-industrial-status-critical"}`} />
                <text x="210" y="15" textAnchor="middle" className="fill-industrial-status-offline font-mono text-[9px] uppercase">Fuel Intake</text>
                
                {/* Air Compressor Stage Section */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Air Compressor Stage")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <path d="M 70,70 L 150,80 L 150,140 L 70,150 Z" fill="#1e2430" stroke="#3b4252" strokeWidth="2" />
                  {/* Rotor Blades inside */}
                  <g className="origin-[110px_110px]" style={{ transform: `rotate(${telemetry.status !== "critical" ? (Date.now() / 15) % 360 : 0}deg)` }}>
                    <line x1="110" y1="80" x2="110" y2="140" stroke="#4c566a" strokeWidth="3" />
                    <line x1="80" y1="110" x2="140" y2="110" stroke="#4c566a" strokeWidth="3" />
                    <line x1="90" y1="90" x2="130" y2="130" stroke="#4c566a" strokeWidth="2" />
                    <line x1="90" y1="130" x2="130" y2="90" stroke="#4c566a" strokeWidth="2" />
                  </g>
                  <text x="110" y="114" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[10px] select-none font-bold uppercase pointer-events-none">Comp</text>
                  <rect x="80" y="70" width="60" height="80" className={`fill-transparent ${hoveredComponent === "Air Compressor Stage" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1" />
                </g>

                {/* Combustor Chamber Section */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Combustor Chamber")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <rect x="150" y="60" width="100" height="100" rx="4" fill="#2e3440" stroke="#434c5e" strokeWidth="2" />
                  {/* Burning Glow representation */}
                  <rect
                    x="160" y="70" width="80" height="80" rx="4"
                    fill={telemetry.status === "critical" ? "#ef4444" : telemetry.status === "warning" ? "#d08770" : "#5e81ac"}
                    opacity={0.15 + (Math.sin(Date.now() / 100) * 0.05) + (telemetry.load / 500)}
                    className="animate-pulse"
                  />
                  {/* Fire flames visual */}
                  {telemetry.status !== "critical" && (
                    <path
                      d="M 170,110 Q 185,90 200,110 T 230,110"
                      fill="none"
                      stroke={telemetry.status === "warning" ? "#f59e0b" : "#3b82f6"}
                      strokeWidth="3"
                      className="animate-pulse"
                    />
                  )}
                  <text x="200" y="114" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[10px] select-none font-bold uppercase pointer-events-none">Combustor</text>
                  <rect x="150" y="60" width="100" height="100" className={`fill-transparent ${hoveredComponent === "Combustor Chamber" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1" />
                </g>

                {/* Power Turbine Stage Section */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("High-Pressure Turbine")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <path d="M 250,80 L 330,70 L 330,150 L 250,140 Z" fill="#1e2430" stroke="#3b4252" strokeWidth="2" />
                  {/* Turbine blades rotating */}
                  <g className="origin-[290px_110px]" style={{ transform: `rotate(${telemetry.status !== "critical" ? (Date.now() / 10) % 360 : 0}deg)` }}>
                    <line x1="290" y1="75" x2="290" y2="145" stroke="#88c0d0" strokeWidth="3" />
                    <line x1="255" y1="110" x2="325" y2="110" stroke="#88c0d0" strokeWidth="3" />
                    <line x1="265" y1="85" x2="315" y2="135" stroke="#88c0d0" strokeWidth="2" />
                    <line x1="265" y1="135" x2="315" y2="85" stroke="#88c0d0" strokeWidth="2" />
                  </g>
                  <text x="290" y="114" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[10px] select-none font-bold uppercase pointer-events-none">Turbine</text>
                  <rect x="250" y="70" width="80" height="80" className={`fill-transparent ${hoveredComponent === "High-Pressure Turbine" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1" />
                </g>

                {/* Main Bearings Sensor Area */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Main Bearings B1")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <circle cx="150" cy="110" r="10" fill="#2b303c" stroke={telemetry.status === "warning" && activeAnomaly === "bearing-wear" ? "#ef4444" : "#4c566a"} strokeWidth="2" className={telemetry.status === "warning" && activeAnomaly === "bearing-wear" ? "animate-pulse" : ""} />
                  <circle cx="150" cy="110" r="4" fill={telemetry.status === "warning" && activeAnomaly === "bearing-wear" ? "#ef4444" : "#10b981"} />
                  <text x="150" y="132" textAnchor="middle" className="fill-industrial-status-offline font-mono text-[8px] uppercase select-none pointer-events-none">B1 Sensor</text>
                </g>

                {/* Generator Section */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Generator Unit")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <rect x="350" y="80" width="90" height="60" rx="2" fill="#2e3440" stroke="#4c566a" strokeWidth="2" />
                  {/* Coils and magnetic flux animation */}
                  <line x1="360" y1="90" x2="430" y2="90" stroke="#bf616a" strokeWidth="2" strokeDasharray="5 3" />
                  <line x1="360" y1="130" x2="430" y2="130" stroke="#bf616a" strokeWidth="2" strokeDasharray="5 3" />
                  <rect x="380" y="95" width="30" height="30" fill="#3b4252" stroke="#d8dee9" />
                  <text x="395" y="113" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[9px] select-none font-bold pointer-events-none">GEN</text>
                  <rect x="350" y="80" width="90" height="60" className={`fill-transparent ${hoveredComponent === "Generator Unit" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1" />
                </g>

                {/* Core Shaft */}
                <line x1="110" y1="110" x2="350" y2="110" stroke="#d8dee9" strokeWidth="4" />
                
                {/* Labels and hot zones */}
                {hoveredComponent === "Main Bearings B1" && (
                  <g className="pointer-events-none">
                    <rect x="130" y="10" width="140" height="40" rx="4" fill="#0f1115" stroke="#ef4444" strokeWidth="1.5" />
                    <text x="140" y="24" className="fill-industrial-status-critical font-mono text-[9px] font-bold">TEMP: {telemetry.temperature}°C</text>
                    <text x="140" y="38" className="fill-industrial-status-critical font-mono text-[9px] font-bold">VIB: {telemetry.vibration} mm/s</text>
                  </g>
                )}
              </svg>
            )}

            {currentAsset.id === "compressor-02" && (
              <svg className="w-full max-w-[500px] h-auto overflow-visible text-industrial-bg-light" viewBox="0 0 500 220">
                {/* Fluid piping */}
                <path d="M 20,110 Q 150,110 150,50" fill="none" strokeWidth="6" className={getPipeFlowClass()} />
                <path d="M 330,110 L 480,110" fill="none" strokeWidth="8" className={getPipeFlowClass()} />

                {/* Intake flow labels */}
                <text x="50" y="95" className="fill-industrial-status-offline font-mono text-[9px] uppercase">Gaseous Intake</text>
                
                {/* Main Impeller scroll housing */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Centrifugal Impeller")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <path d="M 150,50 C 150,50 180,10 240,10 C 300,10 330,50 330,110 C 330,170 300,210 240,210 C 180,210 150,170 150,110 Z" fill="#1e2430" stroke="#3b4252" strokeWidth="2" />
                  
                  {/* Rotating Impeller blades */}
                  <g className="origin-[240px_110px]" style={{ transform: `rotate(${telemetry.status !== "critical" ? (Date.now() / 8) % 360 : 0}deg)` }}>
                    <circle cx="240" cy="110" r="45" fill="none" stroke="#4c566a" strokeWidth="1.5" strokeDasharray="3 3" />
                    {Array.from({ length: 8 }).map((_, idx) => (
                      <path
                        key={idx}
                        d={`M 240,110 Q 250,85 275,75`}
                        fill="none"
                        stroke="#88c0d0"
                        strokeWidth="2.5"
                        style={{ transform: `rotate(${idx * 45}deg)`, transformOrigin: "240px 110px" }}
                      />
                    ))}
                    <circle cx="240" cy="110" r="12" fill="#d8dee9" />
                  </g>
                  <text x="240" y="25" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[10px] select-none font-bold uppercase pointer-events-none">Impeller Scroll</text>
                  <path d="M 150,50 C 150,50 180,10 240,10 C 300,10 330,50 330,110 C 330,170 300,210 240,210 C 180,210 150,170 150,110 Z" className={`fill-transparent ${hoveredComponent === "Centrifugal Impeller" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1.5" />
                </g>

                {/* Diffuser & Discharge Section */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Discharge Valve")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <rect x="330" y="85" width="40" height="50" fill="#2e3440" stroke="#4c566a" strokeWidth="2" />
                  <polygon points="340,95 360,95 350,110" fill="#bf616a" />
                  <polygon points="340,125 360,125 350,110" fill="#bf616a" />
                  <text x="350" y="148" textAnchor="middle" className="fill-industrial-status-offline font-mono text-[8px] uppercase select-none pointer-events-none">Discharge</text>
                  <rect x="330" y="85" width="40" height="50" className={`fill-transparent ${hoveredComponent === "Discharge Valve" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1" />
                </g>

                {/* Sensor labels on discharge pressure */}
                {hoveredComponent === "Discharge Valve" && (
                  <g className="pointer-events-none">
                    <rect x="310" y="15" width="130" height="40" rx="4" fill="#0f1115" stroke="#ef4444" strokeWidth="1.5" />
                    <text x="320" y="30" className="fill-industrial-status-critical font-mono text-[9px] font-bold">PRESS: {telemetry.pressure} bar</text>
                    <text x="320" y="44" className="fill-industrial-status-critical font-mono text-[9px] font-bold">FLOW: {telemetry.flowRate} L/m</text>
                  </g>
                )}
              </svg>
            )}

            {currentAsset.id === "pump-03" && (
              <svg className="w-full max-w-[500px] h-auto overflow-visible text-industrial-bg-light" viewBox="0 0 500 220">
                {/* Fluid piping */}
                <path d="M 20,110 L 150,110" fill="none" strokeWidth="6" className={getPipeFlowClass()} />
                <path d="M 290,110 L 480,110" fill="none" strokeWidth="8" className={getPipeFlowClass()} />

                {/* Inlet and Outlet piping lines */}
                <path d="M 220,110 L 220,50" fill="none" strokeWidth="5" className={getPipeFlowClass()} />

                {/* Piston chamber */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Reciprocating Piston")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <rect x="150" y="70" width="140" height="80" rx="4" fill="#1e2430" stroke="#3b4252" strokeWidth="2" />
                  
                  {/* Moving Piston (Uses sin translate coordinate) */}
                  <g style={{ transform: `translateX(${telemetry.status !== "critical" ? Math.sin(Date.now() / 200) * 20 : 0}px)` }}>
                    <rect x="190" y="75" width="20" height="70" fill="#88c0d0" stroke="#d8dee9" strokeWidth="1.5" />
                    {/* Connecting rod */}
                    <line x1="190" y1="110" x2="100" y2="110" stroke="#e5e9f0" strokeWidth="4" />
                  </g>

                  {/* Crankshaft rotating wheel */}
                  <g className="origin-[100px_110px]" style={{ transform: `rotate(${telemetry.status !== "critical" ? (Date.now() / 5) % 360 : 0}deg)` }}>
                    <circle cx="100" cy="110" r="30" fill="#2e3440" stroke="#4c566a" strokeWidth="2" />
                    <line x1="100" y1="110" x2="125" y2="125" stroke="#bf616a" strokeWidth="3.5" />
                    <circle cx="125" cy="125" r="4" fill="#d8dee9" />
                  </g>

                  <text x="220" y="60" textAnchor="middle" className="fill-industrial-bg-light font-mono text-[10px] select-none font-bold uppercase pointer-events-none">Piston Chamber</text>
                  <rect x="150" y="70" width="140" height="80" className={`fill-transparent ${hoveredComponent === "Reciprocating Piston" ? "stroke-industrial-status-warning" : "stroke-transparent"}`} strokeWidth="1.5" />
                </g>

                {/* Suction Check Valves */}
                <g 
                  className="cursor-pointer"
                  onMouseEnter={() => setHoveredComponent("Check Valve V1")}
                  onMouseLeave={() => setHoveredComponent(null)}
                >
                  <circle cx="150" cy="110" r="10" fill="#2b303c" stroke="#4c566a" />
                  <path d="M 146,110 L 154,110 M 150,106 L 150,114" stroke="#d8dee9" strokeWidth="1.5" />
                  <text x="150" y="132" textAnchor="middle" className="fill-industrial-status-offline font-mono text-[8px] uppercase select-none pointer-events-none">Suction</text>
                </g>

                {/* Inspecting check valve details */}
                {hoveredComponent === "Check Valve V1" && (
                  <g className="pointer-events-none">
                    <rect x="130" y="10" width="130" height="40" rx="4" fill="#0f1115" stroke="#ef4444" strokeWidth="1.5" />
                    <text x="140" y="24" className="fill-industrial-status-critical font-mono text-[9px] font-bold">FLOW: {telemetry.flowRate} L/m</text>
                    <text x="140" y="38" className="fill-industrial-status-critical font-mono text-[9px] font-bold">STROKE: {Math.round(telemetry.speed / 60)} Hz</text>
                  </g>
                )}
              </svg>
            )}
          </div>

          {/* Component status overview */}
          <div className="flex flex-wrap gap-xs z-10 pt-md border-t border-industrial-border-dark text-[11px] font-mono">
            <span className="text-industrial-status-offline">Sub-Systems:</span>
            <span className="text-industrial-status-ok flex items-center gap-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-industrial-status-ok" /> Shaft Drive
            </span>
            <span className={`flex items-center gap-xs ${telemetry.status === "critical" && activeAnomaly === "electrical-trip" ? "text-industrial-status-critical animate-pulse" : "text-industrial-status-ok"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${telemetry.status === "critical" && activeAnomaly === "electrical-trip" ? "bg-industrial-status-critical" : "bg-industrial-status-ok"}`} /> Electronics
            </span>
            <span className={`flex items-center gap-xs ${telemetry.status === "warning" && activeAnomaly === "bearing-wear" ? "text-industrial-status-warning animate-pulse" : "text-industrial-status-ok"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${telemetry.status === "warning" && activeAnomaly === "bearing-wear" ? "bg-industrial-status-warning" : "bg-industrial-status-ok"}`} /> Bearings B1-B2
            </span>
            <span className={`flex items-center gap-xs ${telemetry.status === "critical" && activeAnomaly === "compressor-surge" ? "text-industrial-status-critical animate-pulse" : "text-industrial-status-ok"}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${telemetry.status === "critical" && activeAnomaly === "compressor-surge" ? "bg-industrial-status-critical" : "bg-industrial-status-ok"}`} /> Hydraulics
            </span>
          </div>
        </div>

        {/* Telemetry Sensor Panels (1 Col) */}
        <div className="flex flex-col gap-md">
          {/* Card: RPM & Torque */}
          <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-industrial-status-offline uppercase tracking-wider">Rotational Speed</span>
              <Gauge className="w-4 h-4 text-industrial-status-ok" />
            </div>
            <div className="my-sm flex items-baseline gap-xs">
              <span className="text-2xl font-bold font-mono text-industrial-bg-light">{telemetry.speed}</span>
              <span className="text-xs text-industrial-status-offline font-mono">RPM</span>
            </div>
            {renderMiniChart("speed", "text-industrial-status-ok", 0, currentAsset.id.includes("compressor") ? 5500 : 3500)}
          </div>

          {/* Card: Vibration & Temp */}
          <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-industrial-status-offline uppercase tracking-wider">Housing Vibration</span>
              <Activity className="w-4 h-4 text-industrial-status-warning" />
            </div>
            <div className="my-sm flex items-baseline gap-xs">
              <span className={`text-2xl font-bold font-mono ${telemetry.vibration > 4 ? "text-industrial-status-critical" : telemetry.vibration > 3 ? "text-industrial-status-warning" : "text-industrial-bg-light"}`}>{telemetry.vibration}</span>
              <span className="text-xs text-industrial-status-offline font-mono">mm/s</span>
            </div>
            {renderMiniChart("vibration", "text-industrial-status-warning", 0, 10)}
          </div>

          {/* Card: Pressure & Flow */}
          <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-industrial-status-offline uppercase tracking-wider">Discharge Pressure</span>
              <Gauge className="w-4 h-4 text-industrial-status-ok" />
            </div>
            <div className="my-sm flex items-baseline gap-xs">
              <span className="text-2xl font-bold font-mono text-industrial-bg-light">{telemetry.pressure}</span>
              <span className="text-xs text-industrial-status-offline font-mono">bar</span>
            </div>
            {renderMiniChart("pressure", "text-industrial-status-ok", 0, currentAsset.id.includes("compressor") ? 60 : 20)}
          </div>

          {/* Card: Anomaly Score */}
          <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-industrial-status-offline uppercase tracking-wider">AI Risk Index</span>
              <ShieldAlert className="w-4 h-4 text-industrial-status-critical" />
            </div>
            <div className="my-sm flex justify-between items-center">
              <div className="flex items-baseline gap-xs">
                <span className={`text-2xl font-bold font-mono ${telemetry.riskScore > 80 ? "text-industrial-status-critical" : telemetry.riskScore > 50 ? "text-industrial-status-warning" : "text-industrial-status-ok"}`}>{telemetry.riskScore}%</span>
              </div>
              <span className="text-[10px] font-mono bg-industrial-bg-light/5 border border-industrial-border-dark px-sm py-0.5 rounded text-industrial-status-offline">SHAP active</span>
            </div>
            {renderMiniChart("riskScore", "text-industrial-status-critical", 0, 100)}
          </div>
        </div>
      </div>
    </div>
  );
};
