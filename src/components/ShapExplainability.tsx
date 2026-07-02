"use client";

import React, { useState } from "react";
import { useTelemetry } from "@/contexts/TelemetryContext";
import { ShieldAlert, Info, HelpCircle } from "lucide-react";

interface SHAPFeature {
  name: string;
  value: string;
  shapValue: number; // positive = pushes risk up, negative = pulls risk down
  desc: string;
}

export const ShapExplainability: React.FC = () => {
  const { assets, selectedAssetId, features, activeAnomaly } = useTelemetry();
  const [hoveredFeature, setHoveredFeature] = useState<string | null>(null);

  if (!features.shap) {
    return (
      <div className="border border-industrial-border-dark bg-industrial-panel-dark rounded p-md flex flex-col items-center justify-center text-center py-2xl h-full">
        <HelpCircle className="w-12 h-12 text-industrial-status-offline mb-md" />
        <h3 className="text-lg font-bold font-mono">SHAP Explainability Disabled</h3>
        <p className="text-sm text-industrial-status-offline max-w-sm mt-xs">Enable SHAP explainability feature flags in environment variables to run model prediction disclosures.</p>
      </div>
    );
  }

  const currentAsset = assets.find((a) => a.id === selectedAssetId);
  if (!currentAsset) return null;

  const { telemetry } = currentAsset;

  // Calculate dynamic SHAP features based on active telemetry and anomalies
  const getShapFeatures = (): SHAPFeature[] => {
    const isTurbine = currentAsset.id.includes("turbine");
    const isCompressor = currentAsset.id.includes("compressor");
    
    const baseList: SHAPFeature[] = [];

    if (isTurbine) {
      if (activeAnomaly === "bearing-wear") {
        baseList.push(
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 45.2, desc: "Extreme vibration detected at Bearing B1 housing." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: 22.1, desc: "Thermal buildup due to increased bearing wear friction." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: -3.5, desc: "Rotation speed is steady, providing slight negative influence on risk." },
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: 0.8, desc: "Outlet pressure matches output requirements." },
          { name: "Electrical Load", value: `${telemetry.load} kW`, shapValue: 3.6, desc: "Load is high, slightly compounding bearing stresses." }
        );
      } else if (activeAnomaly === "electrical-trip") {
        baseList.push(
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: 55.4, desc: "Severe RPM deceleration represents a trip threshold breach." },
          { name: "Electrical Load", value: `${telemetry.load} kW`, shapValue: 32.1, desc: "Sudden load loss indicates breaker disconnection." },
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 12.8, desc: "Transient vibrations during shutdown deceleration." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: -5.2, desc: "Cooling thermal inertia reduces overall fire/overheating risks." },
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: 3.4, desc: "Pressure drops below nominal thresholds." }
        );
      } else {
        // Nominal
        baseList.push(
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 1.1, desc: "Vibrations are within nominal operational bounds." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: -1.2, desc: "Thermal readings are well within cooling system tolerances." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: 0.5, desc: "Operating speed matches setpoint profile." },
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: -0.8, desc: "Pressure profiles are stable." },
          { name: "Electrical Load", value: `${telemetry.load} kW`, shapValue: 0.9, desc: "Load parameters match nominal grid demands." }
        );
      }
    } else if (isCompressor) {
      if (activeAnomaly === "compressor-surge") {
        baseList.push(
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: 52.8, desc: "Drastic pressure drop triggers aerodynamic surge thresholds." },
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 34.6, desc: "Mechanical shock and impeller buffet vibrations." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: -6.4, desc: "RPM drop slows compressor down, reducing friction risks." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: 11.2, desc: "Frictional hot gas leakage raises housing temperatures." },
          { name: "Electrical Load", value: `${telemetry.load} kW`, shapValue: 0.2, desc: "Load fluctuations are secondary symptoms." }
        );
      } else {
        baseList.push(
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: 0.4, desc: "Discharge pressure levels match dynamic requirements." },
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 1.5, desc: "Slight nominal impeller hum." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: -1.1, desc: "Synchronous speed matching network frequencies." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: 0.8, desc: "Temperature within acceptable boundaries." },
          { name: "Electrical Load", value: `${telemetry.load} kW`, shapValue: 0.2, desc: "Nominal load profiles." }
        );
      }
    } else { // Pump
      if (activeAnomaly === "leakage") {
        baseList.push(
          { name: "Discharge Flow", value: `${telemetry.flowRate} L/m`, shapValue: 44.8, desc: "Flow rate dropped significantly below expected capacity." },
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: 24.2, desc: "Substantial pressure loss in the outlet lines." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: -3.8, desc: "Motor runs at full speed, indicating bypass leakage." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: 6.8, desc: "Local cavitation heating in pump chambers." },
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 1.8, desc: "Minor pressure oscillation vibration." }
        );
      } else {
        baseList.push(
          { name: "Discharge Flow", value: `${telemetry.flowRate} L/m`, shapValue: 0.5, desc: "Fluid throughput matches operating demands." },
          { name: "Discharge Pressure", value: `${telemetry.pressure} bar`, shapValue: -0.6, desc: "Pressure lines are steady." },
          { name: "Rotor Speed", value: `${telemetry.speed} RPM`, shapValue: 0.8, desc: "Drive motor running at regular load." },
          { name: "Casing Temperature", value: `${telemetry.temperature} °C`, shapValue: -1.4, desc: "Bearings and housing are well-cooled." },
          { name: "Bearing Vibration", value: `${telemetry.vibration} mm/s`, shapValue: 1.2, desc: "Nominal piston cycle vibrations." }
        );
      }
    }

    return baseList.sort((a, b) => Math.abs(b.shapValue) - Math.abs(a.shapValue));
  };

  const shapFeatures = getShapFeatures();
  const baseValue = 5.2; // E(f(x)) - Expected value of model output
  const predictionValue = telemetry.riskScore;

  // Get recommendations based on highest positive contributor
  const getActionRecommendations = () => {
    const highestContributor = shapFeatures[0];
    if (!highestContributor || highestContributor.shapValue <= 5) {
      return ["System is operating nominally. Keep existing preventive maintenance schedules."];
    }

    const name = highestContributor.name;
    if (name === "Bearing Vibration") {
      return [
        "Schedule urgent mechanical alignment checks (bearing housing offset).",
        "Inspect lubricating oil for metal filings or moisture contamination.",
        "Perform structural casing tightness checks to eliminate loose components."
      ];
    } else if (name === "Casing Temperature") {
      return [
        "Initiate coolant line flush to clear any internal pipe blocks.",
        "Verify oil viscosity matches operating limits (requires grade ISO-VG-32 or higher).",
        "Temporarily shed asset load by 15% to check if heat buildup stabilizes."
      ];
    } else if (name === "Discharge Pressure") {
      return [
        "Check anti-surge valve feedback loop calibration.",
        "Inspect downstream flow check-valves for mechanical blockages.",
        "Execute automated pressure release bypass if surge symptoms persist."
      ];
    } else if (name === "Discharge Flow") {
      return [
        "Inspect main casing seals and gasket flanges for external leaks.",
        "Recalibrate flow meters to rule out telemetry signal errors.",
        "Verify intake check-valve suction pressure to check for fluid starvation."
      ];
    } else if (name === "Rotor Speed") {
      return [
        "Check electrical supply breakers and variable frequency drive (VFD) outputs.",
        "Confirm rotor mechanical lock state before initiating motor restart.",
        "Clear high-priority system trip registers to allow manual controller release."
      ];
    }

    return ["Verify sensor telemetry links.", "Consult engineering schematics."];
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-md h-full">
      {/* SHAP Waterfall plot (2 Cols) */}
      <div className="xl:col-span-2 border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
        <div>
          <span className="text-xs uppercase tracking-wider text-industrial-status-offline font-semibold">Model Interpretability</span>
          <h2 className="text-lg font-bold font-mono text-industrial-bg-light">SHAP Feature Waterfall Chart</h2>
          <p className="text-xs text-industrial-status-offline">Deconstructs the contribution of each sensor parameter to the current anomaly risk score.</p>
        </div>

        {/* Waterfall representation */}
        <div className="my-md flex-grow flex flex-col justify-center gap-sm">
          {/* Base Value indicator */}
          <div className="flex justify-between items-center text-xs font-mono border-b border-industrial-border-dark pb-xs text-industrial-status-offline">
            <span>Base Model Prediction expectation: E[f(x)]</span>
            <span className="font-bold">{baseValue}%</span>
          </div>

          {/* List of SHAP bars */}
          <div className="flex flex-col gap-md my-sm">
            {shapFeatures.map((feat) => {
              const absVal = Math.abs(feat.shapValue);
              const pctWidth = Math.min(100, (absVal / 60) * 100);
              const isPositive = feat.shapValue >= 0;

              return (
                <div
                  key={feat.name}
                  className="flex flex-col md:flex-row md:items-center justify-between gap-sm cursor-help relative group"
                  onMouseEnter={() => setHoveredFeature(feat.name)}
                  onMouseLeave={() => setHoveredFeature(null)}
                >
                  <div className="w-40 font-mono text-xs">
                    <span className="text-industrial-bg-light font-bold">{feat.name}</span>
                    <div className="text-[10px] text-industrial-status-offline">Val: {feat.value}</div>
                  </div>

                  {/* Horizontal Bar Graphic */}
                  <div className="flex-grow bg-industrial-bg-dark h-6 rounded overflow-hidden relative border border-industrial-border-dark/40 flex items-center">
                    {/* Bar Fill */}
                    <div
                      style={{
                        width: `${pctWidth}%`,
                        marginLeft: isPositive ? "50%" : `calc(50% - ${pctWidth}%)`
                      }}
                      className={`h-full transition-all duration-500 flex items-center px-sm ${
                        isPositive
                          ? "bg-industrial-status-critical/20 border-l border-industrial-status-critical/80 text-industrial-status-critical justify-start"
                          : "bg-blue-500/20 border-r border-blue-500/80 text-blue-400 justify-end"
                      }`}
                    >
                      <span className="font-mono text-[9px] font-bold">
                        {isPositive ? `+${feat.shapValue}%` : `${feat.shapValue}%`}
                      </span>
                    </div>

                    {/* Midpoint line */}
                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-industrial-status-offline/50 z-10" />
                  </div>

                  {/* Tooltip Overlay */}
                  {hoveredFeature === feat.name && (
                    <div className="absolute left-40 right-0 top-[-35px] md:top-[-10px] bg-industrial-bg-dark border border-industrial-status-warning p-xs rounded text-[10px] font-mono z-20 shadow-xl">
                      <span className="text-industrial-status-warning font-bold uppercase">Explanation:</span> {feat.desc}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Current Risk Indicator */}
          <div className={`flex justify-between items-center text-xs font-mono border-t border-industrial-border-dark pt-xs ${
            predictionValue > 80 ? "text-industrial-status-critical font-bold" :
            predictionValue > 50 ? "text-industrial-status-warning font-bold" :
            "text-industrial-status-ok font-bold"
          }`}>
            <span>Target Anomaly Prediction output: f(x)</span>
            <span>{predictionValue}%</span>
          </div>
        </div>

        <div className="text-[10px] font-mono text-industrial-status-offline bg-industrial-bg-dark/40 border border-industrial-border-dark p-sm rounded flex items-start gap-sm">
          <Info className="w-4 h-4 text-industrial-status-warning shrink-0" />
          <span>
            Model base expectation represents nominal plant statistics. Red values increase overall risk, while blue values reflect dampening metrics keeping values sub-hazard.
          </span>
        </div>
      </div>

      {/* Beeswarm Plot & Action panel (1 Col) */}
      <div className="flex flex-col gap-md">
        {/* Beeswarm plot summary card */}
        <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-mono text-industrial-status-offline uppercase">Global Importances</span>
            <h3 className="font-bold text-sm font-mono">SHAP Summary Beeswarm</h3>
            <p className="text-[10px] text-industrial-status-offline">Statistical distribution of sensor impacts over 1,000 historical operations runs.</p>
          </div>

          {/* Beeswarm SVG plot */}
          <div className="my-md bg-industrial-bg-dark/50 p-xs border border-industrial-border-dark/60 rounded">
            <svg className="w-full h-36 overflow-visible" viewBox="0 0 200 140">
              <line x1="100" y1="10" x2="100" y2="130" stroke="#2a303c" strokeDasharray="2 2" />
              <text x="100" y="138" textAnchor="middle" className="fill-industrial-status-offline font-mono text-[7px]">0 (No Impact)</text>
              <text x="20" y="138" textAnchor="middle" className="fill-blue-400 font-mono text-[7px]">Negative SHAP</text>
              <text x="180" y="138" textAnchor="middle" className="fill-industrial-status-critical font-mono text-[7px]">Positive SHAP</text>

              {/* Feature row 1: Vibration */}
              <text x="5" y="24" className="fill-industrial-bg-light font-mono text-[8px] font-bold">Vibration</text>
              {/* Dot distribution */}
              <circle cx="102" cy="22" r="2.5" className="fill-blue-500" />
              <circle cx="106" cy="21" r="2.5" className="fill-blue-500" />
              <circle cx="112" cy="22" r="2.5" className="fill-blue-400" />
              <circle cx="120" cy="23" r="2.5" className="fill-industrial-status-warning" />
              <circle cx="140" cy="22" r="2.5" className="fill-industrial-status-critical animate-pulse" />
              <circle cx="152" cy="21" r="2.5" className="fill-industrial-status-critical" />
              <circle cx="165" cy="22" r="2.5" className="fill-industrial-status-critical" />

              {/* Feature row 2: Temperature */}
              <text x="5" y="52" className="fill-industrial-bg-light font-mono text-[8px] font-bold">Temperature</text>
              <circle cx="95" cy="50" r="2.5" className="fill-blue-500" />
              <circle cx="98" cy="49" r="2.5" className="fill-blue-400" />
              <circle cx="104" cy="50" r="2.5" className="fill-blue-400" />
              <circle cx="112" cy="51" r="2.5" className="fill-industrial-status-warning" />
              <circle cx="128" cy="50" r="2.5" className="fill-industrial-status-critical" />
              <circle cx="138" cy="50" r="2.5" className="fill-industrial-status-critical" />

              {/* Feature row 3: Flow */}
              <text x="5" y="80" className="fill-industrial-bg-light font-mono text-[8px] font-bold">Discharge Flow</text>
              <circle cx="60" cy="78" r="2.5" className="fill-industrial-status-critical" />
              <circle cx="75" cy="78" r="2.5" className="fill-industrial-status-warning" />
              <circle cx="98" cy="77" r="2.5" className="fill-blue-400" />
              <circle cx="101" cy="79" r="2.5" className="fill-blue-400" />
              <circle cx="105" cy="78" r="2.5" className="fill-blue-500" />
              <circle cx="110" cy="78" r="2.5" className="fill-blue-500" />

              {/* Feature row 4: Pressure */}
              <text x="5" y="108" className="fill-industrial-bg-light font-mono text-[8px] font-bold">Pressure</text>
              <circle cx="85" cy="106" r="2.5" className="fill-industrial-status-critical" />
              <circle cx="96" cy="105" r="2.5" className="fill-blue-400" />
              <circle cx="102" cy="107" r="2.5" className="fill-blue-400" />
              <circle cx="108" cy="106" r="2.5" className="fill-blue-500" />
              <circle cx="118" cy="105" r="2.5" className="fill-blue-500" />
            </svg>
          </div>

          <div className="flex justify-between items-center text-[7px] font-mono text-industrial-status-offline">
            <span>Dot position = SHAP impact</span>
            <span className="flex items-center gap-xs">
              Value magnitude: <span className="w-1.5 h-1.5 rounded-full bg-blue-500" /> low <span className="w-1.5 h-1.5 rounded-full bg-industrial-status-critical" /> high
            </span>
          </div>
        </div>

        {/* Action / Mitigations Panel */}
        <div className="border border-industrial-border-dark bg-industrial-panel-dark p-md rounded flex-grow flex flex-col gap-sm">
          <div className="flex items-center gap-xs">
            <ShieldAlert className="w-4 h-4 text-industrial-status-warning" />
            <h3 className="font-bold text-xs font-mono uppercase text-industrial-status-warning">Model Mitigations</h3>
          </div>
          <p className="text-[10px] text-industrial-status-offline leading-relaxed font-mono">
            AI-recommended mitigation instructions generated dynamically from the top SHAP indicators:
          </p>

          <div className="flex flex-col gap-sm mt-xs">
            {getActionRecommendations().map((rec, idx) => (
              <div
                key={idx}
                className="text-xs bg-industrial-bg-dark border-l-2 border-industrial-status-warning p-sm rounded font-mono text-industrial-bg-light flex gap-sm items-start"
              >
                <span className="text-industrial-status-warning font-bold">0{idx + 1}.</span>
                <span>{rec}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
