'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { tenantsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Brain, Save, RotateCcw, MessageSquare } from 'lucide-react';
import { toast } from 'sonner';

export default function KnowledgePage() {
  const { activeTenant, refreshTenants } = useAuth();
  const [systemPrompt, setSystemPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Fetch current system prompt
  useEffect(() => {
    const loadPrompt = async () => {
      if (!activeTenant?.tenant_id) {
        setLoading(false);
        return;
      }

      try {
        const tenant = await tenantsApi.get(activeTenant.tenant_id);
        setSystemPrompt(tenant.system_prompt || '');
        setOriginalPrompt(tenant.system_prompt || '');
      } catch (error) {
        console.error('Failed to load prompt:', error);
        toast.error('Failed to load system prompt');
      } finally {
        setLoading(false);
      }
    };

    loadPrompt();
  }, [activeTenant?.tenant_id]);

  const handleSave = async () => {
    if (!activeTenant?.tenant_id) return;

    setSaving(true);
    try {
      await tenantsApi.update(activeTenant.tenant_id, { system_prompt: systemPrompt });
      setOriginalPrompt(systemPrompt);
      await refreshTenants();
      toast.success('System prompt saved successfully');
    } catch (error) {
      console.error('Failed to save prompt:', error);
      toast.error('Failed to save system prompt');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setSystemPrompt(originalPrompt);
    toast.info('Changes discarded');
  };

  const hasChanges = systemPrompt !== originalPrompt;
  const charCount = systemPrompt.length;

  if (!activeTenant?.tenant_id) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <Brain className="h-12 w-12 mb-4" />
        <p className="text-lg">No WhatsApp connected</p>
        <p className="text-sm">Connect a WhatsApp number to configure the AI</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI Settings</h1>
          <p className="text-muted-foreground">
            Configure how the AI responds to messages for {activeTenant?.tenant?.instance_name || 'your connection'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={!hasChanges || saving}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Discard
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || saving}
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {/* System Prompt Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            System Prompt
          </CardTitle>
          <CardDescription>
            This prompt defines the AI personality and how it responds to customer messages.
            It sets the context, tone, and guidelines for all AI-generated replies.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            className="w-full min-h-[300px] p-4 text-sm rounded-md border border-input bg-background font-mono resize-y"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Enter the system prompt for your AI assistant...

Example:
You are a helpful customer service assistant for [Company Name].
Your role is to answer customer questions professionally and helpfully.
Be friendly, concise, and always try to provide accurate information.
If you don't know the answer, politely say so and offer to escalate to a human agent."
            disabled={saving}
          />

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <div className="flex items-center gap-4">
              <span>{charCount.toLocaleString()} characters</span>
              {hasChanges && (
                <span className="text-amber-400">Unsaved changes</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tips Card */}
      <Card>
        <CardHeader>
          <CardTitle>Writing an Effective Prompt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <h4 className="font-medium text-green-400">Do</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>- Define a clear role and personality</li>
                <li>- Specify the tone (formal, friendly, etc.)</li>
                <li>- Include key information about your business</li>
                <li>- Set boundaries for what the AI should/shouldn&apos;t do</li>
                <li>- Provide examples of good responses</li>
              </ul>
            </div>
            <div className="space-y-2">
              <h4 className="font-medium text-red-400">Don&apos;t</h4>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>- Make the prompt too long or complex</li>
                <li>- Include sensitive information (passwords, etc.)</li>
                <li>- Give contradictory instructions</li>
                <li>- Expect the AI to know real-time info</li>
                <li>- Forget to test with real conversations</li>
              </ul>
            </div>
          </div>

          <Separator />

          <div>
            <h4 className="font-medium mb-2">Example Prompt Structure</h4>
            <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
{`You are [Name], the AI assistant for [Company].

ROLE: [What you do - customer support, sales, etc.]

TONE: [Friendly, professional, casual, etc.]

KEY INFORMATION:
- [Business hours, location, etc.]
- [Products/services offered]
- [Common policies]

GUIDELINES:
- [How to handle specific situations]
- [When to escalate to humans]
- [Things to avoid saying]`}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
