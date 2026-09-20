import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, ArrowRight, ShieldCheck, Lock, AlertTriangle } from "lucide-react";
import { AuthLayout, AuthAsideHeader } from "../components/AuthLayout";

async function authed(): Promise<boolean> {
  try {
    const res = await fetch("/api/me", { credentials: "include" });
    return res.ok;
  } catch {
    return false;
  }
}

export function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [csrf, setCsrf] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authed().then((ok) => {
      if (ok) navigate("/app", { replace: true });
    });
    fetch("/api/auth/csrf", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setCsrf(d.csrf_token || ""))
      .catch(() => {});
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address to continue.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password, csrf_token: csrf }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(
          (body as { error?: string }).error || `Sign-in failed (${res.status}). Try again.`
        );
        setLoading(false);
        return;
      }
      navigate("/app");
    } catch {
      setError("Could not reach the server — is it awake?");
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="Account access"
      title="Sign in to Sentinel"
      subtitle="Authenticate to run scans, review severity-ranked findings, and download evidence-backed reports."
      footer={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-[10px] text-dim">No account yet?</span>
          <Link
            to="/signup"
            className="flex items-center gap-1 text-[10.5px] font-medium text-[#7fa9f0] hover:underline"
          >
            Create one
            <ArrowRight size={10} />
          </Link>
          <div className="ml-auto flex items-center gap-1.5">
            <Lock size={9} className="text-faint" />
            <span className="font-mono text-[8px] text-faint">session logged</span>
          </div>
        </div>
      }
      aside={
        <>
          <AuthAsideHeader
            title="How sign-in works"
            subtitle="Session cookies, brute-force protection, and instant suspension."
          />

          <div className="mt-4 space-y-0">
            {[
              ["Password storage", "scrypt hashes — plaintext never stored"],
              ["Brute-force protection", "5 attempts per 5 minutes per address"],
              ["Sessions", "server-side, destroyed on sign-out"],
              ["Suspended accounts", "rejected on the very next request"],
            ].map(([label, value]) => (
              <div
                key={label}
                className="flex items-center justify-between gap-3 border-b border-line-soft py-2.5"
              >
                <span className="text-[9.5px] text-faint">{label}</span>
                <span className="text-right font-mono text-[9px] text-muted">{value}</span>
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-[6px] border border-line bg-app-880 p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck size={11} className="text-[#66c07a]" />
              <span className="text-[8.5px] font-semibold uppercase tracking-[0.13em] text-faint">
                Authorized testing only
              </span>
            </div>
            <p className="mt-2 text-[9px] leading-[1.85] text-dim">
              Every scan requires an ownership declaration, and every report is stamped with who
              authorized it, when, and from where. Accounts used for unauthorized testing are
              suspended.
            </p>
          </div>
        </>
      }
    >
      {/* Form */}
      <form onSubmit={handleSubmit} noValidate>
        {error ? (
          <div className="mb-4 flex items-start gap-2 rounded-[5px] border border-[rgba(229,72,77,0.28)] bg-[rgba(229,72,77,0.08)] px-3 py-2.5">
            <AlertTriangle size={11} className="mt-[1px] shrink-0 text-[#f28286]" />
            <span className="text-[9.5px] leading-relaxed text-[#f28286]">{error}</span>
          </div>
        ) : null}

        <div className="space-y-4">
          <div>
            <label
              htmlFor="login-email"
              className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
            >
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              className="field !py-[9px] font-mono text-[11.5px]"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label
                htmlFor="login-password"
                className="text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
              >
                Password
              </label>
            </div>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                className="field !py-[9px] pr-10 font-mono text-[11.5px]"
                placeholder="••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[4px] p-1.5 text-faint transition-colors hover:bg-app-750 hover:text-muted"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={12} /> : <Eye size={12} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full !py-[10px] !text-[12px] disabled:opacity-60"
          >
            {loading ? (
              <>
                <span className="h-[11px] w-[11px] rounded-full border-[1.5px] border-[#0b0d10] border-t-transparent animate-spin" />
                Signing in…
              </>
            ) : (
              <>
                Sign in
                <ArrowRight size={12} />
              </>
            )}
          </button>
        </div>
      </form>

      {/* Security notice */}
      <div className="mt-5 rounded-[5px] border border-line bg-app-880 p-3">
        <div className="flex items-start gap-2">
          <Lock size={10} className="mt-[2px] shrink-0 text-dim" />
          <p className="text-[8.5px] leading-[1.85] text-faint">
            Wrong passwords are rate-limited and never say which half was wrong. Suspended
            accounts are rejected on sign-in.
          </p>
        </div>
      </div>
    </AuthLayout>
  );
}
