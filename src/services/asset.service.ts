import { apiClient } from '@/api';
import { Asset } from '@/types';

/**
 * Section 8 Service Interface Mapping: AssetService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const AssetService = {
  /**
   * TODO: Bind to API endpoint /api/v1/assets during Phase 2.
   */
  async getAssets(): Promise<Asset[]> {
    try {
      return await apiClient.get<Asset[]>('/api/v1/assets');
    } catch {
      return [];
    }
  },
  async getAssetById(id: string): Promise<Asset | null> {
    try {
      return await apiClient.get<Asset>(`/api/v1/assets/${id}`);
    } catch {
      return null;
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const assetService = AssetService;
