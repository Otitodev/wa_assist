'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { sessionsApi, healthApi, eventsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  MessageSquare,
  Pause,
  Bot,
  Activity,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { formatDistanceToNow } from 'date-fns';
import type { Session, Message } from '@/types/api';

interface DashboardStats {
  activeSessions: number;
  pausedSessions: number;
  totalMessages: number;
  lastEventTime: string | null;
}

export default function DashboardPage() {
  const { activeTenant } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentEvents, setRecentEvents] = useState<Message[]>([]);
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'error' | 'loading'>('loading');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    // Check both activeTenant and tenant_id exist
    if (!activeTenant?.tenant_id) {
      setLoading(false);
      return;
    }

    const tenantId = activeTenant.tenant_id;

    try {
      // Fetch sessions (both active and paused)
      const [activeResult, pausedResult, events, health] = await Promise.all([
        sessionsApi.list({ tenant_id: tenantId, state: 'active', per_page: 1 }),
        sessionsApi.list({ tenant_id: tenantId, state: 'paused', per_page: 1 }),
        eventsApi.list({ tenant_id: tenantId, limit: 10 }),
        healthApi.check().catch(() => ({ status: 'error', database: 'error' })),
      ]);

      setStats({
        activeSessions: activeResult.total,
        pausedSessions: pausedResult.total,
        totalMessages: events.length, // Placeholder
        lastEventTime: events.length > 0 ? events[0].created_at : null,
      });

      setRecentEvents(events);
      setHealthStatus(health.status === 'healthy' ? 'healthy' : 'error');
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      setHealthStatus('error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();

    // Poll every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [activeTenant?.tenant_id]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (!activeTenant?.tenant_id) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-4" />
        <p className="text-lg">No WhatsApp connected</p>
        <p className="text-sm">Connect a WhatsApp number to view your dashboard</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview for {activeTenant?.tenant?.instance_name || 'your instance'}
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

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* AI Mode Conversations */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">AI Mode</CardTitle>
            <MessageSquare className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{stats?.activeSessions ?? 0}</div>
            )}
            <p className="text-xs text-muted-foreground">Conversations with AI responding</p>
          </CardContent>
        </Card>

        {/* Human Mode Conversations */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Human Mode</CardTitle>
            <Pause className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{stats?.pausedSessions ?? 0}</div>
            )}
            <p className="text-xs text-muted-foreground">You are handling these</p>
          </CardContent>
        </Card>

        {/* AI Replies (placeholder) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
            <Bot className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold">{recentEvents.length}</div>
            )}
            <p className="text-xs text-muted-foreground">Messages in last 10</p>
          </CardContent>
        </Card>

        {/* System Health */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {healthStatus === 'loading' ? (
              <Skeleton className="h-6 w-20" />
            ) : (
              <Badge
                variant={healthStatus === 'healthy' ? 'default' : 'destructive'}
                className={healthStatus === 'healthy' ? 'bg-green-500' : ''}
              >
                {healthStatus === 'healthy' ? 'Healthy' : 'Error'}
              </Badge>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {stats?.lastEventTime
                ? `Last event ${formatDistanceToNow(new Date(stats.lastEventTime), { addSuffix: true })}`
                : 'No recent events'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Messages</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-4 w-4 rounded-full" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : recentEvents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No recent messages</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center gap-4 py-2 border-b last:border-0"
                >
                  <div
                    className={`h-2 w-2 rounded-full ${
                      event.from_me ? 'bg-green-500' : 'bg-blue-500'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">
                      {event.text || '[No text content]'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {event.chat_id?.split('@')[0] || event.chat_id || 'Unknown'}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
