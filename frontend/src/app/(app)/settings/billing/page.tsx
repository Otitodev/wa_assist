'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { billingApi } from '@/lib/api';
import type { Subscription, Plan } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Loader2, CheckCircle2, XCircle, Zap, Building2, Rocket, Star } from 'lucide-react';

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <Zap className="h-5 w-5 text-muted-foreground" />,
  starter: <Star className="h-5 w-5 text-blue-400" />,
  growth: <Rocket className="h-5 w-5 text-green-400" />,
  agency: <Building2 className="h-5 w-5 text-purple-400" />,
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500/10 text-green-400 border-green-500/30',
  past_due: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  cancelled: 'bg-red-500/10 text-red-400 border-red-500/30',
  paused: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
};

const PAYSTACK_PAYMENT_LINKS: Record<string, { ngn: string; usd: string }> = {
  starter: { ngn: '#', usd: '#' },
  growth: { ngn: '#', usd: '#' },
  agency: { ngn: '#', usd: '#' },
};

// Static fallback plans shown when the DB tables aren't set up yet
const STATIC_PLANS: Plan[] = [
  { id: 1, name: 'free',    display_name: 'Free',    price_usd: 0,   price_ngn: 0,      price_usd_annual: 0,     price_ngn_annual: 0,     max_instances: 1,  max_conversations_per_month: 100,   features: { typing_indicator: false, media_processing: false, context_memory: false, analytics: false } },
  { id: 2, name: 'starter', display_name: 'Starter', price_usd: 29,  price_ngn: 15000,  price_usd_annual: 23.20, price_ngn_annual: 12000, max_instances: 2,  max_conversations_per_month: 1000,  features: { typing_indicator: true,  media_processing: false, context_memory: true,  analytics: true  } },
  { id: 3, name: 'growth',  display_name: 'Growth',  price_usd: 79,  price_ngn: 45000,  price_usd_annual: 63.20, price_ngn_annual: 36000, max_instances: 5,  max_conversations_per_month: 5000,  features: { typing_indicator: true,  media_processing: true,  context_memory: true,  analytics: true  } },
  { id: 4, name: 'agency',  display_name: 'Agency',  price_usd: 199, price_ngn: 120000, price_usd_annual: 159.20,price_ngn_annual: 96000, max_instances: -1, max_conversations_per_month: 25000, features: { typing_indicator: true,  media_processing: true,  context_memory: true,  analytics: true, white_label: true, priority_support: true } },
];

const FREE_SUB_FALLBACK: Subscription = {
  plan_name: 'free',
  plan_display_name: 'Free',
  status: 'active',
  billing_cycle: 'monthly',
  currency: 'USD',
  processor: 'free',
  max_instances: 1,
  max_conversations_per_month: 100,
  conversations_used: 0,
  conversations_remaining: 100,
  current_period_end: null,
  cancel_at_period_end: false,
  features: { typing_indicator: false, media_processing: false, context_memory: false, analytics: false },
};

export default function BillingPage() {
  const { activeTenant } = useAuth();
  const [sub, setSub] = useState<Subscription>(FREE_SUB_FALLBACK);
  const [plans, setPlans] = useState<Plan[]>(STATIC_PLANS);
  const [loading, setLoading] = useState(true);
  const [dbReady, setDbReady] = useState(true);
  const [currency, setCurrency] = useState<'USD' | 'NGN'>('USD');
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly');

  useEffect(() => {
    if (!activeTenant?.tenant_id) { setLoading(false); return; }
    // Fetch independently so one failure doesn't block the other
    billingApi.listPlans()
      .then((p) => { if (p.length > 0) setPlans(p); })
      .catch(() => setDbReady(false));
    billingApi.getSubscription(activeTenant.tenant_id)
      .then((s) => { setSub(s); if (s.currency === 'NGN') setCurrency('NGN'); })
      .catch(() => { /* no subscription yet — keep Free fallback */ })
      .finally(() => setLoading(false));
  }, [activeTenant?.tenant_id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const usagePct =
    sub && sub.max_conversations_per_month > 0
      ? Math.min(100, Math.round((sub.conversations_used / sub.max_conversations_per_month) * 100))
      : 0;

  const isUnlimited = sub?.max_conversations_per_month === -1;
  const isNearLimit = usagePct >= 80 && !isUnlimited;
  const isAtLimit = usagePct >= 100 && !isUnlimited;

  function formatPrice(plan: Plan) {
    if (currency === 'NGN') {
      const price = billing === 'annual' ? plan.price_ngn_annual : plan.price_ngn;
      return `₦${price.toLocaleString()}/mo`;
    }
    const price = billing === 'annual' ? plan.price_usd_annual : plan.price_usd;
    return price === 0 ? 'Free' : `$${price}/mo`;
  }

  function getUpgradeLink(plan: Plan) {
    const links = PAYSTACK_PAYMENT_LINKS[plan.name];
    if (!links) return null;
    return currency === 'NGN' ? links.ngn : links.usd;
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Billing & Subscription</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Manage your plan and usage
        </p>
      </div>

      {/* Setup banner — shown when billing DB tables not yet created */}
      {!dbReady && (
        <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-300">
          <strong>Setup required:</strong> Run{' '}
          <code className="font-mono text-xs bg-yellow-500/20 px-1 rounded">database/migrations/003_billing.sql</code>{' '}
          in your Supabase SQL Editor to enable live billing data. Plan prices below are previews.
        </div>
      )}

      {/* Current Plan Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {PLAN_ICONS[sub.plan_name] ?? <Zap className="h-5 w-5" />}
              <div>
                <CardTitle className="text-lg">{sub.plan_display_name} Plan</CardTitle>
                <CardDescription>
                  {sub.processor === 'free'
                    ? 'No payment method on file'
                    : `Billed ${sub.billing_cycle} via ${sub.processor}`}
                </CardDescription>
              </div>
            </div>
            <Badge className={`border ${STATUS_COLORS[sub.status] ?? ''}`}>
              {sub.status.replace('_', ' ')}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Conversation Usage */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-muted-foreground">AI Conversations this month</span>
              <span className={isAtLimit ? 'text-red-400 font-medium' : isNearLimit ? 'text-yellow-400 font-medium' : ''}>
                {isUnlimited
                  ? `${sub.conversations_used} / Unlimited`
                  : `${sub.conversations_used} / ${sub.max_conversations_per_month.toLocaleString()}`}
              </span>
            </div>
            {!isUnlimited && (
              <Progress
                value={usagePct}
                className={`h-2 ${isAtLimit ? '[&>div]:bg-red-500' : isNearLimit ? '[&>div]:bg-yellow-500' : '[&>div]:bg-green-500'}`}
              />
            )}
            {isAtLimit && (
              <p className="text-xs text-red-400 mt-1">
                Conversation limit reached. AI replies are paused. Upgrade to continue.
              </p>
            )}
            {isNearLimit && !isAtLimit && (
              <p className="text-xs text-yellow-400 mt-1">
                You&apos;re approaching your monthly limit.
              </p>
            )}
          </div>

          {/* Limits grid */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">WhatsApp Instances</p>
              <p className="font-medium">
                {sub.max_instances === -1 ? 'Unlimited' : sub.max_instances}
              </p>
            </div>
            {sub.current_period_end && (
              <div>
                <p className="text-muted-foreground">Next renewal</p>
                <p className="font-medium">
                  {new Date(sub.current_period_end).toLocaleDateString()}
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Plan Selection */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Available Plans</h2>
          <div className="flex items-center gap-2">
            {/* Currency Toggle */}
            <div className="flex rounded-md border overflow-hidden text-sm">
              <button
                onClick={() => setCurrency('USD')}
                className={`px-3 py-1.5 ${currency === 'USD' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                USD
              </button>
              <button
                onClick={() => setCurrency('NGN')}
                className={`px-3 py-1.5 ${currency === 'NGN' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                NGN
              </button>
            </div>
            {/* Billing cycle toggle */}
            <div className="flex rounded-md border overflow-hidden text-sm">
              <button
                onClick={() => setBilling('monthly')}
                className={`px-3 py-1.5 ${billing === 'monthly' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBilling('annual')}
                className={`px-3 py-1.5 ${billing === 'annual' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                Annual <span className="text-green-400 text-xs ml-1">-20%</span>
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map((plan) => {
            const isCurrent = sub?.plan_name === plan.name;
            const isUpgrade = plans.findIndex(p => p.name === plan.name) >
              plans.findIndex(p => p.name === sub?.plan_name);
            const upgradeLink = getUpgradeLink(plan);

            return (
              <Card
                key={plan.id}
                className={`relative flex flex-col ${isCurrent ? 'border-green-500/50 bg-green-500/5' : ''}`}
              >
                {isCurrent && (
                  <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                    <Badge className="bg-green-500 text-white text-xs">Current</Badge>
                  </div>
                )}
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    {PLAN_ICONS[plan.name]}
                    <CardTitle className="text-base">{plan.display_name}</CardTitle>
                  </div>
                  <p className="text-2xl font-bold mt-1">{formatPrice(plan)}</p>
                  {billing === 'annual' && plan.price_usd > 0 && (
                    <p className="text-xs text-green-400">Save 20% annually</p>
                  )}
                </CardHeader>
                <CardContent className="flex flex-col flex-1 gap-3">
                  <ul className="space-y-1.5 text-sm flex-1">
                    <li className="flex items-center gap-2 text-muted-foreground">
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
                      {plan.max_instances === -1 ? 'Unlimited instances' : `${plan.max_instances} instance${plan.max_instances > 1 ? 's' : ''}`}
                    </li>
                    <li className="flex items-center gap-2 text-muted-foreground">
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
                      {plan.max_conversations_per_month === -1
                        ? 'Unlimited conversations'
                        : `${plan.max_conversations_per_month.toLocaleString()} conversations/mo`}
                    </li>
                    {Object.entries(plan.features).map(([key, enabled]) => (
                      <li key={key} className="flex items-center gap-2 text-muted-foreground">
                        {enabled
                          ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
                          : <XCircle className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />}
                        {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </li>
                    ))}
                  </ul>

                  {!isCurrent && isUpgrade && upgradeLink && upgradeLink !== '#' ? (
                    <Button size="sm" asChild>
                      <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
                        Upgrade to {plan.display_name}
                      </a>
                    </Button>
                  ) : !isCurrent && isUpgrade ? (
                    <Button size="sm" disabled variant="outline">
                      Coming soon
                    </Button>
                  ) : isCurrent ? (
                    <Button size="sm" variant="outline" disabled>
                      Current plan
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Contact for enterprise */}
      <Card className="bg-muted/30">
        <CardContent className="flex items-center justify-between py-4">
          <div>
            <p className="font-medium">Need unlimited scale or white-label?</p>
            <p className="text-sm text-muted-foreground">
              Enterprise plans with custom limits, SLA, and dedicated support are available.
            </p>
          </div>
          <Button variant="outline" size="sm" asChild>
            <a href="mailto:sales@whaply.co">Contact Sales</a>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
