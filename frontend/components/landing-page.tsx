"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

const revealSelector = "[data-scroll-reveal]";

const stats = [
  ["2k+", "active users"],
  ["30 sec", "average logging time"],
  ["3", "chat channels"],
];

const features = [
  ["chat", "Chat Transaction", "Record expenses in seconds using natural language."],
  ["document_scanner", "Receipt Scanner", "Snap a receipt and let OCR extract the total."],
  ["mic", "Voice Note Input", "Send a quick voice note when typing is too slow."],
  ["picture_as_pdf", "PDF Reports", "Export weekly and monthly reports in one click."],
];

const dashboardItems = [
  ["01", "Track income and expenses", "Automatically categorize every transaction as it happens."],
  ["02", "View monthly cashflow", "See where money goes with simple visual summaries."],
  ["03", "Export PDF reports", "Generate clean reports for review or reimbursement."],
  ["04", "Monitor budgets by category", "Set category limits before spending goes too far."],
];

export function LandingPage() {
  const rootRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>(revealSelector));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.16 },
    );

    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let frame = 0;

    function updateScrollVars() {
      frame = 0;
      const root = rootRef.current;
      if (!root) return;

      const max = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
      const progress = Math.min(window.scrollY / max, 1);
      root.style.setProperty("--landing-scroll", progress.toFixed(4));
      root.classList.toggle("landing-scrolled", window.scrollY > 20);
    }

    function onScroll() {
      if (!frame) frame = window.requestAnimationFrame(updateScrollVars);
    }

    updateScrollVars();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <main ref={rootRef} className="landing-page min-h-screen overflow-hidden bg-[#f7f7f0] text-[#191919]">
      <div className="fixed inset-x-0 top-0 z-[60] h-1 bg-[#dfe4d5]">
        <div className="landing-progress h-full bg-[#c7ff00]" />
      </div>

      <nav className="landing-nav fixed inset-x-0 top-0 z-50 border-b border-white/40 bg-white/70 backdrop-blur-xl transition-all duration-300">
        <div className="mx-auto flex h-20 max-w-[1440px] items-center justify-between px-5 md:px-8">
          <Link href="/" className="text-2xl font-extrabold tracking-tight">
            Sakoo.
          </Link>
          <div className="hidden items-center gap-8 md:flex">
            {[
              ["Features", "#features"],
              ["Dashboard", "#dashboard"],
              ["Bot", "#bot"],
              ["Reports", "#reports"],
              ["Pricing", "#pricing"],
            ].map(([label, href]) => (
              <a key={label} href={href} className="text-sm font-semibold text-[#6f6f6f] transition-colors hover:text-[#191919]">
                {label}
              </a>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="hidden text-sm font-bold hover:opacity-70 md:block">
              Sign In
            </Link>
            <Link href="/register" className="rounded-full bg-[#c7ff00] px-5 py-3 text-sm font-extrabold text-[#202020] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_24px_rgba(199,255,0,0.44)]">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      <section className="px-4 pb-16 pt-28 md:px-8">
        <div className="mx-auto grid min-h-[720px] max-w-[1500px] items-center gap-12 overflow-hidden rounded-[40px] bg-[#202020] p-8 text-white shadow-[0_28px_80px_rgba(0,0,0,0.22)] md:p-16 lg:grid-cols-[1fr_620px] lg:p-20">
          <div data-scroll-reveal="rise" className="scroll-reveal relative z-10">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 backdrop-blur-sm">
              <span className="material-symbols-outlined text-sm text-[#c7ff00]">smart_toy</span>
              <span className="text-sm font-semibold text-white/90">AI finance assistant made easy</span>
            </div>
            <h1 className="max-w-3xl text-5xl font-extrabold leading-[1.04] tracking-[-0.03em] md:text-7xl">
              Manage your money <span className="text-[#c7ff00]">through chat.</span>
            </h1>
            <p className="mt-6 max-w-md text-base leading-7 text-white/70">
              Record expenses via WhatsApp or Telegram. Sakoo Bot categorizes it,
              builds reports, and updates your dashboard instantly.
            </p>
            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <Link href="/register" className="inline-flex items-center justify-center gap-2 rounded-full bg-[#c7ff00] px-8 py-4 text-sm font-extrabold text-[#202020] transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_0_24px_rgba(199,255,0,0.44)]">
                Get Started
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </Link>
              <a href="#bot" className="inline-flex items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-8 py-4 text-sm font-bold text-white transition-all duration-200 hover:bg-white/20">
                <span className="material-symbols-outlined text-sm">play_circle</span>
                Watch Demo
              </a>
            </div>
            <div className="mt-12 grid max-w-lg grid-cols-3 gap-3">
              {stats.map(([value, label], index) => (
                <div
                  key={label}
                  data-scroll-reveal="rise"
                  className="scroll-reveal rounded-2xl border border-white/10 bg-white/5 p-4"
                  style={{ transitionDelay: `${index * 90}ms` }}
                >
                  <p className="text-2xl font-extrabold text-[#c7ff00]">{value}</p>
                  <p className="mt-1 text-xs text-white/55">{label}</p>
                </div>
              ))}
            </div>
          </div>

          <HeroMockup />
        </div>
      </section>

      <section className="px-5 py-20 text-center md:px-8">
        <div data-scroll-reveal="zoom" className="scroll-reveal mx-auto max-w-3xl">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full bg-[#202020] px-4 py-2 text-sm font-bold text-white">
            <span className="material-symbols-outlined text-sm text-[#c7ff00]">bolt</span>
            Built for students, freelancers, and daily money tracking.
          </div>
          <h2 className="text-4xl font-extrabold leading-tight tracking-[-0.03em] md:text-5xl">
            Your personal finance assistant, always available on chat.
          </h2>
        </div>
        <div data-scroll-reveal="rise" className="scroll-reveal mx-auto mt-12 max-w-2xl rounded-[28px] border border-[#e8e8e8] bg-white p-5 shadow-[0_10px_30px_rgba(0,0,0,0.06)]">
          <div className="mb-4 flex flex-col gap-4">
            <div className="landing-chat-bubble self-start rounded-2xl rounded-tl-sm border border-[#e8e8e8] bg-white p-4 shadow-sm">
              How can I help you today?
            </div>
            <div className="landing-chat-bubble landing-chat-bubble-late self-end rounded-2xl rounded-tr-sm bg-[#202020] p-4 text-white shadow-md">
              Track my coffee expense.
            </div>
          </div>
          <div className="relative mt-8">
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[#9a9a9a]">chat_bubble</span>
            <input
              readOnly
              className="w-full rounded-2xl border border-[#e8e8e8] bg-white py-4 pl-12 pr-16 text-sm shadow-sm outline-none transition-all duration-300 focus:ring-2 focus:ring-[#c7ff00]"
              placeholder="Type a message..."
              type="text"
            />
            <button className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center justify-center rounded-xl bg-[#c7ff00] p-2 text-[#202020]">
              <span className="material-symbols-outlined">send</span>
            </button>
            <div className="absolute -bottom-7 left-12 flex items-center gap-2">
              <span className="landing-dot" />
              <span className="text-[10px] font-extrabold uppercase tracking-[0.2em] text-[#6f6f6f]">Sakoo is typing</span>
            </div>
          </div>
        </div>
      </section>

      <section id="dashboard" className="mx-auto grid max-w-[1440px] items-center gap-16 px-5 py-24 md:px-8 lg:grid-cols-2">
        <div data-scroll-reveal="left" className="scroll-reveal relative flex h-[500px] items-center justify-center">
          <DashboardPreview />
        </div>
        <div data-scroll-reveal="right" className="scroll-reveal">
          <div className="mb-6 inline-block rounded-full bg-[#202020] px-3 py-1 text-xs font-extrabold uppercase tracking-wider text-[#c7ff00]">
            Smart Dashboard
          </div>
          <h2 className="mb-6 text-4xl font-extrabold leading-tight tracking-[-0.03em] md:text-5xl">
            All your finances in one clean dashboard
          </h2>
          <ul className="mb-10 grid gap-6 sm:grid-cols-2">
            {dashboardItems.map(([number, title, body], index) => (
              <li
                key={title}
                data-scroll-reveal="rise"
                className="scroll-reveal flex items-start gap-3"
                style={{ transitionDelay: `${index * 80}ms` }}
              >
                <span className="text-lg font-extrabold text-[#9cc900]">{number}</span>
                <div>
                  <h3 className="mb-1 text-base font-extrabold">{title}</h3>
                  <p className="text-sm leading-6 text-[#6f6f6f]">{body}</p>
                </div>
              </li>
            ))}
          </ul>
          <Link href="/register" className="inline-flex items-center gap-2 rounded-full bg-[#c7ff00] px-8 py-4 text-sm font-extrabold text-[#202020] transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_0_24px_rgba(199,255,0,0.44)]">
            Open Dashboard
            <span className="material-symbols-outlined text-sm">open_in_new</span>
          </Link>
        </div>
      </section>

      <section id="bot" className="mx-auto grid max-w-[1440px] items-center gap-16 px-5 py-24 md:px-8 lg:grid-cols-2">
        <div data-scroll-reveal="left" className="scroll-reveal order-2 lg:order-1">
          <div className="mb-6 inline-block rounded-full border border-[#202020]/20 px-3 py-1 text-xs font-extrabold uppercase tracking-wider">
            No app switching
          </div>
          <h2 className="mb-6 text-4xl font-extrabold leading-tight tracking-[-0.03em] md:text-5xl">
            Record transactions directly from WhatsApp and Telegram
          </h2>
          <p className="max-w-md text-base leading-8 text-[#6f6f6f]">
            Text Sakoo like a friend. Use natural language to record purchases,
            check balances, or ask where your money went.
          </p>
        </div>
        <div data-scroll-reveal="right" className="scroll-reveal order-1 flex justify-center lg:order-2">
          <BotMockup />
        </div>
      </section>

      <section id="features" className="mx-auto max-w-[1440px] rounded-[40px] bg-[#f1f2f0] px-5 py-24 md:px-8">
        <div data-scroll-reveal="zoom" className="scroll-reveal mb-16 text-center">
          <h2 className="mb-4 text-4xl font-extrabold leading-tight tracking-[-0.03em] md:text-5xl">
            Powerful tools, simple interface
          </h2>
          <p className="mx-auto max-w-2xl text-base leading-7 text-[#6f6f6f]">
            Everything you need to manage your money, powered by intelligent automation.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map(([icon, title, body], index) => (
            <div
              key={title}
              data-scroll-reveal="rise"
              className="scroll-reveal rounded-3xl border border-[#e8e8e8] bg-white p-8 shadow-[0_10px_30px_rgba(0,0,0,0.06)] transition-transform duration-300 hover:-translate-y-2"
              style={{ transitionDelay: `${index * 90}ms` }}
            >
              <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#c7ff00]/20 text-[#202020]">
                <span className="material-symbols-outlined text-2xl">{icon}</span>
              </div>
              <h3 className="mb-3 text-base font-extrabold">{title}</h3>
              <p className="text-sm leading-6 text-[#6f6f6f]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="reports" className="mx-auto max-w-[1440px] px-4 py-24 md:px-8">
        <div data-scroll-reveal="zoom" className="scroll-reveal overflow-hidden rounded-[40px] bg-[#202020] p-10 text-center text-white md:p-20">
          <h2 className="mx-auto mb-6 max-w-3xl text-4xl font-extrabold leading-tight tracking-[-0.03em] md:text-5xl">
            Start tracking your money the easy way
          </h2>
          <p className="mx-auto mb-10 max-w-xl text-base leading-7 text-white/70">
            Use Sakoo from chat, dashboard, receipt scan, or voice note.
          </p>
          <div className="flex flex-col justify-center gap-4 sm:flex-row">
            <Link href="/register" className="rounded-full bg-[#c7ff00] px-8 py-4 text-sm font-extrabold text-[#202020] transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_0_24px_rgba(199,255,0,0.44)]">
              Get Started
            </Link>
            <Link href="/login" className="rounded-full border border-white/30 px-8 py-4 text-sm font-bold text-white transition-all duration-200 hover:bg-white/10">
              View Demo
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#e8e8e8] bg-white px-5 pb-8 pt-16 md:px-8">
        <div className="mx-auto max-w-[1440px]">
          <div className="mb-12 grid gap-8 md:grid-cols-4">
            <div className="md:col-span-2">
              <div className="mb-4 text-2xl font-extrabold">Sakoo.</div>
              <p className="max-w-sm text-sm leading-7 text-[#6f6f6f]">
                The easiest way to track expenses and manage personal finances through conversational AI.
              </p>
            </div>
            <FooterLinks title="Product" items={["Features", "Integrations", "Pricing", "Changelog"]} />
            <FooterLinks title="Legal" items={["Privacy Policy", "Terms of Service", "Cookie Policy"]} />
          </div>
          <div className="flex flex-col items-center justify-between gap-4 border-t border-[#e8e8e8] pt-8 text-sm text-[#6f6f6f] md:flex-row">
            <p>(c) 2026 Sakoo Finance Bot. All rights reserved.</p>
            <div className="flex gap-4">
              <a href="#" className="transition-colors hover:text-[#202020]">Twitter</a>
              <a href="#" className="transition-colors hover:text-[#202020]">LinkedIn</a>
              <a href="#" className="transition-colors hover:text-[#202020]">Instagram</a>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}

function HeroMockup() {
  return (
    <div data-scroll-reveal="right" className="scroll-reveal landing-hero-stage relative z-10 flex h-[540px] items-center justify-center lg:h-[700px]">
      <div className="landing-phone-tilt absolute left-1/2 top-1/2 z-20 h-[500px] w-[240px] -translate-x-[72%] -translate-y-1/2 -rotate-6 overflow-hidden rounded-[32px] bg-[#c7ff00] p-2 shadow-[0_18px_40px_rgba(0,0,0,0.18)] transition-transform duration-500 hover:rotate-0">
        <div className="flex h-full flex-col overflow-hidden rounded-[26px] bg-[#202020]">
          <div className="flex h-6 justify-center pt-2">
            <div className="h-1 w-1/3 rounded-full bg-white/20" />
          </div>
          <div className="flex flex-1 flex-col items-center justify-center p-4 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#c7ff00] text-[#202020]">
              <span className="material-symbols-outlined text-3xl">forum</span>
            </div>
            <div className="mb-2 text-sm font-extrabold text-white">Sakoo Bot</div>
            <div className="mb-8 text-xs text-white/50">Online</div>
            <div className="flex w-full flex-col gap-3">
              <div className="max-w-[85%] self-end rounded-2xl rounded-tr-sm bg-[#c7ff00] px-3 py-2 text-left text-xs font-semibold text-[#202020] shadow-md">
                Grab lunch 120k
              </div>
              <div className="max-w-[85%] self-start rounded-2xl rounded-tl-sm border border-white/10 bg-white/10 px-3 py-2 text-left text-xs text-white">
                Got it. Recorded Rp120.000 for Food and Dining.
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="landing-float-card absolute left-1/2 top-1/2 z-30 w-[260px] -translate-y-[86%] -translate-x-[8%] rotate-3 rounded-3xl border border-[#e8e8e8] bg-white p-5 text-[#202020] shadow-[0_18px_40px_rgba(0,0,0,0.18)] transition-transform duration-500 hover:rotate-0">
        <div className="mb-4 flex items-start justify-between">
          <div className="text-xs text-[#6f6f6f]">Total Balance</div>
          <span className="material-symbols-outlined text-sm text-[#6f6f6f]">more_horiz</span>
        </div>
        <div className="mb-4 text-[28px] font-extrabold leading-none">Rp12.450k</div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-full bg-[#5fcf6a]/10 px-2 py-1 font-bold text-[#2f9d3b]">+2.4%</span>
          <span className="text-[#6f6f6f]">vs last month</span>
        </div>
      </div>

      <div className="landing-float-card landing-float-card-late absolute left-1/2 top-1/2 z-10 w-[220px] translate-x-[16%] translate-y-[12%] -rotate-3 rounded-3xl border border-[#e8e8e8] bg-white p-5 text-[#202020] shadow-[0_18px_40px_rgba(0,0,0,0.18)] transition-transform duration-500 hover:rotate-0">
        <div className="mb-4 text-sm font-extrabold">Weekly Spend</div>
        <div className="mb-2 flex h-[80px] items-end justify-between gap-1">
          {[40, 80, 30, 60, 100, 50, 20].map((height, index) => (
            <div
              key={index}
              className={`w-full rounded-t-sm ${index === 1 ? "bg-[#c7ff00]" : index === 4 ? "bg-[#202020]" : "bg-[#f1f2f0]"}`}
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
        <div className="flex justify-between text-[8px] text-[#6f6f6f]">
          {["M", "T", "W", "T", "F", "S", "S"].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}
        </div>
      </div>

      <div className="landing-badge absolute right-[10%] top-[22%] z-40 flex h-12 w-12 items-center justify-center rounded-full bg-[#c7ff00] text-[#202020] shadow-[0_0_24px_rgba(199,255,0,0.44)]">
        <span className="material-symbols-outlined">receipt_long</span>
      </div>
    </div>
  );
}

function DashboardPreview() {
  return (
    <div className="relative w-full max-w-[420px]">
      <div className="landing-dashboard-card relative z-20 rounded-3xl border border-[#e8e8e8] bg-white p-6 shadow-[0_18px_40px_rgba(0,0,0,0.18)]">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-bold text-[#6f6f6f]">Total Balance</span>
          <span className="material-symbols-outlined text-[#6f6f6f]">account_balance_wallet</span>
        </div>
        <div className="mb-4 text-3xl font-extrabold">Rp12.450.000</div>
      </div>
      <div className="landing-dashboard-card landing-dashboard-card-late relative z-10 ml-8 mt-6 rounded-3xl border border-[#e8e8e8] bg-white p-6 shadow-[0_18px_40px_rgba(0,0,0,0.18)]">
        <div className="mb-4 flex items-center justify-between">
          <span className="font-extrabold">Cashflow</span>
          <span className="rounded-md bg-[#202020] px-2 py-1 text-xs font-extrabold text-[#c7ff00]">This Month</span>
        </div>
        <div className="flex h-24 items-end gap-2">
          {[50, 100, 75, 33].map((height, index) => (
            <div
              key={index}
              className={`w-1/4 rounded-t-md ${index === 1 ? "bg-[#c7ff00]" : index === 2 ? "bg-[#202020]" : "bg-[#f1f2f0]"}`}
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function BotMockup() {
  return (
    <div className="landing-phone w-full max-w-[360px] rounded-[32px] border border-[#e8e8e8] bg-white p-6 shadow-[0_18px_40px_rgba(0,0,0,0.18)]">
      <div className="mb-8 flex items-center gap-3 border-b border-[#e8e8e8] pb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#c7ff00]">
          <span className="material-symbols-outlined text-[#202020]">smart_toy</span>
        </div>
        <div>
          <div className="text-sm font-extrabold">Sakoo Bot</div>
          <div className="flex items-center gap-1 text-xs text-[#2f9d3b]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#5fcf6a]" />
            Online
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-4">
        <Bubble side="right">Bought coffee for Rp18.000</Bubble>
        <Bubble side="left">Noted. Added Rp18.000 to Food and Drinks.</Bubble>
        <Bubble side="right">What is my total balance?</Bubble>
        <Bubble side="green">Your total balance is Rp12.450.000.</Bubble>
      </div>
    </div>
  );
}

function Bubble({ children, side }: { children: string; side: "left" | "right" | "green" }) {
  const className = {
    left: "self-start rounded-tl-sm bg-[#202020] text-white",
    right: "self-end rounded-tr-sm bg-[#f1f2f0] text-[#202020]",
    green: "self-start rounded-tl-sm bg-[#c7ff00] text-[#202020]",
  }[side];

  return (
    <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function FooterLinks({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-4 text-sm font-extrabold">{title}</h3>
      <ul className="space-y-3 text-sm text-[#6f6f6f]">
        {items.map((item) => (
          <li key={item}>
            <a href="#" className="transition-colors hover:text-[#202020]">{item}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}
