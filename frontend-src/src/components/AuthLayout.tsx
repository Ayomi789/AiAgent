import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ArrowLeft, Lock } from "lucide-react";

export function AuthLayout({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
  aside,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
  aside: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-app-900">
      {/* Top bar */}
      <header className="border-b border-line">
        <div className="mx-auto flex h-[56px] w-full max-w-[1240px] items-center gap-3 px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-[28px] w-[28px] items-center justify-center rounded-[5px] border border-line-strong bg-app-800">
              <ShieldCheck size={15} className="text-ink" />
            </span>
            <span className="text-[12.5px] font-semibold tracking-[-0.01em] text-ink">
              Sentinel
            </span>
          </Link>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden items-center gap-1.5 rounded-[4px] border border-[rgba(70,167,88,0.26)] bg-[rgba(70,167,88,0.07)] px-2.5 py-[5px] sm:flex">
              <Lock size={9} className="text-[#66c07a]" />
              <span className="font-mono text-[8px] font-semibold uppercase tracking-[0.13em] text-[#66c07a]">
                HTTPS · session cookie
              </span>
            </div>
            <Link to="/" className="btn-secondary !py-[6px] !text-[11px]">
              <ArrowLeft size={11} />
              Back to site
            </Link>
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="mx-auto grid w-full max-w-[1240px] flex-1 grid-cols-1 px-5 lg:grid-cols-2">
        {/* Form column */}
        <div className="flex flex-col justify-center py-12 lg:py-16 lg:pr-16">
          <div className="w-full max-w-[404px]">
            <div className="flex items-center gap-2">
              <span className="h-[5px] w-[5px] rounded-[1px] bg-[#4c8dff]" />
              <span className="font-mono text-[8.5px] font-semibold uppercase tracking-[0.17em] text-dim">
                {eyebrow}
              </span>
            </div>

            <h1 className="mt-4 text-[25px] font-semibold leading-[1.2] tracking-[-0.021em] text-ink">
              {title}
            </h1>
            <p className="mt-3 text-[11.5px] leading-[1.8] text-muted">{subtitle}</p>

            <div className="mt-7">{children}</div>

            <div className="mt-7 border-t border-line pt-5">{footer}</div>
          </div>
        </div>

        {/* Aside column */}
        <aside className="border-t border-line py-12 lg:border-l lg:border-t-0 lg:py-16 lg:pl-16">
          <div className="lg:sticky lg:top-16">{aside}</div>
        </aside>
      </div>

      {/* Footer strip */}
      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1240px] flex-wrap items-center gap-x-5 gap-y-1.5 px-5 py-3.5">
          <span className="font-mono text-[8px] text-faint">© 2026 Sentinel</span>
          <span className="font-mono text-[8px] text-faint">qaagent 0.1.0</span>
          <div className="ml-auto flex items-center gap-4">
            <a href="/terms" className="font-mono text-[8px] text-faint hover:text-muted">
              Terms
            </a>
            <a href="/abuse" className="font-mono text-[8px] text-faint hover:text-muted">
              Report abuse
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export function AuthAsideHeader({
  title,
  subtitle,
  status,
}: {
  title: string;
  subtitle: string;
  status?: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
      <div>
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
          {title}
        </h2>
        <p className="mt-1.5 max-w-[320px] text-[9.5px] leading-[1.8] text-dim">{subtitle}</p>
      </div>
      {status ? (
        <div className="flex items-center gap-1.5 rounded-[4px] border border-[rgba(76,141,255,0.26)] bg-[rgba(76,141,255,0.08)] px-2 py-[4px]">
          <span className="h-[5px] w-[5px] rounded-full bg-[#4c8dff] animate-pulse-dot" />
          <span className="font-mono text-[7.5px] font-semibold uppercase tracking-[0.13em] text-[#7fa9f0]">
            {status}
          </span>
        </div>
      ) : null}
    </div>
  );
}
