import { apiClient } from '@/api';
import { Prediction } from '@/types';

const MOCK_PREDICTIONS: Prediction[] = [
  {
    id: 'pred-shap-01',
    assetId: 'turbine-01',
    remainingUsefulLifeDays: 45,
    failureProbability: 0.12,
    inferredFaultMechanism: 'Bearing Casing Degradation',
  },
  {
    id: 'pred-rag-02',
    assetId: 'compressor-02',
    remainingUsefulLifeDays: 82,
    failureProbability: 0.04,
    inferredFaultMechanism: 'Lubrication Film Failure',
  },
];

/**
 * Section 8 Service Interface Mapping: PredictionService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const PredictionService = {
  /**
   * TODO: Connect real-time SHAP/RUL model inference arrays in Phase 2.
   */
  async getPredictions(): Promise<Prediction[]> {
    try {
      return await apiClient.get<Prediction[]>('/api/v1/predictions');
    } catch {
      return MOCK_PREDICTIONS;
    }
  },
  async getModels(): Promise<Prediction[]> {
    try {
      return await apiClient.get<Prediction[]>('/api/v1/predictions/models');
    } catch {
      return MOCK_PREDICTIONS;
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const predictionService = PredictionService;
