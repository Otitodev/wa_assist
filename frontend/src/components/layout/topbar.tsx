'use client';

import { useAuth } from '@/hooks/use-auth';
import { TenantSwitcher } from './tenant-switcher';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { LogOut, User } from 'lucide-react';

export function Topbar() {
  const { user, logout } = useAuth();

  // Safely compute initials
  const getInitials = (): string => {
    if (user?.display_name) {
      const parts = user.display_name.split(' ').filter(Boolean);
      if (parts.length > 0) {
        return parts.map((n) => n[0]).join('').toUpperCase().slice(0, 2);
      }
    }
    if (user?.email) {
      return user.email[0].toUpperCase();
    }
    return '?';
  };
  const initials = getInitials();

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      {/* Left side - Tenant Switcher */}
      <TenantSwitcher />

      {/* Right side - User Menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-10 w-10 rounded-full">
            <Avatar className="h-10 w-10">
              <AvatarFallback className="bg-green-500/15 text-green-400">
                {initials}
              </AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end" forceMount>
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">
                {user?.display_name || 'User'}
              </p>
              <p className="text-xs leading-none text-muted-foreground">
                {user?.email || 'No email'}
              </p>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <a href="/settings" className="flex items-center">
              <User className="mr-2 h-4 w-4" />
              Settings
            </a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-red-600">
            <LogOut className="mr-2 h-4 w-4" />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
