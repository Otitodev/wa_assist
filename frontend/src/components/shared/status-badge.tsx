'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export type StatusType = 'active' | 'paused' | 'error' | 'connecting' | 'disconnected';

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

const statusConfig: Record<StatusType, { label: string; className: string; variant: 'default' | 'outline' | 'secondary' | 'destructive' }> = {
  active: {
    label: 'AI Mode',
    className: 'bg-green-500/15 text-green-400 border border-green-500/30 hover:bg-green-500/20',
    variant: 'outline',
  },
  paused: {
    label: 'Human Mode',
    className: 'bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/15',
    variant: 'outline',
  },
  error: {
    label: 'Error',
    className: 'bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/20',
    variant: 'outline',
  },
  connecting: {
    label: 'Connecting',
    className: 'bg-zinc-500/15 text-zinc-400 border border-zinc-500/30 hover:bg-zinc-500/20',
    variant: 'outline',
  },
  disconnected: {
    label: 'Disconnected',
    className: 'bg-zinc-700/20 text-zinc-500 border border-zinc-700/30',
    variant: 'outline',
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge
      variant={config.variant}
      className={cn(config.className, className)}
    >
      {config.label}
    </Badge>
  );
}

// Session-specific badge that maps is_paused to status
interface SessionStatusBadgeProps {
  isPaused: boolean;
  className?: string;
}

export function SessionStatusBadge({ isPaused, className }: SessionStatusBadgeProps) {
  return (
    <StatusBadge
      status={isPaused ? 'paused' : 'active'}
      className={className}
    />
  );
}
