'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { instancesApi, tenantsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft, Copy, Check, Zap, Server, Settings, Pencil, X, Save } from 'lucide-react';
import { toast } from 'sonner';
import type { Tenant } from '@/types/api';

export default function InstanceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { tenants, activeTenant, refreshTenants } = useAuth();
  const instanceName = params.name as string;

  const [instance, setInstance] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editEvoServerUrl, setEditEvoServerUrl] = useState('');
  const [editEvoApiKey, setEditEvoApiKey] = useState('');
  const [editSystemPrompt, setEditSystemPrompt] = useState('');

  // Find instance from tenants (we already have this data)
  useEffect(() => {
    const tenantList = Array.isArray(tenants) ? tenants : [];
    const membership = tenantList.find((t) => t?.tenant?.instance_name === instanceName);
    if (membership?.tenant) {
      setInstance(membership.tenant);
      // Initialize edit fields
      setEditEvoServerUrl(membership.tenant.evo_server_url || '');
      setEditEvoApiKey(''); // Don't show existing key for security
      setEditSystemPrompt(membership.tenant.system_prompt || '');
    }
    setLoading(false);
  }, [tenants, instanceName]);

  const handleTestWebhook = async () => {
    if (!instance || !activeTenant?.tenant_id) return;

    setTestingWebhook(true);
    try {
      const result = await instancesApi.testWebhook(instanceName, activeTenant.tenant_id);
      if (result.success) {
        toast.success('Webhook test successful');
      } else {
        toast.error(result.message || 'Webhook test failed');
      }
    } catch (error) {
      console.error('Webhook test failed:', error);
      toast.error('Failed to test webhook');
    } finally {
      setTestingWebhook(false);
    }
  };

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleStartEdit = () => {
    if (instance) {
      setEditEvoServerUrl(instance.evo_server_url || '');
      setEditEvoApiKey('');
      setEditSystemPrompt(instance.system_prompt || '');
    }
    setEditing(true);
  };

  const handleCancelEdit = () => {
    if (instance) {
      setEditEvoServerUrl(instance.evo_server_url || '');
      setEditEvoApiKey('');
      setEditSystemPrompt(instance.system_prompt || '');
    }
    setEditing(false);
  };

  const handleSave = async () => {
    if (!instance?.id) return;

    setSaving(true);
    try {
      const updateData: { evo_server_url?: string; evo_api_key?: string; system_prompt?: string } = {};

      // Only include changed fields
      if (editEvoServerUrl !== instance.evo_server_url) {
        updateData.evo_server_url = editEvoServerUrl;
      }
      if (editEvoApiKey) {
        updateData.evo_api_key = editEvoApiKey;
      }
      if (editSystemPrompt !== instance.system_prompt) {
        updateData.system_prompt = editSystemPrompt;
      }

      if (Object.keys(updateData).length === 0) {
        toast.info('No changes to save');
        setEditing(false);
        return;
      }

      const updated = await tenantsApi.update(instance.id, updateData);
      setInstance(updated);
      await refreshTenants();
      toast.success('Configuration saved');
      setEditing(false);
    } catch (error) {
      console.error('Failed to save configuration:', error);
      toast.error('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-[400px]" />
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

  const webhookUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/webhooks/evolution`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{instance.instance_name}</h1>
            <p className="text-sm text-muted-foreground">WhatsApp connection settings</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="webhooks">Webhooks</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="h-5 w-5" />
                  Connection Details
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Instance Name</p>
                  <p className="text-sm font-mono">{instance.instance_name}</p>
                </div>

                <Separator />

                <div>
                  <p className="text-sm font-medium text-muted-foreground">Evolution Server</p>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-sm font-mono truncate flex-1">
                      {instance.evo_server_url || 'Not configured'}
                    </p>
                    {instance.evo_server_url && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleCopy(instance.evo_server_url!, 'evo_url')}
                      >
                        {copied === 'evo_url' ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>

                <Separator />

                <div>
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <Badge className="mt-1 bg-green-500">Connected</Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  AI Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">System Prompt</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {instance.system_prompt
                      ? instance.system_prompt.substring(0, 100) + '...'
                      : 'Using default prompt'}
                  </p>
                </div>

                <Separator />

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push('/knowledge')}
                >
                  Edit AI Prompt
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Webhooks Tab */}
        <TabsContent value="webhooks" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                Webhook Configuration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Webhook URL</p>
                <p className="text-sm text-muted-foreground mb-2">
                  Configure this URL in your Evolution API instance settings
                </p>
                <div className="flex items-center gap-2">
                  <code className="text-sm bg-muted px-3 py-2 rounded flex-1 truncate">
                    {webhookUrl}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => handleCopy(webhookUrl, 'webhook_url')}
                  >
                    {copied === 'webhook_url' ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <Separator />

              <div>
                <p className="text-sm font-medium text-muted-foreground">Required Events</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  <Badge variant="outline">messages.upsert</Badge>
                  <Badge variant="outline">connection.update</Badge>
                </div>
              </div>

              <Separator />

              <div>
                <p className="text-sm font-medium mb-2">Test Webhook</p>
                <Button
                  variant="outline"
                  onClick={handleTestWebhook}
                  disabled={testingWebhook}
                >
                  <Zap className={`h-4 w-4 mr-2 ${testingWebhook ? 'animate-pulse' : ''}`} />
                  {testingWebhook ? 'Testing...' : 'Send Test Event'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Config Tab */}
        <TabsContent value="config" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Connection Settings</CardTitle>
              {!editing ? (
                <Button variant="outline" size="sm" onClick={handleStartEdit}>
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </Button>
              ) : (
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleCancelEdit} disabled={saving}>
                    <X className="h-4 w-4 mr-2" />
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    <Save className="h-4 w-4 mr-2" />
                    {saving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label>Connection Name</Label>
                <Input value={instance.instance_name} disabled />
                <p className="text-xs text-muted-foreground">Connection name cannot be changed after creation</p>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="edit-evo-server-url">Evolution Server URL</Label>
                {editing ? (
                  <Input
                    id="edit-evo-server-url"
                    value={editEvoServerUrl}
                    onChange={(e) => setEditEvoServerUrl(e.target.value)}
                    placeholder="https://evolution-api.example.com"
                    disabled={saving}
                  />
                ) : (
                  <p className="text-sm font-mono py-2">{instance.evo_server_url || 'Not configured'}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-evo-api-key">API Key</Label>
                {editing ? (
                  <>
                    <Input
                      id="edit-evo-api-key"
                      type="password"
                      value={editEvoApiKey}
                      onChange={(e) => setEditEvoApiKey(e.target.value)}
                      placeholder="Enter new API key (leave empty to keep current)"
                      disabled={saving}
                    />
                    <p className="text-xs text-muted-foreground">Leave empty to keep existing API key</p>
                  </>
                ) : (
                  <p className="text-sm py-2">{instance.evo_api_key ? '********' : 'Not configured'}</p>
                )}
              </div>

              <Separator />

              <div className="space-y-2">
                <Label htmlFor="edit-system-prompt">System Prompt</Label>
                {editing ? (
                  <textarea
                    id="edit-system-prompt"
                    className="w-full min-h-[150px] p-3 text-sm rounded-md border border-input bg-background"
                    value={editSystemPrompt}
                    onChange={(e) => setEditSystemPrompt(e.target.value)}
                    placeholder="Enter AI system prompt..."
                    disabled={saving}
                  />
                ) : (
                  <pre className="text-sm bg-muted p-4 rounded-lg overflow-auto whitespace-pre-wrap">
                    {instance.system_prompt || 'Using default prompt'}
                  </pre>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
