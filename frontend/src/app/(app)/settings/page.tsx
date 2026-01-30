'use client';

import { useAuth } from '@/hooks/use-auth';
import { privacyApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Copy, Check, User, Server, Shield, Download, Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

export default function SettingsPage() {
  const { user, activeTenant, tenants } = useAuth();
  const [copied, setCopied] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleExportData = async () => {
    setExporting(true);
    try {
      const data = await privacyApi.exportData();

      // Create downloadable JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hybridflow-data-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success('Your data has been exported');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export data');
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAllData = async () => {
    setDeleting(true);
    try {
      const result = await privacyApi.deleteAllData(true);
      toast.success(result.message);
      // Redirect to login after deletion
      window.location.href = '/login';
    } catch (error) {
      console.error('Deletion failed:', error);
      toast.error('Failed to delete data');
    } finally {
      setDeleting(false);
    }
  };

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const webhookUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/webhooks/evolution`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and instance settings
        </p>
      </div>

      {/* Account Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Account
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Display Name</p>
            <p className="text-sm">{user?.display_name || 'Not set'}</p>
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium text-muted-foreground">Email</p>
            <p className="text-sm">{user?.email}</p>
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium text-muted-foreground">User ID</p>
            <p className="text-sm font-mono">{user?.id}</p>
          </div>
        </CardContent>
      </Card>

      {/* Active Connection */}
      {activeTenant && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Active WhatsApp
            </CardTitle>
            <CardDescription>
              Currently selected WhatsApp connection
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Connection Name</p>
              <p className="text-sm font-mono">{activeTenant?.tenant?.instance_name || 'N/A'}</p>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Your Role</p>
              <Badge variant="outline" className="capitalize mt-1">
                {activeTenant?.role || 'member'}
              </Badge>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Webhook URL</p>
              <p className="text-sm text-muted-foreground mb-2">
                Use this URL in Evolution API settings
              </p>
              <div className="flex items-center gap-2">
                <code className="text-sm bg-muted px-3 py-2 rounded flex-1 truncate">
                  {webhookUrl}
                </code>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => handleCopy(webhookUrl, 'webhook')}
                >
                  {copied === 'webhook' ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <Separator />

            <div>
              <p className="text-sm font-medium text-muted-foreground">Evolution Server</p>
              <p className="text-sm font-mono">
                {activeTenant?.tenant?.evo_server_url || 'Not configured'}
              </p>
            </div>

          </CardContent>
        </Card>
      )}

      {/* All Connections */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Your WhatsApp Connections
          </CardTitle>
          <CardDescription>
            All WhatsApp numbers you have access to
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!tenants || tenants.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No WhatsApp numbers connected
            </p>
          ) : (
            <div className="space-y-3">
              {tenants.map((membership) => (
                <div
                  key={membership.tenant_id || membership.tenant?.id}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div>
                    <p className="font-medium">{membership.tenant?.instance_name || 'Connection'}</p>
                    <p className="text-sm text-muted-foreground">
                      {membership.tenant?.evo_server_url || 'N/A'}
                    </p>
                  </div>
                  <Badge variant="outline" className="capitalize">
                    {membership.role || 'member'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* API Information */}
      <Card>
        <CardHeader>
          <CardTitle>API Information</CardTitle>
          <CardDescription>
            Backend API connection details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">API URL</p>
            <p className="text-sm font-mono">
              {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Privacy & Data */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Privacy & Data
          </CardTitle>
          <CardDescription>
            Manage your personal data and privacy settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium">Export Your Data</p>
            <p className="text-sm text-muted-foreground mb-3">
              Download a copy of all your personal data including messages,
              sessions, and account information.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportData}
              disabled={exporting}
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              {exporting ? 'Exporting...' : 'Export Data'}
            </Button>
          </div>

          <Separator />

          <div>
            <p className="text-sm font-medium text-red-600">Delete All Data</p>
            <p className="text-sm text-muted-foreground mb-3">
              Permanently delete all your data including messages, conversations,
              and WhatsApp connections. This action cannot be undone.
            </p>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={deleting}>
                  {deleting ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4 mr-2" />
                  )}
                  Delete All Data
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    Delete All Your Data?
                  </AlertDialogTitle>
                  <AlertDialogDescription className="space-y-2">
                    <p>
                      This will permanently delete:
                    </p>
                    <ul className="list-disc list-inside text-sm space-y-1">
                      <li>All your WhatsApp connections</li>
                      <li>All conversation messages</li>
                      <li>All session history</li>
                      <li>Your account settings</li>
                    </ul>
                    <p className="font-medium text-red-600 mt-2">
                      This action cannot be undone!
                    </p>
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDeleteAllData}
                    className="bg-red-600 hover:bg-red-700"
                  >
                    Yes, Delete Everything
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          <Separator />

          <div className="text-xs text-muted-foreground space-y-1">
            <p>
              <strong>Data Retention:</strong> Messages are automatically deleted after 90 days.
            </p>
            <p>
              <strong>Your Rights:</strong> You have the right to access, export, and delete
              your personal data at any time under GDPR.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
