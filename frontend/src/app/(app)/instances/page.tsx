'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Server, ExternalLink, RefreshCw } from 'lucide-react';

export default function InstancesPage() {
  const { tenants, activeTenant, loading: authLoading } = useAuth();
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = () => {
    setRefreshing(true);
    // In a real app, we'd refetch tenants here
    setTimeout(() => setRefreshing(false), 1000);
    window.location.reload();
  };

  if (authLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  // Ensure tenants is an array
  const tenantList = Array.isArray(tenants) ? tenants : [];

  if (tenantList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <Server className="h-12 w-12 mb-4" />
        <p className="text-lg">No instances configured</p>
        <p className="text-sm">Contact support to connect a WhatsApp instance</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Instances</h1>
          <p className="text-muted-foreground">
            Manage your WhatsApp instances
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Instance Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {tenantList.map((membership) => {
          const isActive = membership.tenant_id === activeTenant?.tenant_id;

          return (
            <Card
              key={membership.tenant_id}
              className={`cursor-pointer transition-colors hover:border-green-300 ${
                isActive ? 'border-green-500 bg-green-50/50' : ''
              }`}
              onClick={() => router.push(`/instances/${membership.tenant?.instance_name || membership.tenant_id}`)}
            >
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg font-medium">
                  {membership.tenant?.instance_name || 'Instance'}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {isActive && (
                    <Badge variant="outline" className="border-green-500 text-green-600">
                      Active
                    </Badge>
                  )}
                  <Badge variant="secondary" className="capitalize">
                    {membership.role}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Server URL</p>
                    <p className="text-sm truncate">
                      {membership.tenant?.evo_server_url || 'Not configured'}
                    </p>
                  </div>

                  <div>
                    <p className="text-sm font-medium text-muted-foreground">LLM Provider</p>
                    <p className="text-sm capitalize">
                      {membership.tenant?.llm_provider || 'Default'}
                    </p>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-muted-foreground"
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(`/instances/${membership.tenant?.instance_name || membership.tenant_id}`);
                    }}
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    View details
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
