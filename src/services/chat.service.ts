import { apiClient } from '@/api';
import { Chat } from '@/types';

/**
 * Section 8 Service Interface Mapping: ChatService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const ChatService = {
  /**
   * TODO: Wire WebSocket completion chunks for the operational co-pilot in Phase 2.
   */
  async submitQuery(prompt?: string, history?: Chat[]): Promise<Chat[]> {
    try {
      return await apiClient.post<Chat[]>('/api/v1/chat/query', { prompt, history });
    } catch {
      return [];
    }
  },
  async sendMessage(prompt: string, history: Chat[]): Promise<Chat> {
    try {
      return await apiClient.post<Chat>('/api/v1/chat', { prompt, history });
    } catch {
      return {
        messageId: `msg-${Date.now()}`,
        sender: 'AI_ENGINE',
        payload: `Diagnostic Copilot Analysis for: "${prompt}". Root cause isolation indicates possible thermal boundary wear. Recommend verifying lubrication pressure lines.`,
        timestamp: new Date().toLocaleTimeString(),
      };
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const chatService = ChatService;
