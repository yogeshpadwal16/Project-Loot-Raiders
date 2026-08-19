/**
 * Centralized Resilient API Client connecting to web/server.py and loot_brain/dashboard_api.py.
 * Features automatic multi-target failover to ensure 100% uptime on Cloudflare Pages and custom domains.
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

const ACTIVE_TUNNEL_FALLBACK = 'https://standard-license-arabic-shaft.trycloudflare.com';

/**
 * Resilient multi-target fetch utility.
 * First tries standard relative path. If Cloudflare Edge returns 530/502/504 or network fails,
 * seamlessly fails over to the verified HTTPS backend tunnel.
 */
export async function resilientFetch(path: string, options?: RequestInit): Promise<Response> {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return fetch(path, options);
  }

  const endpoint = path.startsWith('/') ? path : `/${path}`;

  // 1. Try relative path first
  try {
    const res = await fetch(endpoint, options);
    // If not Cloudflare edge error (530/502/504), return immediately
    if (res.status !== 530 && res.status !== 502 && res.status !== 504 && res.status !== 404) {
      return res;
    }
  } catch (err) {
    // Relative fetch failed -> fallback to tunnel
  }

  // 2. Direct fallback to verified HTTPS tunnel
  const directUrl = `${ACTIVE_TUNNEL_FALLBACK}${endpoint}`;
  return fetch(directUrl, options);
}

export class ApiClient {
  private static getHeaders(): Record<string, string> {
    const token = localStorage.getItem('loot_session_token') || 'admin_session_key_default';
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };
  }

  static async fetchPublicDeals(limit = 50): Promise<DealItem[]> {
    try {
      const res = await resilientFetch(`/api/deals/public?limit=${limit}`);
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
    const res = await resilientFetch(`/api/deals/history?id=${encodeURIComponent(productId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  static async fetchStatus(): Promise<ScraperStatus> {
    const res = await resilientFetch('/api/status');
    return await res.json();
  }

  static async fetchHealth(): Promise<HealthStatus> {
    const res = await resilientFetch('/api/scraper/health');
    return await res.json();
  }

  static async fetchAnalytics(): Promise<AnalyticsMetrics> {
    const res = await resilientFetch('/api/analytics', { headers: this.getHeaders() });
    return await res.json();
  }

  static async fetchLootMapEvents(): Promise<MapEvent[]> {
    const res = await resilientFetch('/api/lootmap/events');
    return await res.json();
  }

  static async claimScratchReward(userId = 'web_user'): Promise<ScratchResult> {
    const res = await resilientFetch(`/api/rewards/scratch?user_id=${userId}`);
    return await res.json();
  }

  static async fetchBrainStatus(): Promise<BrainStatus> {
    const res = await resilientFetch('/api/v1/brain/status');
    return await res.json();
  }

  static async fetchBrainMemories(query?: string): Promise<MemoryEntry[]> {
    const path = query ? `/api/v1/brain/memories?query=${encodeURIComponent(query)}` : '/api/v1/brain/memories';
    const res = await resilientFetch(path);
    return await res.json();
  }

  static async fetchBrainPolicies(): Promise<PolicyCandidate[]> {
    const res = await resilientFetch('/api/v1/brain/learning/policies');
    return await res.json();
  }

  static async approveBrainPolicy(policyId: string): Promise<{ approved: boolean }> {
    const res = await resilientFetch(`/api/v1/brain/learning/policies/${policyId}/approve`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ approver_id: 'human_operator' })
    });
    return await res.json();
  }

  static async processBrainPipeline(payload: ProcessDealPayload): Promise<any> {
    const res = await resilientFetch('/api/v1/brain/pipeline/process', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload)
    });
    return await res.json();
  }

  static async fetchSelectors(): Promise<Record<string, SelectorMatrixItem>> {
    const res = await resilientFetch('/api/selectors', { headers: this.getHeaders() });
    return await res.json();
  }

  static async triggerManualCrawl(url: string): Promise<any> {
    const res = await resilientFetch('/api/manual/crawl', {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ url })
    });
    return await res.json();
  }
}
