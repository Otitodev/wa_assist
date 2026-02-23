'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { whatsappApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Server, ExternalLink, RefreshCw, Plus, Smartphone, CheckCircle2, Loader2, Wifi, WifiOff } from 'lucide-react';
import { toast } from 'sonner';

type ConnectionStep = 'name' | 'qrcode' | 'connected';

export default function InstancesPage() {
  const { tenants, activeTenant, loading: authLoading, refreshTenants } = useAuth();
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);

  // Add Instance dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [connectionName, setConnectionName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<ConnectionStep>('name');
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [createdInstanceName, setCreatedInstanceName] = useState<string | null>(null);
  const [checkingConnection, setCheckingConnection] = useState(false);
  const [connectionStatuses, setConnectionStatuses] = useState<Record<string, 'open' | 'connecting' | 'close' | 'unknown'>>({});

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshTenants();
    setRefreshing(false);
  };

  const resetDialog = useCallback(() => {
    setStep('name');
    setConnectionName('');
    setQrCode(null);
    setPairingCode(null);
    setCreatedInstanceName(null);
    setCheckingConnection(false);
    setSubmitting(false);
  }, []);

  const handleDialogClose = (open: boolean) => {
    if (!open) {
      resetDialog();
    }
    setDialogOpen(open);
  };

  // Fetch live connection status for all instances
  useEffect(() => {
    const list = Array.isArray(tenants) ? tenants : [];
    list.forEach((membership) => {
      const name = membership.tenant?.instance_name;
      if (!name) return;
      whatsappApi.getConnectionStatus(name)
        .then((status) => setConnectionStatuses(prev => ({ ...prev, [name]: status.state })))
        .catch(() => setConnectionStatuses(prev => ({ ...prev, [name]: 'unknown' })));
    });
  }, [tenants]);

  // Poll for connection status when showing QR code
  useEffect(() => {
    if (step !== 'qrcode' || !createdInstanceName) return;

    setCheckingConnection(true);
    const pollInterval = setInterval(async () => {
      try {
        const status = await whatsappApi.getConnectionStatus(createdInstanceName);
        if (status.connected && status.state === 'open') {
          clearInterval(pollInterval);
          setCheckingConnection(false);
          setStep('connected');
          toast.success('WhatsApp connected successfully!');
          await refreshTenants();
        }
      } catch (error) {
        console.error('Failed to check connection status:', error);
      }
    }, 3000); // Poll every 3 seconds

    // Clean up interval on unmount or step change
    return () => clearInterval(pollInterval);
  }, [step, createdInstanceName, refreshTenants]);

  const handleGetQRCode = async (e: React.FormEvent) => {
    e.preventDefault();

    const trimmedName = connectionName.trim().toLowerCase().replace(/\s+/g, '-');
    if (!trimmedName) {
      toast.error('Please enter a connection name');
      return;
    }

    setSubmitting(true);
    try {
      const result = await whatsappApi.connect({
        instance_name: trimmedName,
      });

      if (result.ok && result.qr_code) {
        setQrCode(result.qr_code);
        setPairingCode(result.pairing_code || null);
        setCreatedInstanceName(result.instance_name);
        setStep('qrcode');
      } else {
        throw new Error('Failed to get QR code');
      }
    } catch (error: unknown) {
      console.error('Failed to create instance:', error);
      const message = error instanceof Error ? error.message : 'Failed to connect WhatsApp';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefreshQRCode = async () => {
    if (!createdInstanceName) return;

    setSubmitting(true);
    try {
      const result = await whatsappApi.getQRCode(createdInstanceName);
      if (result.ok && result.qr_code) {
        setQrCode(result.qr_code);
        setPairingCode(result.pairing_code || null);
      }
    } catch (error) {
      console.error('Failed to refresh QR code:', error);
      toast.error('Failed to refresh QR code');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinish = async () => {
    await refreshTenants();
    handleDialogClose(false);
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">WhatsApp Connections</h1>
          <p className="text-muted-foreground">
            Manage your connected WhatsApp numbers
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>

          <Dialog open={dialogOpen} onOpenChange={handleDialogClose}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Connect WhatsApp
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              {step === 'name' && (
                <form onSubmit={handleGetQRCode}>
                  <DialogHeader>
                    <DialogTitle>Connect WhatsApp</DialogTitle>
                    <DialogDescription>
                      Give your WhatsApp connection a name, then scan the QR code with your phone
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-4 py-6">
                    <div className="space-y-2">
                      <Label htmlFor="connection-name">Connection Name</Label>
                      <Input
                        id="connection-name"
                        placeholder="my-business"
                        value={connectionName}
                        onChange={(e) => setConnectionName(e.target.value)}
                        disabled={submitting}
                        autoFocus
                      />
                      <p className="text-xs text-muted-foreground">
                        A unique name to identify this WhatsApp number
                      </p>
                    </div>
                  </div>

                  <DialogFooter>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleDialogClose(false)}
                      disabled={submitting}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={submitting}>
                      {submitting ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Smartphone className="h-4 w-4 mr-2" />
                          Get QR Code
                        </>
                      )}
                    </Button>
                  </DialogFooter>
                </form>
              )}

              {step === 'qrcode' && (
                <>
                  <DialogHeader>
                    <DialogTitle>Scan QR Code</DialogTitle>
                    <DialogDescription>
                      Open WhatsApp on your phone, go to Settings → Linked Devices → Link a Device
                    </DialogDescription>
                  </DialogHeader>

                  <div className="flex flex-col items-center py-6 space-y-4">
                    {qrCode ? (
                      <div className="bg-white p-4 rounded-lg shadow-inner">
                        <img
                          src={`data:image/png;base64,${qrCode}`}
                          alt="WhatsApp QR Code"
                          className="w-64 h-64"
                        />
                      </div>
                    ) : (
                      <Skeleton className="w-64 h-64" />
                    )}

                    {pairingCode && (
                      <div className="text-center">
                        <p className="text-sm text-muted-foreground mb-1">Or use pairing code:</p>
                        <code className="text-lg font-mono bg-muted px-3 py-1 rounded">
                          {pairingCode}
                        </code>
                      </div>
                    )}

                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      {checkingConnection ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Waiting for connection...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="h-4 w-4" />
                          QR code will auto-refresh
                        </>
                      )}
                    </div>
                  </div>

                  <DialogFooter className="flex-col sm:flex-row gap-2">
                    <Button
                      variant="outline"
                      onClick={handleRefreshQRCode}
                      disabled={submitting}
                      className="w-full sm:w-auto"
                    >
                      {submitting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4 mr-2" />
                      )}
                      Refresh QR Code
                    </Button>
                  </DialogFooter>
                </>
              )}

              {step === 'connected' && (
                <>
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                      Connected!
                    </DialogTitle>
                    <DialogDescription>
                      Your WhatsApp is now connected and ready to receive messages
                    </DialogDescription>
                  </DialogHeader>

                  <div className="flex flex-col items-center py-8">
                    <div className="h-20 w-20 rounded-full bg-green-500/15 flex items-center justify-center mb-4">
                      <CheckCircle2 className="h-10 w-10 text-green-400" />
                    </div>
                    <p className="text-center text-muted-foreground">
                      <strong>{createdInstanceName}</strong> is now connected.
                      <br />
                      Messages will appear in Conversations.
                    </p>
                  </div>

                  <DialogFooter>
                    <Button onClick={handleFinish} className="w-full">
                      Done
                    </Button>
                  </DialogFooter>
                </>
              )}
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Empty State */}
      {tenantList.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
          <Server className="h-12 w-12 mb-4" />
          <p className="text-lg">No WhatsApp numbers connected</p>
          <p className="text-sm mb-4">Connect your first WhatsApp number to start automating conversations</p>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Connect WhatsApp
          </Button>
        </div>
      ) : (
        /* Instance Grid */
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {tenantList.map((membership) => {
            const isActive = membership.tenant_id === activeTenant?.tenant_id;

            return (
              <Card
                key={membership.tenant_id}
                className={`cursor-pointer transition-colors hover:border-green-500/40 ${
                  isActive ? 'border-green-500/50 bg-green-500/8' : ''
                }`}
                onClick={() => router.push(`/instances/${membership.tenant?.instance_name || membership.tenant_id}`)}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-lg font-medium">
                    {membership.tenant?.instance_name || 'Instance'}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {isActive && (
                      <Badge variant="outline" className="border-green-500/40 text-green-400">
                        Selected
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
                      {(() => {
                        const name = membership.tenant?.instance_name ?? '';
                        const state = connectionStatuses[name];
                        if (!state) return (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                          </span>
                        );
                        if (state === 'open') return (
                          <span className="flex items-center gap-1 text-xs text-green-400">
                            <Wifi className="h-3 w-3" /> Connected
                          </span>
                        );
                        if (state === 'connecting') return (
                          <span className="flex items-center gap-1 text-xs text-amber-400">
                            <Loader2 className="h-3 w-3 animate-spin" /> Connecting
                          </span>
                        );
                        return (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <WifiOff className="h-3 w-3" /> Disconnected
                          </span>
                        );
                      })()}
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
      )}
    </div>
  );
}
