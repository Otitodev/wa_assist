// API Types for Whaply Frontend

export interface User {
  id: string;
  email: string;
  name: string;           // BetterAuth primary display name
  display_name?: string;  // optional, kept for compatibility
  emailVerified: boolean;
  createdAt: string;
}

export interface Tenant {
  id: number;
  instance_name: string;
  evo_server_url: string;
  evo_api_key?: string;
  llm_provider?: string;
  system_prompt?: string;
  created_at: string;
  updated_at?: string;
}

export interface TenantMembership {
  tenant_id: number;
  role: 'owner' | 'admin' | 'member';
  tenant: Tenant;
}

export interface Session {
  id: number;
  tenant_id: number;
  chat_id: string;
  is_paused: boolean;
  pause_reason: string | null;
  last_message_at: string;
  last_human_at: string | null;
  created_at: string;
  last_message_text?: string | null;
}

export interface Message {
  id: number;
  tenant_id: number;
  chat_id: string;
  message_id: string;
  from_me: boolean;
  message_type: string;
  text: string | null;
  raw: Record<string, unknown>;
  created_at: string;
}

export interface Instance {
  instance_name: string;
  evo_server_url: string;
  status?: 'connected' | 'disconnected' | 'unknown';
  last_seen?: string;
}

export interface ProcessedEvent {
  id: number;
  tenant_id: number;
  message_id: string;
  event_type: string;
  action_taken: string;
  created_at: string;
}

// API Response wrappers
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface Plan {
  id: number;
  name: 'free' | 'starter' | 'growth' | 'agency';
  display_name: string;
  price_usd: number;
  price_ngn: number;
  price_usd_annual: number;
  price_ngn_annual: number;
  max_instances: number;
  max_conversations_per_month: number; // -1 = unlimited
  features: {
    typing_indicator?: boolean;
    media_processing?: boolean;
    context_memory?: boolean;
    analytics?: boolean;
    white_label?: boolean;
    priority_support?: boolean;
  };
}

export interface Subscription {
  plan_name: string;
  plan_display_name: string;
  status: 'active' | 'paused' | 'cancelled' | 'past_due';
  billing_cycle: 'monthly' | 'annual';
  currency: 'USD' | 'NGN';
  processor: 'free' | 'paystack' | 'lemonsqueezy' | 'flutterwave';
  max_instances: number;
  max_conversations_per_month: number; // -1 = unlimited
  conversations_used: number;
  conversations_remaining: number;     // -1 = unlimited
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  features: Plan['features'];
}

export interface SessionsQueryParams {
  tenant_id: number;
  state?: 'active' | 'paused' | 'all';
  page?: number;
  per_page?: number;
  search?: string;
}

export interface MessagesQueryParams {
  tenant_id: number;
  chat_id?: string;
  limit?: number;
  offset?: number;
}
