import { apiClient } from '@/api';
import { User } from '@/types';

const MOCK_USER: User = {
  id: 'usr-001',
  username: 'Alex Mercer',
  email: 'a.mercer@iob.enterprise.internal',
  role: 'SUPER_ADMIN',
  clearanceLevel: 4,
};

/**
 * Section 8 Service Interface Mapping: UserService
 * Integrated with existing Section 7 decoupled network layer (apiClient).
 * Conformed to Section 11 Strict Shared TypeScript Layouts.
 */
export const UserService = {
  /**
   * TODO: Map organizational ACL privileges and profile claims in Phase 2.
   */
  async getProfile(): Promise<User | null> {
    try {
      return await apiClient.get<User>('/api/v1/users/profile');
    } catch {
      return null;
    }
  },
  async getCurrentUser(): Promise<User> {
    try {
      return await apiClient.get<User>('/api/v1/users/me');
    } catch {
      return MOCK_USER;
    }
  },
};

// Backwards-compatible alias for existing Section 7 repo wiring
export const userService = UserService;
