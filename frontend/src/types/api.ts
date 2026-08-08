/**
 * TypeScript Data Models matching existing Python Backend API Contracts (web/server.py & loot_brain/dashboard_api.py).
 */

export interface DealItem {
  id: string;
  title: string;
  price: number;
  mrp: number;
  discount: number;
  platform: 'amazon' | 'flipkart' | 'myntra' | 'snapdeal' | 'generic' | string;
  image_url: string;
  url: string;
  deal_score: number;
  is_verified_low: boolean;
  coupon_code?: string;
  bank_offer?: string;
  affiliate_url?: string;
  created_at?: string;
  timestamp?: number;
  telegram_message_id?: number;
}

export interface PriceHistoryPoint {
  price: number;
  mrp?: number;
  discount?: number;
  timestamp: number;
}

export interface PriceHistoryResponse {
  product_id: string;
  title: string;
  platform: string;
  current_price: number;
  mrp: number;
  deal_score: number;
  is_verified_low: boolean;
  history: PriceHistoryPoint[];
}

export interface ScraperStatus {
  status: string;
  uptime_seconds?: number;
  version?: string;
  active_scrapers?: number;
  deals_count?: number;
}

export interface HealthStatus {
  status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY' | string;
  db_status: string;
  scraper_loop_alive: boolean;
  telegram_bot_alive: boolean;
  redis_queue_depth?: number;
}

export interface AnalyticsMetrics {
  total_deals: number;
  active_platforms: number;
  total_clicks: number;
  verified_all_time_lows: number;
  avg_discount: number;
}

export interface MapEvent {
  city?: string;
  name?: string;
  action?: string;
  lat?: number;
  lng?: number;
  timestamp?: number;
}

export interface ScratchResult {
  status: 'success' | 'error';
  points_won?: number;
  new_total?: number;
  message?: string;
  error?: string;
}

export interface BrainAgent {
  agent_id: string;
  name: string;
  role: string;
  capabilities: string[];
  max_privilege_scope: string;
  state: string;
}

export interface BrainStatus {
  status: 'ONLINE' | 'STANDALONE' | string;
  version: string;
  registered_agents_count: number;
  agents: BrainAgent[];
  active_memories_count: number;
  archived_memories_count: number;
  pending_policy_proposals_count: number;
}

export interface MemoryEntry {
  memory_id: string;
  category: string;
  memory_type: string;
  title: string;
  content: string;
  confidence: number;
  scope: string;
  agent_id: string;
  platform?: string;
  usefulness_score: number;
  created_at: number;
}

export interface PolicyCandidate {
  policy_id: string;
  proposed_by: string;
  description: string;
  target_component: string;
  approved: boolean;
  created_at: number;
}

export interface SelectorMatrixItem {
  platform: string;
  url: string;
  card_selector: string;
  title_selector: string;
  link_selector: string;
  image_selector: string;
}

export interface ProcessDealPayload {
  title: string;
  original_price: number;
  deal_price: number;
  merchant?: string;
  url: string;
  in_stock?: boolean;
  coupon_code?: string;
}
