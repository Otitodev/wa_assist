'use client';

import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { MessageSquare, Bot, User, AlertCircle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

interface TimelineEvent {
  id: string | number;
  type: 'inbound' | 'outbound' | 'ai_reply' | 'system';
  text: string | null;
  timestamp: string;
  from_me?: boolean;
}

interface TimelineProps {
  events: TimelineEvent[];
  loading?: boolean;
  emptyMessage?: string;
}

const eventConfig = {
  inbound: {
    icon: MessageSquare,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/25',
    label: 'Customer',
  },
  outbound: {
    icon: User,
    color: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/25',
    label: 'Owner',
  },
  ai_reply: {
    icon: Bot,
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/25',
    label: 'AI',
  },
  system: {
    icon: AlertCircle,
    color: 'text-zinc-400',
    bgColor: 'bg-zinc-500/10',
    borderColor: 'border-zinc-500/25',
    label: 'System',
  },
};

export function Timeline({ events, loading = false, emptyMessage = 'No messages yet' }: TimelineProps) {
  if (loading) {
    return <TimelineSkeleton />;
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {events.map((event) => {
        const config = eventConfig[event.type];
        const Icon = config.icon;

        return (
          <div
            key={event.id}
            className={cn(
              'flex gap-4 p-4 rounded-lg border',
              config.bgColor,
              config.borderColor
            )}
          >
            <div className={cn('flex-shrink-0 mt-1', config.color)}>
              <Icon className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={cn('text-sm font-medium', config.color)}>
                  {config.label}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                </span>
              </div>
              <p className="text-sm text-foreground whitespace-pre-wrap break-words">
                {event.text || <span className="text-muted-foreground italic">[No text content]</span>}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TimelineSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-4 p-4 rounded-lg border">
          <Skeleton className="h-5 w-5 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

// Helper to convert Message to TimelineEvent
export function messageToTimelineEvent(message: {
  id: number;
  from_me: boolean;
  text: string | null;
  created_at: string;
  raw?: Record<string, unknown>;
}): TimelineEvent {
  let type: TimelineEvent['type'] = 'inbound';

  if (message.from_me) {
    // Check if it's an AI reply by looking at raw data
    const isAiGenerated = message.raw?.generated === true;
    type = isAiGenerated ? 'ai_reply' : 'outbound';
  }

  return {
    id: message.id,
    type,
    text: message.text,
    timestamp: message.created_at,
    from_me: message.from_me,
  };
}
