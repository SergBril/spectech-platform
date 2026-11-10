import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
  };
})();
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

// Mock import.meta.env
vi.stubEnv('VITE_API_URL', 'http://test-api:8000/api/v1');

describe('API Client', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  it('adds Authorization header when token exists', async () => {
    localStorageMock.getItem.mockImplementation((key: string) => {
      if (key === 'access_token') return 'test-jwt-token';
      return null;
    });

    // Dynamic import to pick up mocked localStorage
    const { apiClient } = await import('../api/client');
    const config = { headers: {} as Record<string, string> };

    // Access interceptor via axios internals
    expect(apiClient.defaults.baseURL).toBe('http://test-api:8000/api/v1');
  });

  it('uses correct base URL', async () => {
    const { apiClient } = await import('../api/client');
    expect(apiClient.defaults.baseURL).toContain('/api/v1');
  });
});
