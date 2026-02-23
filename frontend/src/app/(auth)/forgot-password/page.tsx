'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { authClient } from '@/lib/auth-client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { ArrowLeft, Mail } from 'lucide-react';
import { getErrorMessage } from '@/lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await authClient.requestPasswordReset({
        email,
        redirectTo: '/reset-password',
      });

      if (result.error) {
        toast.error(result.error.message ?? 'Failed to send reset email');
        return;
      }

      setSent(true);
    } catch (error) {
      console.error('Forgot password failed:', error);
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-950/40 to-background p-4">
      <div className="w-full max-w-md flex flex-col">
        {/* Back link */}
        <Link
          href="/login"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4 self-start transition-colors"
        >
          <ArrowLeft size={14} /> Back to sign in
        </Link>

        <Card>
          <CardHeader className="space-y-1">
            <div className="flex items-center gap-2 mb-4">
              <Image
                src="/logo.png"
                alt="HybridFlow"
                width={40}
                height={40}
                className="rounded-lg"
              />
              <span className="text-2xl font-bold">HybridFlow</span>
            </div>
            <CardTitle className="text-2xl">Forgot password</CardTitle>
            <CardDescription>
              Enter your email and we&apos;ll send you a reset link
            </CardDescription>
          </CardHeader>

          {sent ? (
            /* Success state */
            <CardContent className="space-y-4 text-center py-6">
              <div className="flex justify-center">
                <div className="rounded-full bg-green-500/10 border border-green-500/30 p-4">
                  <Mail className="h-8 w-8 text-green-400" />
                </div>
              </div>
              <div className="space-y-1">
                <p className="font-medium">Check your inbox</p>
                <p className="text-sm text-muted-foreground">
                  If <span className="text-foreground">{email}</span> is registered,
                  you&apos;ll receive a password reset link shortly.
                </p>
              </div>
              <p className="text-xs text-muted-foreground pt-2">
                Didn&apos;t receive it? Check spam or{' '}
                <button
                  type="button"
                  onClick={() => setSent(false)}
                  className="text-green-400 hover:underline"
                >
                  try again
                </button>
                .
              </p>
            </CardContent>
          ) : (
            /* Email form */
            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
              </CardContent>
              <CardFooter className="flex flex-col space-y-4">
                <Button
                  type="submit"
                  className="w-full bg-green-600 hover:bg-green-700"
                  disabled={loading}
                >
                  {loading ? 'Sending...' : 'Send reset link'}
                </Button>
              </CardFooter>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}
