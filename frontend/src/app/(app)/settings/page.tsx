'use client';

import { useAuth } from '@/hooks/use-auth';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { Copy, Check, User, Server, Shield } from 'lucide-react';
import { useState } from 'react';

export default function SettingsPage() {
  const { user, activeTenant, tenants } = useAuth();
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const webhookUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/webhooks/evolution`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and instance settings
        </p>
      </div>

      {/* Account Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Account
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Display Name</p>
            <p className="text-sm">{user?.display_name || 'Not set'}</p>
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium text-muted-foreground">Email</p>
            <p className="text-sm">{user?.email}</p>
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium text-muted-foreground">User ID</p>
            <p className="text-sm font-mono">{user?.id}</p>
          </div>
        </CardContent>
      </Card>

      {/* Active Instance */}
      {activeTenant && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Active Instance
            </CardTitle>
            <CardDescription>
              Currently selected WhatsApp instance
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Instance Name</p>
              <p className="text-sm font-mono">{activeTenant?.tenant?.instance_name || 'N/A'}</p>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Your Role</p>
              <Badge variant="outline" className="capitalize mt-1">
                {activeTenant?.role || 'member'}
              </Badge>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Webhook URL</p>
              <p className="text-sm text-muted-foreground mb-2">
                Use this URL in Evolution API settings
              </p>
              <div className="flex items-center gap-2">
                <code className="text-sm bg-muted px-3 py-2 rounded flex-1 truncate">
                  {webhookUrl}
                </code>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleCopy(webhookUrl, 'webhook')}
                >
                  {copied === 'webhook' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Evolution Server</p>
              <p className="text-sm font-mono">
                {activeTenant?.tenant?.evo_server_url || 'Not configured'}
              </p>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">LLM Provider</p>
              <p className="text-sm capitalize">
                {activeTenant?.tenant?.llm_provider || 'Default'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* All Instances */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Your Instances
          </CardTitle>
          <CardDescription>
            All instances you have access to
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!tenants || tenants.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No instances configured
            </p>
          ) : (
            <div className="space-y-3">
              {tenants.map((membership) => (
                <div
                  key={membership.tenant_id || membership.tenant?.id}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div>
                    <p className="font-medium">{membership.tenant?.instance_name || 'Instance'}</p>
                    <p className="text-sm text-muted-foreground">
                      {membership.tenant?.evo_server_url || 'N/A'}
                    </p>
                  </div>
                  <Badge variant="outline" className="capitalize">
                    {membership.role || 'member'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* API Information */}
      <Card>
        <CardHeader>
          <CardTitle>API Information</CardTitle>
          <CardDescription>
            Backend API connection details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">API URL</p>
            <p className="text-sm font-mono">
              {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
