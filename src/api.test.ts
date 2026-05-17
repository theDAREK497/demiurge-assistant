import { describe, it, expect, beforeEach, vi } from 'vitest';
import { api } from './api';

describe('API Utils', () => {
  beforeEach(() => {
    // Reset universe ID before each test
    api.setUniverseId('');
    
    // Mock global fetch
    global.fetch = vi.fn();
  });

  it('should set and get universe ID', () => {
    api.setUniverseId('test-123');
    expect(api.getUniverseId()).toBe('test-123');
  });

  it('should format getUniverses request correctly', async () => {
    const mockResponse = [{ id: '1', name: 'Test' }];
    (global.fetch as any).mockResolvedValueOnce({
      json: () => Promise.resolve(mockResponse)
    });

    const result = await api.getUniverses();
    
    expect(global.fetch).toHaveBeenCalledWith('/api/universes');
    expect(result).toEqual(mockResponse);
  });
});
