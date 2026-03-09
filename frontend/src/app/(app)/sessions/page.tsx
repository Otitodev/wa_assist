'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { sessionsApi } from '@/lib/api';
import { authClient } from '@/lib/auth-client';
import { DataTable } from '@/components/shared/data-table';
import { SessionStatusBadge } from '@/components/shared/status-badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatDistanceToNow } from 'date-fns';
import { RefreshCw, MessageSquare, Play } from 'lucide-react';
import type { Session } from '@/types/api';
import type { ColumnDef, RowSelectionState } from '@tanstack/react-table';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const columns: ColumnDef<Session>[] = [
  {
    accessorKey: 'chat_id',
    header: 'Customer',
    cell: ({ row }) => {
      const chatId = row.getValue('chat_id') as string;
      // Extract phone number from chat_id (e.g., "5511999999999@s.whatsapp.net" -> "5511999999999")
      const displayId = chatId?.split('@')[0] || chatId || 'Unknown';
      return (
        <div className="font-mono text-sm">
          {displayId.length > 15 ? `${displayId.slice(0, 15)}...` : displayId}
        </div>
      );
    },
  },
  {
    accessorKey: 'last_message_text',
    header: 'Preview',
    cell: ({ row }) => {
      const text = row.original.last_message_text;
      return (
        <span className="text-muted-foreground text-sm truncate max-w-[200px] block">
          {text ?? '—'}
        </span>
      );
    },
  },
  {
    accessorKey: 'is_paused',
    header: 'Mode',
    cell: ({ row }) => (
      <SessionStatusBadge isPaused={row.getValue('is_paused')} />
    ),
  },
  {
    accessorKey: 'pause_reason',
    header: 'Reason',
    cell: ({ row }) => {
      const reason = row.getValue('pause_reason') as string | null;
      return reason ? (
        <span className="text-sm text-muted-foreground capitalize">
          {reason.replace(/_/g, ' ')}
        </span>
      ) : (
        <span className="text-sm text-muted-foreground">-</span>
      );
    },
  },
  {
    accessorKey: 'last_message_at',
    header: 'Last Message',
    cell: ({ row }) => {
      const timestamp = row.getValue('last_message_at') as string;
      return (
        <span className="text-sm text-muted-foreground">
          {formatDistanceToNow(new Date(timestamp), { addSuffix: true })}
        </span>
      );
    },
  },
  {
    accessorKey: 'last_human_at',
    header: 'Last Human Reply',
    cell: ({ row }) => {
      const timestamp = row.getValue('last_human_at') as string | null;
      if (!timestamp) {
        return <span className="text-sm text-muted-foreground">-</span>;
      }
      return (
        <span className="text-sm text-muted-foreground">
          {formatDistanceToNow(new Date(timestamp), { addSuffix: true })}
        </span>
      );
    },
  },
];

type StateFilter = 'all' | 'active' | 'paused';

export default function SessionsPage() {
  const { activeTenant } = useAuth();
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stateFilter, setStateFilter] = useState<StateFilter>('all');
  const [total, setTotal] = useState(0);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [bulkResuming, setBulkResuming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const loadSessions = useCallback(async () => {
    if (!activeTenant?.tenant_id) {
      setLoading(false);
      return;
    }

    try {
      const result = await sessionsApi.list({
        tenant_id: activeTenant.tenant_id,
        state: stateFilter === 'all' ? undefined : stateFilter,
        per_page: 100,
      });

      setSessions(result.items);
      setTotal(result.total);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTenant?.tenant_id, stateFilter]);

  useEffect(() => {
    setLoading(true);
    loadSessions();
  }, [loadSessions]);

  // SSE: live session updates (replaces 30s polling)
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
          const { sessions: streamedSessions } = JSON.parse(e.data) as { sessions: Session[] };
          if (!streamedSessions) return;
          // Merge is_paused state into existing sessions to reflect live changes
          setSessions((prev) => {
            const map = new Map(streamedSessions.map((s) => [s.id, s]));
            return prev.map((s) => {
              const updated = map.get(s.id);
              return updated ? { ...s, is_paused: updated.is_paused, pause_reason: updated.pause_reason } : s;
            });
          });
        } catch {
          // ignore
        }
      };

      es.onerror = () => es.close();
    });

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [activeTenant?.tenant_id]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadSessions();
  };

  const handleRowClick = (session: Session) => {
    router.push(`/sessions/${session.id}`);
  };

  const handleBulkResume = async () => {
    if (!activeTenant?.tenant_id) return;
    const selectedIndices = Object.keys(rowSelection).map(Number);
    const selectedSessions = selectedIndices.map((i) => sessions[i]).filter(Boolean);
    if (!selectedSessions.length) return;
    setBulkResuming(true);
    try {
      await Promise.all(
        selectedSessions.map((s) => sessionsApi.resume(s.id, activeTenant.tenant_id))
      );
      setRowSelection({});
      loadSessions();
    } catch (error) {
      console.error('Bulk resume failed:', error);
    } finally {
      setBulkResuming(false);
    }
  };

  if (!activeTenant?.tenant_id) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-4" />
        <p className="text-lg">No WhatsApp connected</p>
        <p className="text-sm">Connect a WhatsApp number to view conversations</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Conversations</h1>
          <p className="text-muted-foreground">
            {loading ? (
              <span className="inline-block h-4 w-48 bg-muted animate-pulse rounded" />
            ) : (
              `${total} total conversations for ${activeTenant?.tenant?.instance_name || 'your connection'}`
            )}
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

      {/* Filters + Bulk Actions */}
      <div className="flex items-center justify-between gap-4">
        <Tabs value={stateFilter} onValueChange={(v) => { setStateFilter(v as StateFilter); setRowSelection({}); }}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">AI Mode</TabsTrigger>
            <TabsTrigger value="paused">Human Mode</TabsTrigger>
          </TabsList>
        </Tabs>
        {Object.keys(rowSelection).length > 0 && (
          <Button
            size="sm"
            onClick={handleBulkResume}
            disabled={bulkResuming}
          >
            <Play className="h-4 w-4 mr-2" />
            {bulkResuming ? 'Resuming…' : `Resume ${Object.keys(rowSelection).length} selected`}
          </Button>
        )}
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={sessions}
        loading={loading}
        searchColumn="chat_id"
        searchPlaceholder="Search by phone number..."
        onRowClick={handleRowClick}
        pageSize={15}
        enableRowSelection
        rowSelection={rowSelection}
        onRowSelectionChange={setRowSelection}
      />
    </div>
  );
}
