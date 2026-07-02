"use client";

import React, { createContext, useContext, useState, useEffect, useRef } from "react";

export type AssetStatus = "ok" | "warning" | "critical" | "offline";

export interface TelemetryReading {
  timestamp: string;
  speed: number;       // RPM
  torque: number;      // Nm
  temperature: number; // °C
  vibration: number;   // mm/s
  flowRate: number;    // L/min
  pressure: number;    // bar
  load: number;        // kW
  riskScore: number;   // Anomaly score 0 - 100%
  status: AssetStatus;
}

export interface Asset {
  id: string;
  name: string;
  type: string;
  status: AssetStatus;
  telemetry: TelemetryReading;
  history: TelemetryReading[];
}

interface TelemetryContextType {
  assets: Asset[];
  selectedAssetId: string;
  setSelectedAssetId: (id: string) => void;
  wsStatus: "connecting" | "connected" | "disconnected" | "offline-fallback";
  injectAnomaly: (anomalyType: string) => void;
  clearAnomalies: () => void;
  activeAnomaly: string | null;
  features: {
    shap: boolean;
    graphRag: boolean;
    digitalTwin: boolean;
  };
}

const TelemetryContext = createContext<TelemetryContextType | undefined>(undefined);

const INITIAL_READING = (assetId: string): TelemetryReading => {
  const isTurbine = assetId.includes("turbine");
  const isCompressor = assetId.includes("compressor");
  
  return {
    timestamp: new Date().toLocaleTimeString(),
    speed: isTurbine ? 3000 : isCompressor ? 4500 : 1500,
    torque: isTurbine ? 850 : isCompressor ? 400 : 1200,
    temperature: 65.4,
    vibration: 1.8,
    flowRate: isTurbine ? 220 : isCompressor ? 140 : 500,
    pressure: isTurbine ? 12.5 : isCompressor ? 45.0 : 8.2,
    load: isTurbine ? 250 : isCompressor ? 180 : 190,
    riskScore: 4.5,
    status: "ok"
  };
};

const INITIAL_ASSETS: Asset[] = [
  {
    id: "turbine-01",
    name: "Gas Turbine G-101",
    type: "Turbine",
    status: "ok",
    telemetry: INITIAL_READING("turbine-01"),
    history: Array.from({ length: 20 }, (_, i) => {
      const reading = INITIAL_READING("turbine-01");
      const d = new Date();
      d.setSeconds(d.getSeconds() - (20 - i) * 2);
      reading.timestamp = d.toLocaleTimeString();
      return reading;
    })
  },
  {
    id: "compressor-02",
    name: "Centrifugal Compressor C-204",
    type: "Compressor",
    status: "ok",
    telemetry: INITIAL_READING("compressor-02"),
    history: Array.from({ length: 20 }, (_, i) => {
      const reading = INITIAL_READING("compressor-02");
      const d = new Date();
      d.setSeconds(d.getSeconds() - (20 - i) * 2);
      reading.timestamp = d.toLocaleTimeString();
      return reading;
    })
  },
  {
    id: "pump-03",
    name: "Reciprocating Pump P-302",
    type: "Pump",
    status: "ok",
    telemetry: INITIAL_READING("pump-03"),
    history: Array.from({ length: 20 }, (_, i) => {
      const reading = INITIAL_READING("pump-03");
      const d = new Date();
      d.setSeconds(d.getSeconds() - (20 - i) * 2);
      reading.timestamp = d.toLocaleTimeString();
      return reading;
    })
  }
];

export const TelemetryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assets, setAssets] = useState<Asset[]>(INITIAL_ASSETS);
  const [selectedAssetId, setSelectedAssetId] = useState<string>("turbine-01");
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected" | "offline-fallback">("connecting");
  const [activeAnomaly, setActiveAnomaly] = useState<string | null>(null);

  // Read environment variable feature flags with appropriate defaults
  const [features] = useState({
    shap: process.env.NEXT_PUBLIC_ENABLE_SHAP_EXPLAINABILITY !== "false",
    graphRag: process.env.NEXT_PUBLIC_ENABLE_GRAPH_RAG !== "false",
    digitalTwin: process.env.NEXT_PUBLIC_ENABLE_DIGITAL_TWIN_STREAMING !== "false"
  });

  const wsRef = useRef<WebSocket | null>(null);
  const simulationIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // WebSocket Connection Attempt (Mock wss domain will fail, triggering fallback)
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "wss://stream.iob.enterprise.internal/v1";
    console.log(`[Telemetry] Attempting connections to telemetry endpoint: ${wsUrl}`);
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log("[Telemetry] Connected to enterprise WS stream.");
        setWsStatus("connected");
      };

      wsRef.current.onerror = () => {
        console.warn("[Telemetry] WebSocket connection failed. Using high-fidelity simulator fallback.");
        setWsStatus("offline-fallback");
      };

      wsRef.current.onclose = () => {
        if (wsStatus === "connecting") {
          setWsStatus("offline-fallback");
        } else if (wsStatus !== "offline-fallback") {
          setWsStatus("disconnected");
        }
      };
    } catch (e) {
      console.warn("[Telemetry] Could not construct WebSocket. Fallback initiated.");
      setWsStatus("offline-fallback");
    }

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Telemetry Simulation Hook
  useEffect(() => {
    // Only run simulator if we are on offline-fallback or disconnected
    if (wsStatus !== "offline-fallback" && wsStatus !== "disconnected" && wsStatus !== "connecting") return;

    simulationIntervalRef.current = setInterval(() => {
      setAssets((prevAssets) =>
        prevAssets.map((asset) => {
          // Generate realistic noise
          const noise = (min: number, max: number) => Math.random() * (max - min) + min;
          const currentReading = asset.telemetry;
          
          let speed = currentReading.speed;
          let torque = currentReading.torque;
          let temperature = currentReading.temperature;
          let vibration = currentReading.vibration;
          let flowRate = currentReading.flowRate;
          let pressure = currentReading.pressure;
          let load = currentReading.load;
          let riskScore = currentReading.riskScore;
          let status: AssetStatus = "ok";

          const isTurbine = asset.id.includes("turbine");
          const isCompressor = asset.id.includes("compressor");

          // Nominal fluctuation calculations
          if (isTurbine) {
            speed = 3000 + noise(-15, 15);
            torque = 850 + noise(-8, 8);
            temperature = 65.4 + noise(-0.4, 0.4);
            vibration = 1.8 + noise(-0.1, 0.1);
            flowRate = 220 + noise(-2, 2);
            pressure = 12.5 + noise(-0.15, 0.15);
            load = 250 + noise(-3, 3);
            riskScore = 4.0 + noise(-0.5, 0.5);
          } else if (isCompressor) {
            speed = 4500 + noise(-20, 20);
            torque = 400 + noise(-5, 5);
            temperature = 74.2 + noise(-0.6, 0.6);
            vibration = 2.1 + noise(-0.15, 0.15);
            flowRate = 140 + noise(-1.5, 1.5);
            pressure = 45.0 + noise(-0.4, 0.4);
            load = 180 + noise(-2, 2);
            riskScore = 5.2 + noise(-0.6, 0.6);
          } else { // Pump
            speed = 1500 + noise(-10, 10);
            torque = 1200 + noise(-12, 12);
            temperature = 52.8 + noise(-0.3, 0.3);
            vibration = 2.8 + noise(-0.2, 0.2);
            flowRate = 500 + noise(-5, 5);
            pressure = 8.2 + noise(-0.1, 0.1);
            load = 190 + noise(-2.5, 2.5);
            riskScore = 6.8 + noise(-0.7, 0.7);
          }

          // Apply injected anomalies (Targeting specific assets for clarity)
          if (activeAnomaly && asset.id === selectedAssetId) {
            if (activeAnomaly === "bearing-wear" && isTurbine) {
              // Spike bearing vibration and temperature
              vibration = 5.2 + noise(-0.3, 0.3);
              temperature = 88.5 + noise(-0.8, 0.8);
              riskScore = 68.2 + noise(-2, 2);
              status = "warning";
            } else if (activeAnomaly === "compressor-surge" && isCompressor) {
              // Massive pressure drop, vibration spike, sudden speed fluctuation
              vibration = 8.6 + noise(-0.6, 0.6);
              pressure = 24.5 + noise(-1.5, 1.5);
              speed = 3800 + noise(-100, 100);
              temperature = 94.1 + noise(-1.2, 1.2);
              riskScore = 92.4 + noise(-1, 1);
              status = "critical";
            } else if (activeAnomaly === "leakage" && asset.id.includes("pump")) {
              // Flow rate drop, pressure drop, speed remains constant
              flowRate = 310 + noise(-8, 8);
              pressure = 5.1 + noise(-0.3, 0.3);
              temperature = 58.2 + noise(-0.5, 0.5);
              riskScore = 72.8 + noise(-2, 2);
              status = "warning";
            } else if (activeAnomaly === "electrical-trip") {
              // Rapid system-wide deceleration and shutdown (Critical state)
              speed = Math.max(0, currentReading.speed - 350);
              torque = Math.max(0, currentReading.torque - 80);
              load = Math.max(0, currentReading.load - 20);
              vibration = speed > 100 ? 6.4 + noise(-0.4, 0.4) : 0.2;
              pressure = Math.max(0, currentReading.pressure - 2);
              riskScore = 98.5;
              status = "critical";
            }
          }

          // Clean up risk clamp
          riskScore = Math.max(0, Math.min(100, riskScore));

          // Auto-classify status based on riskScore thresholds if not set explicitly
          if (status === "ok") {
            if (riskScore > 80) status = "critical";
            else if (riskScore > 50) status = "warning";
          }

          const newReading: TelemetryReading = {
            timestamp: new Date().toLocaleTimeString(),
            speed: Math.round(speed * 10) / 10,
            torque: Math.round(torque * 10) / 10,
            temperature: Math.round(temperature * 10) / 10,
            vibration: Math.round(vibration * 100) / 100,
            flowRate: Math.round(flowRate * 10) / 10,
            pressure: Math.round(pressure * 10) / 10,
            load: Math.round(load * 10) / 10,
            riskScore: Math.round(riskScore * 10) / 10,
            status
          };

          // Slide historical buffer
          const newHistory = [...asset.history.slice(1), newReading];

          return {
            ...asset,
            status,
            telemetry: newReading,
            history: newHistory
          };
        })
      );
    }, 1500);

    return () => {
      if (simulationIntervalRef.current) clearInterval(simulationIntervalRef.current);
    };
  }, [wsStatus, activeAnomaly, selectedAssetId]);

  const injectAnomaly = (anomalyType: string) => {
    setActiveAnomaly(anomalyType);
  };

  const clearAnomalies = () => {
    setActiveAnomaly(null);
  };

  return (
    <TelemetryContext.Provider
      value={{
        assets,
        selectedAssetId,
        setSelectedAssetId,
        wsStatus,
        injectAnomaly,
        clearAnomalies,
        activeAnomaly,
        features
      }}
    >
      {children}
    </TelemetryContext.Provider>
  );
};

export const useTelemetry = () => {
  const context = useContext(TelemetryContext);
  if (context === undefined) {
    throw new Error("useTelemetry must be used within a TelemetryProvider");
  }
  return context;
};
