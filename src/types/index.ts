export type Role = 'SUPER_ADMIN' | 'PLANT_MANAGER' | 'CONTROL_ROOM_OPERATOR' | 'MAINTENANCE_ENGINEER';

export interface User {
  id: string;
  username: string;
  email: string;
  role: Role;
  clearanceLevel: number;
}

export interface Asset {
  id: string;
  name: string;
  type: string;
  status: 'OPERATIONAL' | 'DEGRADED' | 'CRITICAL' | 'OFFLINE';
  parentId: string | null;
}

export interface Alert {
  id: string;
  assetId: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL' | 'FATAL';
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface Prediction {
  id: string;
  assetId: string;
  remainingUsefulLifeDays: number;
  failureProbability: number;
  inferredFaultMechanism: string;
}

export interface Knowledge {
  nodeId: string;
  label: string;
  properties: Record<string, unknown>;
  edges: Array<{ relationship: string; targetId: string }>;
}

export interface Chat {
  messageId: string;
  sender: 'OPERATOR' | 'AI_ENGINE';
  payload: string;
  timestamp: string;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}
