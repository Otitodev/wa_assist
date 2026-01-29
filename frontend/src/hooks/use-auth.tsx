'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import { authApi } from '@/lib/api';
import type { User, TenantMembership } from '@/types/api';
import { tenantsApi } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  tenants: TenantMembership[];
  activeTenant: TenantMembership | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  setActiveTenant: (tenant: TenantMembership) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Helper to safely get tenant_id as string
function getTenantIdString(tenant: TenantMembership | undefined | null): string | null {
  if (!tenant) return null;
  if (tenant.tenant_id !== undefined && tenant.tenant_id !== null) {
    return tenant.tenant_id.toString();
  }
  return null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenants, setTenants] = useState<TenantMembership[]>([]);
  const [activeTenant, setActiveTenantState] = useState<TenantMembership | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load user and tenants on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        // Fetch user
        const { user: currentUser } = await authApi.me();
        setUser(currentUser);

        // Fetch tenants
        const tenantList = await tenantsApi.list();
        const validTenants = Array.isArray(tenantList) ? tenantList : [];
        setTenants(validTenants);

        // Restore active tenant from localStorage or use first
        const savedTenantId = localStorage.getItem('active_tenant_id');
        if (savedTenantId && validTenants.length > 0) {
          const savedTenant = validTenants.find(
            (t) => getTenantIdString(t) === savedTenantId
          );
          if (savedTenant) {
            setActiveTenantState(savedTenant);
          } else {
            setActiveTenantState(validTenants[0]);
          }
        } else if (validTenants.length > 0) {
          setActiveTenantState(validTenants[0]);
        }
      } catch (error) {
        // Token invalid - clear storage
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('active_tenant_id');
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login({ email, password });
    setUser(response.user);

    // Fetch tenants after login
    const tenantList = await tenantsApi.list();
    const validTenants = Array.isArray(tenantList) ? tenantList : [];
    setTenants(validTenants);

    if (validTenants.length > 0) {
      const firstTenant = validTenants[0];
      setActiveTenantState(firstTenant);
      const tenantId = getTenantIdString(firstTenant);
      if (tenantId) {
        localStorage.setItem('active_tenant_id', tenantId);
      }
    }

    router.push('/dashboard');
  }, [router]);

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const response = await authApi.register({ email, password, display_name: displayName });
    setUser(response.user);

    // New users may not have tenants yet
    try {
      const tenantList = await tenantsApi.list();
      const validTenants = Array.isArray(tenantList) ? tenantList : [];
      setTenants(validTenants);
      if (validTenants.length > 0) {
        const firstTenant = validTenants[0];
        setActiveTenantState(firstTenant);
        const tenantId = getTenantIdString(firstTenant);
        if (tenantId) {
          localStorage.setItem('active_tenant_id', tenantId);
        }
      }
    } catch {
      // Ignore - new user has no tenants
    }

    router.push('/dashboard');
  }, [router]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setTenants([]);
      setActiveTenantState(null);
      localStorage.removeItem('active_tenant_id');
      router.push('/login');
    }
  }, [router]);

  const setActiveTenant = useCallback((tenant: TenantMembership) => {
    setActiveTenantState(tenant);
    const tenantId = getTenantIdString(tenant);
    if (tenantId) {
      localStorage.setItem('active_tenant_id', tenantId);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        tenants,
        activeTenant,
        loading,
        login,
        register,
        logout,
        setActiveTenant,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Hook for requiring authentication
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  return { user, loading };
}
