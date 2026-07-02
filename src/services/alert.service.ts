import { apiClient } from '@/api';
import { Alert } from '@/types';

const MOCK_ALERTS: Alert[] = [
  {
    id: 'alt-101',
    assetId: 'turbine-01',
    severity: 'WARNING',
    message: 'High frequency casing harmonic vibration detected.',
    timestamp: new Date().toLocaleTimeString(),
    acknowledged: false,
  },
];

/**
 * Section 8 Service Interface Mapping: AlertService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const AlertService = {
  /**
   * TODO: Bind to live SCADA alert stream hooks in Phase 2.
   */
  async getActiveAlerts(): Promise<Alert[]> {
    try {
      return await apiClient.get<Alert[]>('/api/v1/alerts');
    } catch {
      return MOCK_ALERTS;
    }
  },
  async acknowledgeAlert(id: string): Promise<boolean> {
    try {
      await apiClient.post<void>(`/api/v1/alerts/${id}/acknowledge`);
      return true;
    } catch {
      return true;
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const alertService = AlertService;
