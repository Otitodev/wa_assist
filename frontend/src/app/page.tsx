import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import {
  Shield, Timer, Brain, LayoutDashboard, Building2, Lock,
  X, Check, ArrowRight,
} from 'lucide-react';

export const metadata: Metadata = {
  title: 'HybridFlow — WhatsApp AI That Knows When to Step Aside',
  description: 'AI handles your WhatsApp conversations. You step in when needed. Zero conflicts, zero missed messages.',
};

export default function LandingPage() {
  return (
    <>
      <style>{`
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
          --bg:#060b06; --bg2:#0c150c; --bg3:#111d11;
          --card:rgba(255,255,255,0.03); --border:rgba(34,197,94,0.15); --border-hi:rgba(34,197,94,0.4);
          --green:#16a34a; --green-hi:#22c55e; --green-xl:#4ade80;
          --glow:rgba(34,197,94,0.12); --text:#f0fdf4; --text-2:#bbf7d0; --text-3:#6b7280;
          --font-display:'Syne',sans-serif; --font-body:'DM Sans',sans-serif; --font-mono:'JetBrains Mono',monospace;
          --radius:16px; --radius-sm:10px;
        }
        html { scroll-behavior:smooth; }
        body { font-family:var(--font-body); background:var(--bg); color:var(--text); line-height:1.6; overflow-x:hidden; }
        body::before {
          content:''; position:fixed; inset:0;
          background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
          opacity:0.035; pointer-events:none; z-index:999;
        }
        .mesh { position:absolute; inset:0; background:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(22,163,74,0.18) 0%,transparent 70%),radial-gradient(ellipse 40% 40% at 80% 30%,rgba(34,197,94,0.07) 0%,transparent 60%),radial-gradient(ellipse 30% 50% at 10% 60%,rgba(22,163,74,0.06) 0%,transparent 60%); pointer-events:none; }
        .grid-lines { position:absolute; inset:0; background-image:linear-gradient(rgba(34,197,94,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(34,197,94,0.04) 1px,transparent 1px); background-size:60px 60px; mask-image:radial-gradient(ellipse 80% 80% at 50% 50%,black 30%,transparent 100%); pointer-events:none; }
        nav { position:fixed; top:0; left:0; right:0; z-index:100; display:flex; align-items:center; justify-content:space-between; padding:0 clamp(1.5rem,5vw,4rem); height:68px; background:rgba(6,11,6,0.85); backdrop-filter:blur(20px); border-bottom:1px solid var(--border); }
        .nav-logo { display:flex; align-items:center; gap:10px; text-decoration:none; color:var(--text); }
        .nav-logo span { font-family:var(--font-display); font-weight:700; font-size:1.1rem; letter-spacing:-0.02em; }
        .nav-links { display:flex; align-items:center; gap:2rem; list-style:none; }
        .nav-links a { color:var(--text-3); text-decoration:none; font-size:0.875rem; transition:color .2s; }
        .nav-links a:hover { color:var(--text); }
        .nav-cta { display:flex; gap:10px; align-items:center; }
        .btn { display:inline-flex; align-items:center; gap:8px; padding:9px 20px; border-radius:8px; font-family:var(--font-body); font-size:0.875rem; font-weight:500; text-decoration:none; cursor:pointer; border:none; transition:all .2s; }
        .btn-ghost { background:transparent; color:var(--text-3); border:1px solid var(--border); }
        .btn-ghost:hover { border-color:var(--border-hi); color:var(--text); }
        .btn-primary { background:var(--green); color:white; }
        .btn-primary:hover { background:#15803d; box-shadow:0 0 24px rgba(22,163,74,0.35); transform:translateY(-1px); }
        .btn-xl { padding:16px 36px; font-size:1.05rem; border-radius:var(--radius-sm); }
        @media(max-width:768px){.nav-links{display:none;}}
        #hero { position:relative; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:120px clamp(1.5rem,5vw,4rem) 80px; overflow:hidden; }
        .hero-badge { display:inline-flex; align-items:center; gap:8px; padding:6px 14px; background:rgba(22,163,74,0.1); border:1px solid rgba(22,163,74,0.3); border-radius:999px; font-size:0.8rem; font-weight:500; color:var(--green-xl); margin-bottom:2rem; animation:fadeUp .6s ease both; }
        .dot { width:6px; height:6px; border-radius:50%; background:var(--green-hi); animation:pulse-dot 2s ease infinite; }
        @keyframes pulse-dot { 0%,100%{opacity:1;transform:scale(1);} 50%{opacity:0.5;transform:scale(0.7);} }
        h1 { font-family:var(--font-display); font-size:clamp(2.8rem,7vw,6.5rem); font-weight:800; line-height:1.0; letter-spacing:-0.04em; max-width:900px; animation:fadeUp .7s .1s ease both; }
        .line-green { background:linear-gradient(135deg,var(--green-hi) 0%,var(--green-xl) 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .hero-sub { margin-top:1.5rem; font-size:clamp(1rem,2vw,1.2rem); color:var(--text-3); max-width:560px; line-height:1.7; font-weight:300; animation:fadeUp .7s .2s ease both; }
        .hero-ctas { margin-top:2.5rem; display:flex; gap:12px; flex-wrap:wrap; justify-content:center; animation:fadeUp .7s .3s ease both; }
        .hero-preview { margin-top:4rem; position:relative; max-width:860px; width:100%; animation:fadeUp .8s .4s ease both; }
        .preview-window { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; box-shadow:0 0 0 1px rgba(34,197,94,0.08),0 40px 80px rgba(0,0,0,0.6),0 0 120px rgba(22,163,74,0.08); }
        .preview-bar { display:flex; align-items:center; gap:8px; padding:12px 16px; border-bottom:1px solid var(--border); background:rgba(255,255,255,0.02); }
        .preview-dot { width:10px; height:10px; border-radius:50%; }
        .preview-dot.r{background:#ff5f57;} .preview-dot.y{background:#ffbd2e;} .preview-dot.g{background:#28c840;}
        .preview-url { flex:1; text-align:center; font-family:var(--font-mono); font-size:0.75rem; color:var(--text-3); }
        .preview-inner { display:grid; grid-template-columns:220px 1fr; min-height:280px; }
        .preview-sidebar { border-right:1px solid var(--border); padding:16px 12px; display:flex; flex-direction:column; gap:4px; }
        .preview-nav-item { padding:8px 12px; border-radius:8px; font-size:0.78rem; color:var(--text-3); display:flex; align-items:center; gap:8px; }
        .preview-nav-item.active { background:rgba(22,163,74,0.12); color:var(--green-xl); }
        .preview-nav-icon { width:16px; height:16px; border-radius:4px; background:currentColor; opacity:0.3; }
        .preview-main { padding:20px; }
        .preview-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px; }
        .preview-kpi { background:var(--card); border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px 14px; }
        .preview-kpi-val { font-family:var(--font-display); font-size:1.3rem; font-weight:700; color:var(--text); }
        .preview-kpi-val.green { color:var(--green-hi); }
        .preview-kpi-label { font-size:0.72rem; color:var(--text-3); margin-top:2px; }
        .preview-sessions { display:flex; flex-direction:column; gap:6px; }
        .preview-session-row { display:flex; align-items:center; gap:10px; padding:8px 10px; background:var(--card); border-radius:8px; border:1px solid var(--border); font-size:0.75rem; }
        .badge-active { padding:2px 8px; border-radius:999px; background:rgba(34,197,94,0.15); color:var(--green-xl); font-size:0.68rem; font-weight:500; }
        .badge-paused { padding:2px 8px; border-radius:999px; background:rgba(251,191,36,0.1); color:#fbbf24; font-size:0.68rem; font-weight:500; }
        .session-name { flex:1; color:var(--text-2); }
        .session-time { color:var(--text-3); }
        .preview-fade { position:absolute; bottom:0; left:0; right:0; height:120px; background:linear-gradient(to top,var(--bg),transparent); border-radius:0 0 var(--radius) var(--radius); pointer-events:none; }
        .logos-bar { padding:40px clamp(1.5rem,5vw,4rem); text-align:center; border-top:1px solid var(--border); border-bottom:1px solid var(--border); }
        .logos-bar p { font-size:0.78rem; color:var(--text-3); text-transform:uppercase; letter-spacing:0.12em; margin-bottom:1.5rem; }
        .logos-row { display:flex; align-items:center; justify-content:center; gap:clamp(2rem,5vw,5rem); flex-wrap:wrap; }
        .logo-item { font-family:var(--font-display); font-weight:700; font-size:1rem; color:var(--text-3); opacity:0.5; letter-spacing:-0.02em; }
        section { padding:clamp(4rem,8vw,8rem) clamp(1.5rem,5vw,4rem); max-width:1200px; margin:0 auto; }
        .section-full { max-width:none; background:var(--bg2); border-top:1px solid var(--border); border-bottom:1px solid var(--border); }
        .section-full>.section-inner { max-width:1200px; margin:0 auto; padding:clamp(4rem,8vw,8rem) clamp(1.5rem,5vw,4rem); }
        .section-tag { display:inline-block; font-family:var(--font-mono); font-size:0.75rem; color:var(--green-hi); margin-bottom:1rem; letter-spacing:0.08em; }
        h2 { font-family:var(--font-display); font-size:clamp(2rem,4vw,3.2rem); font-weight:800; line-height:1.1; letter-spacing:-0.03em; margin-bottom:1rem; }
        .section-sub { color:var(--text-3); font-size:1.05rem; max-width:560px; line-height:1.7; font-weight:300; }
        .ps-grid { display:grid; grid-template-columns:1fr 1fr; gap:2px; margin-top:3rem; border-radius:var(--radius); overflow:hidden; border:1px solid var(--border); }
        @media(max-width:768px){.ps-grid{grid-template-columns:1fr;}}
        .ps-card { padding:2.5rem; background:var(--card); }
        .ps-card.problem { background:rgba(239,68,68,0.03); }
        .ps-card.solution { background:rgba(22,163,74,0.04); }
        .ps-label { font-family:var(--font-mono); font-size:0.7rem; font-weight:500; letter-spacing:0.12em; text-transform:uppercase; margin-bottom:1.2rem; padding:4px 10px; border-radius:999px; display:inline-block; }
        .ps-card.problem .ps-label { background:rgba(239,68,68,0.1); color:#f87171; border:1px solid rgba(239,68,68,0.2); }
        .ps-card.solution .ps-label { background:rgba(22,163,74,0.1); color:var(--green-hi); border:1px solid rgba(22,163,74,0.25); }
        .ps-card h3 { font-family:var(--font-display); font-size:1.4rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:.75rem; }
        .ps-card p { color:var(--text-3); line-height:1.7; font-size:0.95rem; }
        .ps-list { list-style:none; margin-top:1.2rem; display:flex; flex-direction:column; gap:.6rem; }
        .ps-list li { display:flex; align-items:flex-start; gap:10px; font-size:0.9rem; color:var(--text-3); line-height:1.5; }
        .steps { display:grid; grid-template-columns:repeat(3,1fr); gap:2rem; margin-top:3rem; position:relative; }
        @media(max-width:768px){.steps{grid-template-columns:1fr;}}
        .steps::before { content:''; position:absolute; top:24px; left:calc(16.66% + 24px); right:calc(16.66% + 24px); height:1px; background:linear-gradient(90deg,var(--border-hi),var(--border),var(--border-hi)); }
        @media(max-width:768px){.steps::before{display:none;}}
        .step { display:flex; flex-direction:column; align-items:flex-start; }
        .step-num { width:48px; height:48px; border-radius:50%; border:1px solid var(--border-hi); background:var(--bg2); display:flex; align-items:center; justify-content:center; font-family:var(--font-display); font-weight:700; font-size:1rem; color:var(--green-hi); margin-bottom:1.5rem; position:relative; z-index:1; }
        .step h3 { font-family:var(--font-display); font-size:1.15rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:.5rem; }
        .step p { color:var(--text-3); font-size:0.9rem; line-height:1.65; }
        .step-mono { margin-top:1rem; font-family:var(--font-mono); font-size:0.72rem; color:var(--green-hi); opacity:0.7; background:rgba(22,163,74,0.06); border:1px solid rgba(22,163,74,0.15); padding:4px 10px; border-radius:6px; display:inline-block; }
        .features-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:1px; margin-top:3rem; border:1px solid var(--border); border-radius:var(--radius); overflow:hidden; }
        .feature-card { padding:2rem 2rem 2.2rem; background:var(--card); transition:background .2s; position:relative; overflow:hidden; }
        .feature-card:hover { background:rgba(22,163,74,0.04); }
        .feature-icon { width:44px; height:44px; background:rgba(22,163,74,0.1); border:1px solid rgba(22,163,74,0.2); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:1.2rem; margin-bottom:1.2rem; }
        .feature-card h3 { font-family:var(--font-display); font-size:1.05rem; font-weight:700; letter-spacing:-0.02em; margin-bottom:.5rem; }
        .feature-card p { color:var(--text-3); font-size:0.875rem; line-height:1.65; }
        .stats-section { border-top:1px solid var(--border); border-bottom:1px solid var(--border); background:var(--bg2); }
        .stats-inner { max-width:1200px; margin:0 auto; padding:4rem clamp(1.5rem,5vw,4rem); display:grid; grid-template-columns:repeat(4,1fr); gap:2rem; }
        @media(max-width:768px){.stats-inner{grid-template-columns:repeat(2,1fr);}}
        .stat { text-align:center; }
        .stat-val { font-family:var(--font-display); font-size:clamp(2.2rem,4vw,3.5rem); font-weight:800; letter-spacing:-0.04em; background:linear-gradient(135deg,var(--green-hi),var(--green-xl)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; line-height:1; }
        .stat-label { margin-top:.5rem; font-size:0.875rem; color:var(--text-3); }
        #cta { text-align:center; position:relative; overflow:hidden; }
        #cta h2 { max-width:700px; margin:0 auto 1rem; }
        #cta p { color:var(--text-3); font-size:1.05rem; max-width:480px; margin:0 auto 2.5rem; font-weight:300; }
        .cta-btns { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
        footer { border-top:1px solid var(--border); padding:2.5rem clamp(1.5rem,5vw,4rem); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem; }
        .footer-logo { display:flex; align-items:center; gap:10px; text-decoration:none; color:var(--text); }
        .footer-logo span { font-family:var(--font-display); font-weight:700; font-size:1rem; }
        .footer-links { display:flex; gap:1.5rem; list-style:none; }
        .footer-links a { color:var(--text-3); text-decoration:none; font-size:0.875rem; transition:color .2s; }
        .footer-links a:hover { color:var(--text); }
        .footer-copy { color:var(--text-3); font-size:0.8rem; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(24px);} to{opacity:1;transform:translateY(0);} }
        ::-webkit-scrollbar{width:6px;} ::-webkit-scrollbar-track{background:var(--bg);} ::-webkit-scrollbar-thumb{background:var(--border-hi);border-radius:3px;}
      `}</style>

      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      {/* eslint-disable-next-line @next/next/no-page-custom-font */}
      <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />

      {/* NAV */}
      <nav>
        <Link href="/" className="nav-logo">
          <Image src="/logo.png" alt="HybridFlow" width={32} height={32} style={{borderRadius:8}} />
          <span>HybridFlow</span>
        </Link>
        <ul className="nav-links">
          <li><a href="#how">How it works</a></li>
          <li><a href="#features">Features</a></li>
        </ul>
        <div className="nav-cta">
          <Link href="/dashboard" className="btn btn-ghost">Sign in</Link>
          <Link href="/register" className="btn btn-primary">Get Started →</Link>
        </div>
      </nav>

      {/* HERO */}
      <section id="hero">
        <div className="mesh" />
        <div className="grid-lines" />
        <div className="hero-badge"><span className="dot" />Now live — WhatsApp AI with Collision Detection</div>
        <h1>AI replies.<br /><span className="line-green">You take over.</span><br />Zero conflicts.</h1>
        <p className="hero-sub">HybridFlow&apos;s Invisible Mute automatically pauses your AI the moment you step into a conversation — and resumes it when you&apos;re done. No double messages. No confusion.</p>
        <div className="hero-ctas">
          <Link href="/register" className="btn btn-primary btn-xl">Start Free <ArrowRight size={16} /></Link>
          <Link href="/dashboard" className="btn btn-ghost btn-xl">View Dashboard</Link>
        </div>
        <div className="hero-preview">
          <div className="preview-window">
            <div className="preview-bar">
              <span className="preview-dot r" /><span className="preview-dot y" /><span className="preview-dot g" />
              <span className="preview-url">app.hybridflow.io/dashboard</span>
              <span style={{width:60}} />
            </div>
            <div className="preview-inner">
              <div className="preview-sidebar">
                <div className="preview-nav-item active"><div className="preview-nav-icon" /> Dashboard</div>
                <div className="preview-nav-item"><div className="preview-nav-icon" /> Conversations</div>
                <div className="preview-nav-item"><div className="preview-nav-icon" /> WhatsApp</div>
                <div className="preview-nav-item"><div className="preview-nav-icon" /> AI Settings</div>
              </div>
              <div className="preview-main">
                <div className="preview-kpis">
                  <div className="preview-kpi"><div className="preview-kpi-val green">24</div><div className="preview-kpi-label">Active Chats</div></div>
                  <div className="preview-kpi"><div className="preview-kpi-val">3</div><div className="preview-kpi-label">Paused (You)</div></div>
                  <div className="preview-kpi"><div className="preview-kpi-val green">98%</div><div className="preview-kpi-label">AI Handled</div></div>
                </div>
                <div className="preview-sessions">
                  <div className="preview-session-row"><span className="session-name">+44 7700 900142</span><span className="badge-active">AI Active</span><span className="session-time">2m ago</span></div>
                  <div className="preview-session-row"><span className="session-name">+1 555 0198</span><span className="badge-paused">You — Paused</span><span className="session-time">5m ago</span></div>
                  <div className="preview-session-row"><span className="session-name">+234 801 234 5678</span><span className="badge-active">AI Active</span><span className="session-time">12m ago</span></div>
                </div>
              </div>
            </div>
          </div>
          <div className="preview-fade" />
        </div>
      </section>

      {/* LOGOS */}
      <div className="logos-bar">
        <p>Built on</p>
        <div className="logos-row">
          <span className="logo-item">Evolution API</span>
          <span className="logo-item">WhatsApp Business</span>
          <span className="logo-item">Claude AI</span>
          <span className="logo-item">ChatGPT</span>
          <span className="logo-item">Supabase</span>
        </div>
      </div>

      {/* PROBLEM / SOLUTION */}
      <section id="problem">
        <div className="section-tag">// the problem</div>
        <h2>AI and humans fighting<br />over the same conversation</h2>
        <p className="section-sub">Every WhatsApp automation platform has the same fatal flaw — when you reply, your AI keeps replying too.</p>
        <div className="ps-grid">
          <div className="ps-card problem">
            <span className="ps-label">Without HybridFlow</span>
            <h3>Message chaos</h3>
            <p>You step in to handle a sensitive customer, and your AI sends three more replies before you can finish typing.</p>
            <ul className="ps-list">
              <li><X size={14} color="#f87171" style={{flexShrink:0,marginTop:3}} /> Double messages confuse customers</li>
              <li><X size={14} color="#f87171" style={{flexShrink:0,marginTop:3}} /> AI contradicts your human response</li>
              <li><X size={14} color="#f87171" style={{flexShrink:0,marginTop:3}} /> You can&apos;t trust your bot when it matters</li>
              <li><X size={14} color="#f87171" style={{flexShrink:0,marginTop:3}} /> Manual &quot;off switch&quot; every time you reply</li>
            </ul>
          </div>
          <div className="ps-card solution">
            <span className="ps-label">With HybridFlow</span>
            <h3>Invisible Mute™</h3>
            <p>The moment you send a message, AI pauses silently. Resumes automatically after 2 hours of your inactivity.</p>
            <ul className="ps-list">
              <li><Check size={14} color="#22c55e" style={{flexShrink:0,marginTop:3}} /> AI detects your reply and pauses instantly</li>
              <li><Check size={14} color="#22c55e" style={{flexShrink:0,marginTop:3}} /> One clean conversation thread, always</li>
              <li><Check size={14} color="#22c55e" style={{flexShrink:0,marginTop:3}} /> Auto-resumes — no manual steps needed</li>
              <li><Check size={14} color="#22c55e" style={{flexShrink:0,marginTop:3}} /> Full control via dashboard anytime</li>
            </ul>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <div className="section-full">
        <div className="section-inner" id="how">
          <div className="section-tag">// how it works</div>
          <h2>Up and running<br />in three steps</h2>
          <p className="section-sub">Connect your WhatsApp, configure your AI, and let it run. Override anytime.</p>
          <div className="steps">
            <div className="step">
              <div className="step-num">01</div>
              <h3>Connect WhatsApp</h3>
              <p>Scan a QR code to link your WhatsApp Business number. Takes under 60 seconds. No API approvals needed.</p>
              <span className="step-mono">QR → Connected ✓</span>
            </div>
            <div className="step">
              <div className="step-num">02</div>
              <h3>AI handles replies</h3>
              <p>Set your AI persona and knowledge base. From that point, every inbound message gets an intelligent, on-brand reply.</p>
              <span className="step-mono">message.upsert → ai_reply</span>
            </div>
            <div className="step">
              <div className="step-num">03</div>
              <h3>Step in anytime</h3>
              <p>Reply from your phone as normal. HybridFlow detects it and mutes the AI — no dashboard required. It resumes itself.</p>
              <span className="step-mono">fromMe=true → pause()</span>
            </div>
          </div>
        </div>
      </div>

      {/* FEATURES */}
      <section id="features">
        <div className="section-tag">// features</div>
        <h2>Everything you need.<br />Nothing you don&apos;t.</h2>
        <p className="section-sub">Built for business owners who need their WhatsApp to work, not a second job to manage.</p>
        <div className="features-grid">
          {[
            { icon: <Shield size={20} />, title: 'Invisible Mute™', desc: "Auto-detects when you've stepped into a conversation and pauses AI immediately. No buttons, no settings." },
            { icon: <Timer size={20} />, title: 'Auto-Resume', desc: 'AI resumes automatically after 2 hours of your inactivity. Configurable per tenant. No manual re-enabling.' },
            { icon: <Brain size={20} />, title: 'Multi-LLM Support', desc: 'Choose Claude or ChatGPT as your AI brain. Switch providers without touching code. Per-tenant configuration.' },
            { icon: <LayoutDashboard size={20} />, title: 'Live Session Dashboard', desc: 'Monitor every active conversation in real time. See AI status, last message, pause reason, and full history.' },
            { icon: <Building2 size={20} />, title: 'Multi-Tenant', desc: 'Manage multiple WhatsApp numbers and businesses from one account. Each tenant gets isolated data and settings.' },
            { icon: <Lock size={20} />, title: 'GDPR Ready', desc: 'Built-in data export, erasure, and retention controls. Webhook signature verification. Auth via Supabase.' },
          ].map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* STATS */}
      <div className="stats-section">
        <div className="stats-inner">
          {[
            { val: '98%', label: 'Messages handled by AI' },
            { val: '<2s', label: 'Average AI response time' },
            { val: '0', label: 'Double messages ever sent' },
            { val: '2hrs', label: 'Until AI auto-resumes' },
          ].map((s) => (
            <div key={s.label} className="stat">
              <div className="stat-val">{s.val}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* FINAL CTA */}
      <section id="cta">
        <div className="mesh" />
        <div className="section-tag">// get started</div>
        <h2>Your WhatsApp.<br /><span className="line-green">On autopilot.</span></h2>
        <p>Free to start. No credit card. Full access to the dashboard and AI automation from day one.</p>
        <div className="cta-btns">
          <Link href="/register" className="btn btn-primary btn-xl">Create Free Account <ArrowRight size={16} /></Link>
          <Link href="/dashboard" className="btn btn-ghost btn-xl">Explore Dashboard</Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        <Link href="/" className="footer-logo">
          <Image src="/logo.png" alt="HybridFlow" width={28} height={28} style={{borderRadius:7}} />
          <span>HybridFlow</span>
        </Link>
        <ul className="footer-links">
          <li><a href="#how">How it works</a></li>
          <li><a href="#features">Features</a></li>
          <Link href="/dashboard"><a>Dashboard</a></Link>
          <Link href="/register"><a>Sign up</a></Link>
        </ul>
        <span className="footer-copy">© 2026 HybridFlow. All rights reserved.</span>
      </footer>
    </>
  );
}
