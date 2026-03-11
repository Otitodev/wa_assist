'use client';

import { useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, XCircle, Zap, Star, Rocket, Building2, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const PLANS = [
  {
    name: 'free',
    label: 'Free',
    icon: <Zap className="h-6 w-6 text-muted-foreground" />,
    usd: 0,
    ngn: 0,
    usdAnnual: 0,
    ngnAnnual: 0,
    maxInstances: 1,
    maxConvos: 100,
    features: [
      { label: '1 WhatsApp instance', included: true },
      { label: '100 AI conversations/month', included: true },
      { label: 'Collision detection (Invisible Mute)', included: true },
      { label: '7-day message history', included: true },
      { label: 'Typing indicators', included: false },
      { label: 'Media processing (images/audio)', included: false },
      { label: 'Conversation memory', included: false },
      { label: 'Analytics dashboard', included: false },
      { label: 'Priority support', included: false },
    ],
    cta: 'Get Started Free',
    ctaHref: '/register',
    highlight: false,
  },
  {
    name: 'starter',
    label: 'Starter',
    icon: <Star className="h-6 w-6 text-blue-400" />,
    usd: 29,
    ngn: 15000,
    usdAnnual: 23.20,
    ngnAnnual: 12000,
    maxInstances: 2,
    maxConvos: 1000,
    features: [
      { label: '2 WhatsApp instances', included: true },
      { label: '1,000 AI conversations/month', included: true },
      { label: 'Collision detection (Invisible Mute)', included: true },
      { label: 'Full message history', included: true },
      { label: 'Typing indicators', included: true },
      { label: 'Media processing (images/audio)', included: false },
      { label: 'Conversation memory', included: true },
      { label: 'Analytics dashboard', included: true },
      { label: 'Priority support', included: false },
    ],
    cta: 'Start Starter',
    ctaHref: '/register',
    highlight: false,
  },
  {
    name: 'growth',
    label: 'Growth',
    icon: <Rocket className="h-6 w-6 text-green-400" />,
    usd: 79,
    ngn: 45000,
    usdAnnual: 63.20,
    ngnAnnual: 36000,
    maxInstances: 5,
    maxConvos: 5000,
    features: [
      { label: '5 WhatsApp instances', included: true },
      { label: '5,000 AI conversations/month', included: true },
      { label: 'Collision detection (Invisible Mute)', included: true },
      { label: 'Full message history', included: true },
      { label: 'Typing indicators', included: true },
      { label: 'Media processing (images/audio)', included: true },
      { label: 'Conversation memory', included: true },
      { label: 'Analytics dashboard', included: true },
      { label: 'Priority support', included: false },
    ],
    cta: 'Start Growth',
    ctaHref: '/register',
    highlight: true, // most popular
  },
  {
    name: 'agency',
    label: 'Agency',
    icon: <Building2 className="h-6 w-6 text-purple-400" />,
    usd: 199,
    ngn: 120000,
    usdAnnual: 159.20,
    ngnAnnual: 96000,
    maxInstances: -1,
    maxConvos: 25000,
    features: [
      { label: 'Unlimited WhatsApp instances', included: true },
      { label: '25,000 AI conversations/month', included: true },
      { label: 'Collision detection (Invisible Mute)', included: true },
      { label: 'Full message history', included: true },
      { label: 'Typing indicators', included: true },
      { label: 'Media processing (images/audio)', included: true },
      { label: 'Conversation memory', included: true },
      { label: 'Analytics dashboard', included: true },
      { label: 'Priority support', included: true },
    ],
    cta: 'Start Agency',
    ctaHref: '/register',
    highlight: false,
  },
];

const FAQ = [
  {
    q: 'What counts as a conversation?',
    a: 'One conversation = one AI reply sent. Inbound messages from customers don\'t count. The counter resets on the 1st of each month.',
  },
  {
    q: 'Can I switch plans anytime?',
    a: 'Yes. Upgrade instantly. Downgrades take effect at the end of your billing period.',
  },
  {
    q: 'What happens when I hit my limit?',
    a: 'AI replies pause for the rest of the month. Your data and settings are preserved. Upgrade anytime to resume.',
  },
  {
    q: 'Do you support NGN payments?',
    a: 'Yes — Nigerian customers can pay in Naira via Paystack (card, bank transfer, or USSD). International customers pay in USD.',
  },
  {
    q: 'Is there a free trial for paid plans?',
    a: 'The Free plan is permanent and gives you 100 conversations/month to test. Paid plans don\'t need a trial — start with Free and upgrade when ready.',
  },
  {
    q: 'Can I use Whaply for multiple businesses?',
    a: 'Yes. Each WhatsApp instance is a separate tenant. The Agency plan gives unlimited instances — perfect for agencies managing multiple clients.',
  },
];

export default function PricingPage() {
  const [currency, setCurrency] = useState<'USD' | 'NGN'>('USD');
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly');

  function price(plan: typeof PLANS[0]) {
    if (currency === 'NGN') {
      const p = billing === 'annual' ? plan.ngnAnnual : plan.ngn;
      return p === 0 ? 'Free' : `₦${p.toLocaleString()}/mo`;
    }
    const p = billing === 'annual' ? plan.usdAnnual : plan.usd;
    return p === 0 ? 'Free' : `$${p}/mo`;
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <nav className="border-b px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg">
          <MessageSquare className="h-5 w-5 text-green-500" />
          Whaply
        </Link>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">Sign in</Link>
          <Button size="sm" asChild>
            <Link href="/register">Get started free</Link>
          </Button>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-16 space-y-16">
        {/* Hero */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">Simple, honest pricing</h1>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Start free. Upgrade when your conversations grow. No hidden fees — you pay for AI replies, not messages received.
          </p>

          {/* Toggles */}
          <div className="flex items-center justify-center gap-3 pt-2">
            <div className="flex rounded-lg border overflow-hidden text-sm">
              <button
                onClick={() => setBilling('monthly')}
                className={`px-4 py-2 ${billing === 'monthly' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBilling('annual')}
                className={`px-4 py-2 flex items-center gap-1.5 ${billing === 'annual' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                Annual
                <span className={`text-xs font-medium ${billing === 'annual' ? 'text-green-300' : 'text-green-500'}`}>-20%</span>
              </button>
            </div>

            <div className="flex rounded-lg border overflow-hidden text-sm">
              <button
                onClick={() => setCurrency('USD')}
                className={`px-4 py-2 ${currency === 'USD' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                $ USD
              </button>
              <button
                onClick={() => setCurrency('NGN')}
                className={`px-4 py-2 ${currency === 'NGN' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
              >
                ₦ NGN
              </button>
            </div>
          </div>
        </div>

        {/* Plans grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`relative flex flex-col rounded-xl border p-6 ${
                plan.highlight
                  ? 'border-green-500/60 bg-green-500/5 shadow-lg shadow-green-500/10'
                  : 'border-border bg-card'
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-green-500 text-white px-3">Most Popular</Badge>
                </div>
              )}

              <div className="flex items-center gap-2 mb-4">
                {plan.icon}
                <span className="font-semibold text-lg">{plan.label}</span>
              </div>

              <div className="mb-6">
                <span className="text-3xl font-bold">{price(plan)}</span>
                {plan.usd > 0 && billing === 'annual' && (
                  <p className="text-xs text-green-400 mt-0.5">
                    Billed {currency === 'NGN'
                      ? `₦${(plan.ngnAnnual * 12).toLocaleString()}/yr`
                      : `$${(plan.usdAnnual * 12).toFixed(0)}/yr`}
                  </p>
                )}
              </div>

              <ul className="space-y-2.5 flex-1 mb-6">
                {plan.features.map((f) => (
                  <li key={f.label} className="flex items-start gap-2 text-sm">
                    {f.included
                      ? <CheckCircle2 className="h-4 w-4 text-green-400 shrink-0 mt-0.5" />
                      : <XCircle className="h-4 w-4 text-muted-foreground/30 shrink-0 mt-0.5" />}
                    <span className={f.included ? 'text-foreground' : 'text-muted-foreground/50'}>
                      {f.label}
                    </span>
                  </li>
                ))}
              </ul>

              <Button
                asChild
                variant={plan.highlight ? 'default' : 'outline'}
                className={plan.highlight ? 'bg-green-600 hover:bg-green-700' : ''}
              >
                <Link href={plan.ctaHref}>{plan.cta}</Link>
              </Button>
            </div>
          ))}
        </div>

        {/* Overage note */}
        <p className="text-center text-sm text-muted-foreground">
          Exceeded your monthly limit? Additional conversations are $0.05 each — or upgrade for the next tier&apos;s pricing.
        </p>

        {/* Enterprise CTA */}
        <div className="rounded-xl border bg-muted/30 p-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">Need more? Enterprise plan available.</h2>
            <p className="text-muted-foreground mt-1">
              Custom limits, white-label, dedicated infrastructure, SLA — for agencies and large businesses.
            </p>
          </div>
          <Button variant="outline" size="lg" asChild>
            <a href="mailto:sales@whaply.co">Contact Sales</a>
          </Button>
        </div>

        {/* FAQ */}
        <div>
          <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
          <div className="grid sm:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {FAQ.map((faq) => (
              <div key={faq.q} className="space-y-2">
                <h3 className="font-semibold">{faq.q}</h3>
                <p className="text-sm text-muted-foreground">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t py-8 text-center text-sm text-muted-foreground">
        <p>© {new Date().getFullYear()} Whaply. All rights reserved.</p>
        <p className="mt-1">
          <Link href="/login" className="hover:text-foreground">Sign in</Link>
          {' · '}
          <a href="mailto:sales@whaply.co" className="hover:text-foreground">Contact</a>
        </p>
      </footer>
    </div>
  );
}
