/**
 * API Client for HybridFlow Backend
 */

import { authClient } from '@/lib/auth-client';
import type {
  User,
  Tenant,
  TenantMembership,
  Session,
  Message,
  PaginatedResponse,
  SessionsQueryParams,
  MessagesQueryParams,
} from '@/types/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClientError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  let token: string | null = null;
  try {
    const result = await authClient.getSession();
    token = result.data?.session?.token ?? null;
  } catch {
    // No active session
  }

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 - Unauthorized (throw only; let useRequireAuth handle redirect)
  if (response.status === 401) {
    throw new ApiClientError('Unauthorized', 401);
  }

  // Handle other errors
  if (!response.ok) {
    let detail = 'Request failed';
    try {
      const errorBody = await response.json();
      detail = errorBody.detail || JSON.stringify(errorBody);
    } catch {
      detail = response.statusText;
    }
    throw new ApiClientError(detail, response.status, detail);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

// Tenants API
export const tenantsApi = {
  list: async (): Promise<TenantMembership[]> => {
    // Backend returns flat tenant objects, we need to transform to TenantMembership format
    const response = await apiClient<{ tenants: (Tenant | TenantMembership)[] }>('/api/tenants');
    const tenants = response.tenants || [];

    // Transform to TenantMembership format if backend returns flat Tenant objects
    return tenants.map((item) => {
      // Check if it's already in TenantMembership format (has tenant_id and tenant)
      if ('tenant_id' in item && 'tenant' in item) {
        return item as TenantMembership;
      }
      // It's a flat Tenant object, transform it
      const tenant = item as Tenant;
      return {
        tenant_id: tenant.id,
        role: 'owner' as const, // Default role since backend doesn't return it
        tenant: tenant,
      };
    });
  },

  get: async (tenantId: number): Promise<Tenant> => {
    return apiClient<Tenant>(`/api/tenants/${tenantId}`);
  },

  create: async (data: {
    instance_name: string;
    evo_server_url: string;
    evo_api_key?: string;
    system_prompt?: string;
  }): Promise<Tenant> => {
    return apiClient<Tenant>('/api/tenants', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  update: async (
    tenantId: number,
    data: {
      evo_server_url?: string;
      evo_api_key?: string;
      system_prompt?: string;
    }
  ): Promise<Tenant> => {
    return apiClient<Tenant>(`/api/tenants/${tenantId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  generatePrompt: async (description: string): Promise<{ system_prompt: string }> => {
    return apiClient<{ system_prompt: string }>('/api/generate-prompt', {
      method: 'POST',
      body: JSON.stringify({ description }),
    });
  },
};

// Sessions API
export const sessionsApi = {
  list: async (params: SessionsQueryParams): Promise<PaginatedResponse<Session>> => {
    const searchParams = new URLSearchParams();
    searchParams.set('tenant_id', params.tenant_id.toString());
    if (params.state) searchParams.set('state', params.state);
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.per_page) searchParams.set('per_page', params.per_page.toString());
    if (params.search) searchParams.set('search', params.search);

    // Backend returns { sessions, total, page, limit }
    const response = await apiClient<{
      sessions: Session[];
      total: number;
      page: number;
      limit: number;
    }>(`/api/sessions?${searchParams}`);

    return {
      items: response.sessions || [],
      total: response.total || 0,
      page: response.page || 1,
      per_page: response.limit || 10,
      pages: Math.ceil((response.total || 0) / (response.limit || 10)) || 1,
    };
  },

  get: async (sessionId: number, tenantId: number): Promise<Session> => {
    return apiClient<Session>(`/api/sessions/${sessionId}?tenant_id=${tenantId}`);
  },

  pause: async (sessionId: number, tenantId: number): Promise<{ ok: boolean; paused: boolean; session_id: number }> => {
    return apiClient<{ ok: boolean; paused: boolean; session_id: number }>(`/api/sessions/${sessionId}/pause`, {
      method: 'POST',
      body: JSON.stringify({ tenant_id: tenantId }),
    });
  },

  resume: async (sessionId: number, tenantId: number): Promise<{ ok: boolean; resumed: boolean; session_id: number }> => {
    return apiClient<{ ok: boolean; resumed: boolean; session_id: number }>(`/api/sessions/${sessionId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ tenant_id: tenantId }),
    });
  },
};

// Messages/Events API
export const eventsApi = {
  list: async (params: MessagesQueryParams): Promise<Message[]> => {
    const searchParams = new URLSearchParams();
    searchParams.set('tenant_id', params.tenant_id.toString());
    if (params.chat_id) searchParams.set('chat_id', params.chat_id);
    if (params.limit) searchParams.set('limit', params.limit.toString());
    if (params.offset) searchParams.set('offset', params.offset.toString());

    // Backend returns { events, limit }
    const response = await apiClient<{ events: Message[]; limit: number }>(`/api/events?${searchParams}`);
    return response.events || [];
  },
};

// Instances API
export const instancesApi = {
  list: async (tenantId: number): Promise<Tenant[]> => {
    // Backend returns { instances }
    const response = await apiClient<{ instances: Tenant[] }>(`/api/instances?tenant_id=${tenantId}`);
    return response.instances || [];
  },

  get: async (instanceName: string, tenantId: number): Promise<Tenant> => {
    return apiClient<Tenant>(`/api/instances/${instanceName}?tenant_id=${tenantId}`);
  },

  testWebhook: async (instanceName: string, tenantId: number): Promise<{ success: boolean; message: string }> => {
    return apiClient<{ success: boolean; message: string }>(
      `/api/instances/${instanceName}/test-webhook`,
      {
        method: 'POST',
        body: JSON.stringify({ tenant_id: tenantId }),
      }
    );
  },
};

// Health API
export const healthApi = {
  check: async (): Promise<{ status: string; database: string }> => {
    return apiClient<{ status: string; database: string }>('/health');
  },
};

// Privacy / GDPR API
export interface DataExportResponse {
  export_date: string;
  data_controller: string;
  user_profile: {
    id: string;
    email: string;
    display_name?: string;
    created_at: string;
  };
  tenant_memberships: Array<{ tenant_id: number; role: string }>;
  tenants: Array<{ id: number; instance_name: string; created_at: string }>;
  sessions: Array<{
    id: number;
    chat_id_masked: string;
    chat_id_hash: string;
    is_paused: boolean;
    created_at: string;
  }>;
  messages: Array<{
    id: number;
    chat_id_masked: string;
    from_me: boolean;
    text?: string;
    created_at: string;
  }>;
}

export interface DataDeletionResponse {
  ok: boolean;
  message: string;
  deleted: {
    messages_deleted: number;
    sessions_deleted: number;
    tenants_deleted: number;
    memberships_deleted: number;
  };
}

export const privacyApi = {
  /**
   * Export all user data (GDPR DSAR)
   */
  exportData: async (): Promise<DataExportResponse> => {
    return apiClient<DataExportResponse>('/api/privacy/export');
  },

  /**
   * Delete all user data (GDPR Right to Erasure)
   * WARNING: This is irreversible!
   */
  deleteAllData: async (confirm: boolean = false): Promise<DataDeletionResponse> => {
    return apiClient<DataDeletionResponse>(`/api/privacy/data?confirm=${confirm}`, {
      method: 'DELETE',
    });
  },

  /**
   * Delete messages for a specific chat
   */
  deleteChatMessages: async (
    chatId: string,
    tenantId: number,
    confirm: boolean = false
  ): Promise<{ ok: boolean; messages_deleted: number }> => {
    return apiClient<{ ok: boolean; messages_deleted: number }>(
      `/api/privacy/messages/${encodeURIComponent(chatId)}?tenant_id=${tenantId}&confirm=${confirm}`,
      { method: 'DELETE' }
    );
  },
};

// WhatsApp Connection API (QR Code Flow)
export interface WhatsAppConnectResponse {
  ok: boolean;
  instance_name: string;
  tenant_id: number;
  qr_code?: string;
  pairing_code?: string;
  message?: string;
}

export interface WhatsAppQRCodeResponse {
  ok: boolean;
  instance_name: string;
  qr_code?: string;
  pairing_code?: string;
}

export interface WhatsAppConnectionStatus {
  ok: boolean;
  instance_name: string;
  connected: boolean;
  state: 'open' | 'connecting' | 'close' | 'unknown';
}

export const whatsappApi = {
  /**
   * Create a new WhatsApp connection and get QR code for scanning
   */
  connect: async (data: {
    instance_name: string;
    system_prompt?: string;
  }): Promise<WhatsAppConnectResponse> => {
    return apiClient<WhatsAppConnectResponse>('/api/whatsapp/connect', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Get or refresh QR code for an instance
   */
  getQRCode: async (instanceName: string): Promise<WhatsAppQRCodeResponse> => {
    return apiClient<WhatsAppQRCodeResponse>(`/api/whatsapp/qr-code/${instanceName}`);
  },

  /**
   * Check connection status (poll this after showing QR code)
   */
  getConnectionStatus: async (instanceName: string): Promise<WhatsAppConnectionStatus> => {
    return apiClient<WhatsAppConnectionStatus>(`/api/whatsapp/connection-status/${instanceName}`);
  },

  /**
   * Delete a WhatsApp connection
   */
  deleteInstance: async (instanceName: string): Promise<{ ok: boolean; deleted: boolean }> => {
    return apiClient<{ ok: boolean; deleted: boolean }>(`/api/whatsapp/instance/${instanceName}`, {
      method: 'DELETE',
    });
  },
};

export { ApiClientError };

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) return error.detail ?? error.message;
  if (error instanceof Error) return error.message;
  return 'Something went wrong';
}
