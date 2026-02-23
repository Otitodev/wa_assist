'use client';

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import { authClient } from '@/lib/auth-client';
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
  refreshTenants: () => Promise<void>;
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
  // Prevents initAuth from clearing user state during post-login navigation
  const transitioning = useRef(false);

  // BetterAuth session hook — reactive, no polling needed
  const { data: session, isPending } = authClient.useSession();

  useEffect(() => {
    const initAuth = async () => {
      if (isPending) return;

      if (!session?.user) {
        // Don't clear state while we're navigating after a successful sign-in
        if (transitioning.current) return;
        setUser(null);
        setTenants([]);
        setActiveTenantState(null);
        setLoading(false);
        return;
      }
      transitioning.current = false;

      const baUser = session.user as {
        id: string;
        email: string;
        name: string;
        display_name?: string;
        emailVerified: boolean;
        createdAt: Date | string;
      };

      setUser({
        id: baUser.id,
        email: baUser.email,
        name: baUser.name,
        display_name: baUser.display_name,
        emailVerified: baUser.emailVerified,
        createdAt: typeof baUser.createdAt === 'string'
          ? baUser.createdAt
          : baUser.createdAt.toISOString(),
      });

      try {
        const tenantList = await tenantsApi.list();
        const validTenants = Array.isArray(tenantList) ? tenantList : [];
        setTenants(validTenants);

        const savedTenantId = localStorage.getItem('active_tenant_id');
        if (savedTenantId && validTenants.length > 0) {
          const saved = validTenants.find(
            (t) => getTenantIdString(t) === savedTenantId
          );
          setActiveTenantState(saved ?? validTenants[0]);
        } else if (validTenants.length > 0) {
          setActiveTenantState(validTenants[0]);
        }
      } catch {
        // Tenant fetch may fail for brand-new users — not an error
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, [session, isPending]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await authClient.signIn.email({ email, password });
    if (result.error) {
      throw new Error(result.error.message ?? 'Login failed');
    }

    // Mark as transitioning so initAuth doesn't clear state during navigation
    transitioning.current = true;
    setLoading(true);

    // Full-page navigation avoids client-side race conditions with useSession
    window.location.href = '/dashboard';
  }, []);

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const result = await authClient.signUp.email({
      email,
      password,
      name: displayName,
      // @ts-expect-error — additionalFields typed at runtime by BetterAuth
      display_name: displayName,
    });
    if (result.error) {
      throw new Error(result.error.message ?? 'Registration failed');
    }

    transitioning.current = true;
    setLoading(true);
    window.location.href = '/dashboard';
  }, []);

  const logout = useCallback(async () => {
    try {
      await authClient.signOut();
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
    const id = getTenantIdString(tenant);
    if (id) localStorage.setItem('active_tenant_id', id);
  }, []);

  const refreshTenants = useCallback(async () => {
    try {
      const tenantList = await tenantsApi.list();
      const validTenants = Array.isArray(tenantList) ? tenantList : [];
      setTenants(validTenants);

      if (!activeTenant && validTenants.length > 0) {
        const first = validTenants[0];
        setActiveTenantState(first);
        const id = getTenantIdString(first);
        if (id) localStorage.setItem('active_tenant_id', id);
      }
    } catch (error) {
      console.error('Failed to refresh tenants:', error);
    }
  }, [activeTenant]);

  return (
    <AuthContext.Provider
      value={{
        user,
        tenants,
        activeTenant,
        loading: loading || isPending,
        login,
        register,
        logout,
        setActiveTenant,
        refreshTenants,
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
