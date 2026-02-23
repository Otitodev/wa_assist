'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { whatsappApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Server, Settings, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { Tenant } from '@/types/api';

export default function InstanceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { tenants } = useAuth();
  const instanceName = params.name as string;

  const [instance, setInstance] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionState, setConnectionState] = useState<'open' | 'connecting' | 'close' | 'unknown' | null>(null);
  const [connectionLoading, setConnectionLoading] = useState(false);

  useEffect(() => {
    const tenantList = Array.isArray(tenants) ? tenants : [];
    const membership = tenantList.find((t) => t?.tenant?.instance_name === instanceName);
    if (membership?.tenant) {
      setInstance(membership.tenant);
    }
    setLoading(false);
  }, [tenants, instanceName]);

  useEffect(() => {
    if (!instance) return;
    setConnectionLoading(true);
    whatsappApi.getConnectionStatus(instance.instance_name)
      .then((status) => setConnectionState(status.state))
      .catch(() => setConnectionState('unknown'))
      .finally(() => setConnectionLoading(false));
  }, [instance]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  if (!instance) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <Server className="h-12 w-12 mb-4 text-muted-foreground" />
        <p className="text-lg text-muted-foreground">Connection not found</p>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Go back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{instance.instance_name}</h1>
          <p className="text-sm text-muted-foreground">WhatsApp connection</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Connection status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Connection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Name</p>
              <p className="text-sm">{instance.instance_name}</p>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Status</p>
              {connectionLoading ? (
                <Skeleton className="mt-1 h-5 w-20" />
              ) : connectionState === 'open' ? (
                <Badge className="mt-1 bg-green-500">Connected</Badge>
              ) : connectionState === 'connecting' ? (
                <Badge className="mt-1 bg-amber-500 flex items-center gap-1 w-fit">
                  <Loader2 className="h-3 w-3 animate-spin" /> Connecting
                </Badge>
              ) : connectionState === 'close' ? (
                <Badge className="mt-1" variant="destructive">Disconnected</Badge>
              ) : (
                <Badge className="mt-1" variant="secondary">Unknown</Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {/* AI */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              AI Assistant
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Persona</p>
              <p className="text-sm text-muted-foreground mt-1">
                {instance.system_prompt
                  ? instance.system_prompt.substring(0, 120) + '...'
                  : 'Using default assistant'}
              </p>
            </div>

            <Separator />

            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/knowledge')}
            >
              Edit AI Persona
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
