/**
 * Centralized API Client connecting to web/server.py and loot_brain/dashboard_api.py.
 * Supports token auth, fallback mock states, and error handling.
 */

import {
  DealItem,
  PriceHistoryResponse,
  ScraperStatus,
  HealthStatus,
  AnalyticsMetrics,
  MapEvent,
  ScratchResult,
  BrainStatus,
  MemoryEntry,
  PolicyCandidate,
  SelectorMatrixItem,
  ProcessDealPayload
} from '../types/api';

const API_BASE = '';

export class ApiClient {
  private static getHeaders(): Record<string, string> {
    const token = localStorage.getItem('DASHBOARD_SESSION_TOKEN') || 'admin_session_key_default';
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  }

  static async fetchPublicDeals(limit = 50): Promise<DealItem[]> {
    try {
      const res = await fetch(`${API_BASE}/api/deals/public?limit=${limit}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn('Live API fetch failed, trying static snapshot deals_history.json:', err);
      try {
        const snapRes = await fetch('./deals_history.json');
        if (snapRes.ok) {
          return await snapRes.json();
        }
      } catch (snapErr) {
        console.warn('Static snapshot fallback failed:', snapErr);
      }
      throw err;
    }
  }

  static async fetchPriceHistory(productId: string): Promise<PriceHistoryResponse> {
    const res = await fetch(`${API_BASE}/api/deals/history?id=${productId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  static async fetchStatus(): Promise<ScraperStatus> {
    const res = await fetch(`${API_BASE}/api/status`);
    return await res.json();
  }

  static async fetchHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/api/scraper/health`);
    return await res.json();
  }

  static async fetchAnalytics(): Promise<AnalyticsMetrics> {
    const res = await fetch(`${API_BASE}/api/analytics`, { headers: this.getHeaders() });
    return await res.json();
  }

  static async fetchLootMapEvents(): Promise<MapEvent[]> {
    const res = await fetch(`${API_BASE}/api/lootmap/events`);
    return await res.json();
  }

  static async claimScratchReward(userId = 'web_user'): Promise<ScratchResult> {
    const res = await fetch(`${API_BASE}/api/rewards/scratch?user_id=${userId}`);
    return await res.json();
  }

  static async fetchBrainStatus(): Promise<BrainStatus> {
    const res = await fetch(`${API_BASE}/api/v1/brain/status`);
    return await res.json();
  }

  static async fetchBrainMemories(query?: string): Promise<MemoryEntry[]> {
    const url = query ? `${API_BASE}/api/v1/brain/memories?query=${encodeURIComponent(query)}` : `${API_BASE}/api/v1/brain/memories`;
    const res = await fetch(url);
    return await res.json();
  }

  static async fetchBrainPolicies(): Promise<PolicyCandidate[]> {
    const res = await fetch(`${API_BASE}/api/v1/brain/learning/policies`);
    return await res.json();
  }

  static async approveBrainPolicy(policyId: string): Promise<{ approved: boolean }> {
    const res = await fetch(`${API_BASE}/api/v1/brain/learning/policies/${policyId}/approve`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ approver_id: 'human_operator' })
    });
    return await res.json();
  }

  static async processBrainPipeline(payload: ProcessDealPayload): Promise<any> {
    const res = await fetch(`${API_BASE}/api/v1/brain/pipeline/process`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return await res.json();
  }

  static async fetchSelectors(): Promise<Record<string, SelectorMatrixItem>> {
    const res = await fetch(`${API_BASE}/api/selectors`, { headers: this.getHeaders() });
    return await res.json();
  }

  static async triggerManualCrawl(url: string): Promise<any> {
    const res = await fetch(`${API_BASE}/api/manual/crawl`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ url })
    });
    return await res.json();
  }
}
