'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { sessionsApi, eventsApi } from '@/lib/api';
import { Timeline, messageToTimelineEvent } from '@/components/shared/timeline';
import { SessionStatusBadge } from '@/components/shared/status-badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  ArrowLeft,
  Play,
  Pause,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';
import type { Session, Message } from '@/types/api';
import { toast } from 'sonner';

export default function SessionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { activeTenant } = useAuth();
  const sessionId = Number(params.id);

  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadData = useCallback(async () => {
    if (!activeTenant?.tenant_id || !sessionId) return;

    try {
      const [sessionData, messagesData] = await Promise.all([
        sessionsApi.get(sessionId, activeTenant.tenant_id),
        eventsApi.list({
          tenant_id: activeTenant.tenant_id,
          limit: 50,
        }),
      ]);

      setSession(sessionData);
      // Filter messages for this session's chat_id
      const sessionMessages = messagesData.filter(
        (m) => m.chat_id === sessionData.chat_id
      );
      setMessages(sessionMessages);
    } catch (error) {
      console.error('Failed to load session:', error);
      toast.error('Failed to load session');
    } finally {
      setLoading(false);
    }
  }, [activeTenant?.tenant_id, sessionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePause = async () => {
    if (!activeTenant?.tenant_id || !session) return;
    setActionLoading(true);

    try {
      await sessionsApi.pause(session.id, activeTenant.tenant_id);
      // Refetch session data since pause returns status, not session
      const updatedSession = await sessionsApi.get(session.id, activeTenant.tenant_id);
      setSession(updatedSession);
      toast.success('Session paused');
    } catch (error) {
      console.error('Failed to pause session:', error);
      toast.error('Failed to pause session');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    if (!activeTenant?.tenant_id || !session) return;
    setActionLoading(true);

    try {
      await sessionsApi.resume(session.id, activeTenant.tenant_id);
      // Refetch session data since resume returns status, not session
      const updatedSession = await sessionsApi.get(session.id, activeTenant.tenant_id);
      setSession(updatedSession);
      toast.success('Session resumed');
    } catch (error) {
      console.error('Failed to resume session:', error);
      toast.error('Failed to resume session');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopyChatId = () => {
    if (!session) return;
    navigator.clipboard.writeText(session.chat_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          <div className="md:col-span-2">
            <Skeleton className="h-[400px]" />
          </div>
          <Skeleton className="h-[400px]" />
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <p className="text-lg text-muted-foreground">Session not found</p>
        <Button variant="outline" className="mt-4" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Go back
        </Button>
      </div>
    );
  }

  const timelineEvents = messages.map(messageToTimelineEvent).reverse();
  const displayChatId = session.chat_id?.split('@')[0] || session.chat_id || 'Unknown';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold font-mono">{displayChatId}</h1>
              <SessionStatusBadge isPaused={session.is_paused} />
            </div>
            <p className="text-sm text-muted-foreground">
              Session #{session.id}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={actionLoading}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>

          {session.is_paused ? (
            <Button
              size="sm"
              onClick={handleResume}
              disabled={actionLoading}
              className="bg-green-600 hover:bg-green-700"
            >
              <Play className="h-4 w-4 mr-2" />
              Resume AI
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={handlePause}
              disabled={actionLoading}
              className="border-orange-500 text-orange-600 hover:bg-orange-50"
            >
              <Pause className="h-4 w-4 mr-2" />
              Pause AI
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="grid gap-6 md:grid-cols-3">
        {/* Timeline */}
        <div className="md:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Conversation Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline
                events={timelineEvents}
                emptyMessage="No messages in this conversation yet"
              />
            </CardContent>
          </Card>
        </div>

        {/* Session Info */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Session Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Chat ID</p>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-sm bg-muted px-2 py-1 rounded flex-1 truncate">
                    {session.chat_id}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleCopyChatId}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <Separator />

              <div>
                <p className="text-sm font-medium text-muted-foreground">Status</p>
                <div className="mt-1">
                  <SessionStatusBadge isPaused={session.is_paused} />
                </div>
              </div>

              {session.pause_reason && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Pause Reason</p>
                  <p className="text-sm capitalize mt-1">
                    {session.pause_reason.replace(/_/g, ' ')}
                  </p>
                </div>
              )}

              <Separator />

              <div>
                <p className="text-sm font-medium text-muted-foreground">Last Message</p>
                <p className="text-sm mt-1">
                  {formatDistanceToNow(new Date(session.last_message_at), { addSuffix: true })}
                </p>
                <p className="text-xs text-muted-foreground">
                  {format(new Date(session.last_message_at), 'PPpp')}
                </p>
              </div>

              {session.last_human_at && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Last Human Activity</p>
                  <p className="text-sm mt-1">
                    {formatDistanceToNow(new Date(session.last_human_at), { addSuffix: true })}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {format(new Date(session.last_human_at), 'PPpp')}
                  </p>
                </div>
              )}

              <Separator />

              <div>
                <p className="text-sm font-medium text-muted-foreground">Created</p>
                <p className="text-sm mt-1">
                  {format(new Date(session.created_at), 'PPpp')}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
