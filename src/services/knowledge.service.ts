import { apiClient } from '@/api';
import { Knowledge } from '@/types';

const MOCK_GRAPH: Knowledge[] = [
  {
    nodeId: 'node-1',
    label: 'Turbine Bearing Assembly',
    properties: {
      category: 'Component',
      snippet: 'Journal bearing specification ISO-10816 threshold limits.',
    },
    edges: [
      { relationship: 'connected_to', targetId: 'node-2' },
      { relationship: 'connected_to', targetId: 'node-3' },
    ],
  },
  {
    nodeId: 'node-2',
    label: 'Harmonic Vibration Spike',
    properties: {
      category: 'FailureMode',
      snippet: 'Occurs when lubrication film degrades below 12 microns.',
    },
    edges: [
      { relationship: 'connected_to', targetId: 'node-1' },
    ],
  },
  {
    nodeId: 'node-3',
    label: 'Emergency Shutdown SOP-109',
    properties: {
      category: 'SOP',
      snippet: 'Trip fuel valve solenoid immediately upon casing temp > 90C.',
    },
    edges: [
      { relationship: 'connected_to', targetId: 'node-1' },
    ],
  },
];

/**
 * Section 8 Service Interface Mapping: KnowledgeService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const KnowledgeService = {
  /**
   * TODO: Connect Neo4j and GraphRAG contextual vector indexes in Phase 2.
   */
  async getGraphContext(): Promise<Knowledge[]> {
    try {
      return await apiClient.get<Knowledge[]>('/api/v1/knowledge/context');
    } catch {
      return MOCK_GRAPH;
    }
  },
  async getKnowledgeGraph(): Promise<Knowledge[]> {
    try {
      return await apiClient.get<Knowledge[]>('/api/v1/knowledge/graph');
    } catch {
      return MOCK_GRAPH;
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const knowledgeService = KnowledgeService;
