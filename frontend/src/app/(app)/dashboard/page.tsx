'use client';

import { useEffect, useState, useRef } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { sessionsApi, healthApi, eventsApi, billingApi } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
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
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { Session, Message, Subscription } from '@/types/api';
import { Progress } from '@/components/ui/progress';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  const [activityData, setActivityData] = useState<Array<{ date: string; messages: number; collisions: number }>>([]);
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'error' | 'loading'>('loading');
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const loadData = async () => {
    // Check both activeTenant and tenant_id exist
    if (!activeTenant?.tenant_id) {
      setLoading(false);
      return;
    }

    const tenantId = activeTenant.tenant_id;

    try {
      // Fetch sessions (both active and paused)
      const [activeResult, pausedResult, events, health, activity, sub] = await Promise.all([
        sessionsApi.list({ tenant_id: tenantId, state: 'active', per_page: 1 }),
        sessionsApi.list({ tenant_id: tenantId, state: 'paused', per_page: 1 }),
        eventsApi.list({ tenant_id: tenantId, limit: 10 }),
        healthApi.check().catch(() => ({ status: 'error', database: 'error' })),
        fetch(`${API_URL}/api/analytics/activity?tenant_id=${tenantId}&days=7`, {
          headers: {
            Authorization: `Bearer ${(await authClient.getSession()).data?.session?.token ?? ''}`,
          },
        }).then((r) => r.ok ? r.json() : { data: [] }).catch(() => ({ data: [] })),
        billingApi.getSubscription(tenantId).catch(() => null),
      ]);

      setStats({
        activeSessions: activeResult.total,
        pausedSessions: pausedResult.total,
        totalMessages: events.length,
        lastEventTime: events.length > 0 ? events[0].created_at : null,
      });

      setRecentEvents(events);
      setActivityData(activity.data ?? []);
      setHealthStatus(health.status === 'healthy' ? 'healthy' : 'error');
      setSubscription(sub);
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
  }, [activeTenant?.tenant_id]);

  // SSE: real-time session counts (replaces 30s polling for session stats)
  useEffect(() => {
    if (!activeTenant?.tenant_id) return;

    let cancelled = false;

    authClient.getSession().then((result) => {
      if (cancelled) return;
      const token = result.data?.session?.token;
      if (!token) return;

      const es = new EventSource(
        `${API_URL}/api/stream/sessions/${activeTenant.tenant_id}?token=${encodeURIComponent(token)}`
      );
      esRef.current = es;

      es.onmessage = (e) => {
        try {
          const { sessions } = JSON.parse(e.data) as { sessions: Session[] };
          if (!sessions) return;
          const active = sessions.filter((s) => !s.is_paused).length;
          const paused = sessions.filter((s) => s.is_paused).length;
          setStats((prev) => prev ? { ...prev, activeSessions: active, pausedSessions: paused } : null);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
      };
    });

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
    };
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
            <MessageSquare className="h-4 w-4 text-green-400" />
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
            <Pause className="h-4 w-4 text-amber-400" />
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
            <Bot className="h-4 w-4 text-blue-400" />
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

      {/* Activity Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Activity — Last 7 Days</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : activityData.length === 0 ? (
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
              No activity data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={activityData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--popover))', border: '1px solid hsl(var(--border))', borderRadius: 6, fontSize: 12 }}
                  labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="messages" name="Messages" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
                <Bar dataKey="collisions" name="Human takeovers" fill="hsl(38 92% 50%)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Usage Widget */}
      {subscription && (
        <Card className={
          subscription.max_conversations_per_month !== -1 &&
          subscription.conversations_used >= subscription.max_conversations_per_month
            ? 'border-red-500/50'
            : subscription.max_conversations_per_month !== -1 &&
              subscription.conversations_used / subscription.max_conversations_per_month >= 0.8
            ? 'border-yellow-500/50'
            : ''
        }>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-sm font-medium">AI Conversations — {subscription.plan_display_name} Plan</CardTitle>
            </div>
            <Link href="/settings/billing" className="text-xs text-muted-foreground hover:text-foreground underline-offset-4 hover:underline">
              {subscription.plan_name !== 'agency' ? 'Upgrade' : 'Manage billing'} →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="flex justify-between text-sm mb-1.5">
              <span className="text-muted-foreground">Used this month</span>
              <span className="font-medium">
                {subscription.max_conversations_per_month === -1
                  ? `${subscription.conversations_used} / Unlimited`
                  : `${subscription.conversations_used} / ${subscription.max_conversations_per_month.toLocaleString()}`}
              </span>
            </div>
            {subscription.max_conversations_per_month !== -1 && (
              <Progress
                value={Math.min(100, Math.round((subscription.conversations_used / subscription.max_conversations_per_month) * 100))}
                className={`h-2 ${
                  subscription.conversations_used >= subscription.max_conversations_per_month
                    ? '[&>div]:bg-red-500'
                    : subscription.conversations_used / subscription.max_conversations_per_month >= 0.8
                    ? '[&>div]:bg-yellow-500'
                    : '[&>div]:bg-green-500'
                }`}
              />
            )}
          </CardContent>
        </Card>
      )}

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
