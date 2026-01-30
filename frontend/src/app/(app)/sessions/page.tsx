'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { sessionsApi } from '@/lib/api';
import { DataTable } from '@/components/shared/data-table';
import { SessionStatusBadge } from '@/components/shared/status-badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatDistanceToNow } from 'date-fns';
import { RefreshCw, MessageSquare } from 'lucide-react';
import type { Session } from '@/types/api';
import type { ColumnDef } from '@tanstack/react-table';

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

  const handleRefresh = () => {
    setRefreshing(true);
    loadSessions();
  };

  const handleRowClick = (session: Session) => {
    router.push(`/sessions/${session.id}`);
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
            {total} total conversations for {activeTenant?.tenant?.instance_name || 'your connection'}
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

      {/* Filters */}
      <Tabs value={stateFilter} onValueChange={(v) => setStateFilter(v as StateFilter)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="active">AI Mode</TabsTrigger>
          <TabsTrigger value="paused">Human Mode</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Table */}
      <DataTable
        columns={columns}
        data={sessions}
        loading={loading}
        searchColumn="chat_id"
        searchPlaceholder="Search by phone number..."
        onRowClick={handleRowClick}
        pageSize={15}
      />
    </div>
  );
}
