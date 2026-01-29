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
    label: 'Active',
    className: 'bg-green-500 hover:bg-green-600 text-white border-green-500',
    variant: 'default',
  },
  paused: {
    label: 'Paused',
    className: 'border-orange-500 text-orange-600 bg-orange-50 hover:bg-orange-100',
    variant: 'outline',
  },
  error: {
    label: 'Error',
    className: 'bg-red-500 hover:bg-red-600 text-white border-red-500',
    variant: 'destructive',
  },
  connecting: {
    label: 'Connecting',
    className: 'bg-gray-400 hover:bg-gray-500 text-white border-gray-400',
    variant: 'secondary',
  },
  disconnected: {
    label: 'Disconnected',
    className: 'bg-gray-200 text-gray-600 border-gray-300',
    variant: 'secondary',
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
