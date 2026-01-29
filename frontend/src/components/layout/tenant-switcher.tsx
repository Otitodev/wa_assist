'use client';

import { useAuth } from '@/hooks/use-auth';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Server } from 'lucide-react';

export function TenantSwitcher() {
  const { tenants, activeTenant, setActiveTenant } = useAuth();

  // Ensure tenants is an array and filter out invalid entries
  const tenantList = (Array.isArray(tenants) ? tenants : []).filter(
    (t) => t && t.tenant_id !== undefined && t.tenant_id !== null
  );

  if (tenantList.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Server className="h-4 w-4" />
        <span>No instances</span>
      </div>
    );
  }

  if (tenantList.length === 1) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Server className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">{tenantList[0]?.tenant?.instance_name || 'Instance'}</span>
      </div>
    );
  }

  // Get current value safely - must not be empty string for Select
  const currentValue = activeTenant?.tenant_id?.toString() || tenantList[0]?.tenant_id?.toString() || 'default';

  return (
    <Select
      value={currentValue}
      onValueChange={(value) => {
        if (value && value !== 'default') {
          const tenant = tenantList.find((t) => t.tenant_id?.toString() === value);
          if (tenant) {
            setActiveTenant(tenant);
          }
        }
      }}
    >
      <SelectTrigger className="w-[200px]">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4" />
          <SelectValue placeholder="Select instance" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {tenantList.map((tenant, index) => {
          const value = tenant.tenant_id?.toString() || `tenant-${index}`;
          return (
            <SelectItem
              key={`tenant-${tenant.tenant_id || index}`}
              value={value}
            >
              <div className="flex flex-col">
                <span>{tenant.tenant?.instance_name || 'Unknown'}</span>
                <span className="text-xs text-muted-foreground capitalize">
                  {tenant.role || 'member'}
                </span>
              </div>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
