import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Lock,
  AlertTriangle,
} from "lucide-react";
import { AuthLayout, AuthAsideHeader } from "../components/AuthLayout";
import { ProgressBar } from "../components/ui";

function passwordScore(pw: string): number {
  if (!pw) return 0;
  let score = 0;
  if (pw.length >= 8) score += 25;
  if (pw.length >= 12) score += 15;
  if (/[A-Z]/.test(pw)) score += 15;
  if (/[a-z]/.test(pw)) score += 10;
  if (/[0-9]/.test(pw)) score += 15;
  if (/[^A-Za-z0-9]/.test(pw)) score += 20;
  return Math.min(100, score);
}

const STRENGTH_META = [
  { min: 0, label: "Empty", color: "#4d555e" },
  { min: 1, label: "Weak", color: "#e5484d" },
  { min: 45, label: "Fair", color: "#f5a623" },
  { min: 70, label: "Strong", color: "#4c8dff" },
  { min: 90, label: "Excellent", color: "#46a758" },
];

type Policy = "bootstrap" | "invite" | "open";

export function Signup() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [code, setCode] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [policy, setPolicy] = useState<Policy>("invite");
  const [csrf, setCsrf] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const score = passwordScore(password);
  const strength = [...STRENGTH_META].reverse().find((s) => score >= s.min) ?? STRENGTH_META[0];

  useEffect(() => {
    fetch("/api/me", { credentials: "include" })
      .then((r) => {
        if (r.ok) navigate("/app", { replace: true });
      })
      .catch(() => {});
    fetch("/api/auth/policy", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        if (d.policy === "bootstrap" || d.policy === "invite" || d.policy === "open") {
          setPolicy(d.policy);
        }
      })
      .catch(() => {});
    fetch("/api/auth/csrf", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setCsrf(d.csrf_token || ""))
      .catch(() => {});
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (policy === "bootstrap" && !code.trim()) {
      setError("Paste the server access token to claim the admin account.");
      return;
    }
    if (policy === "invite" && !code.trim()) {
      setError("Enter the invite code you were given.");
      return;
    }
    if (!agreed) {
      setError("You must accept the Terms of Service to continue.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
          csrf_token: csrf,
          accept_terms: agreed,
          bootstrap_token: policy === "bootstrap" ? code.trim() : "",
          invite_code: policy === "invite" ? code.trim() : "",
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(
          (body as { error?: string }).error || `Signup failed (${res.status}). Try again.`
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
      eyebrow="Create account"
      title={
        policy === "bootstrap" ? "Claim the admin account" : "Create your Sentinel account"
      }
      subtitle={
        policy === "bootstrap"
          ? "This instance has no users yet. Paste the server access token to prove you operate it — the first account is the admin."
          : policy === "invite"
            ? "Signup is by invitation. Enter the single-use code an admin gave you — each code works exactly once."
            : "Create an account to run scans and review reports."
      }
      footer={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-[10px] text-dim">Already have an account?</span>
          <Link
            to="/login"
            className="flex items-center gap-1 text-[10.5px] font-medium text-[#7fa9f0] hover:underline"
          >
            Sign in
            <ArrowRight size={10} />
          </Link>
          <div className="ml-auto flex items-center gap-1.5">
            <Lock size={9} className="text-faint" />
            <span className="font-mono text-[8px] text-faint">scrypt-hashed passwords</span>
          </div>
        </div>
      }
      aside={
        <>
          <AuthAsideHeader
            title="How signup works"
            subtitle="Closed by default. No open registration on public instances."
          />

          <div className="mt-4 space-y-0">
            {[
              ["First account", "requires the server access token — becomes admin"],
              ["Later accounts", "require a single-use invite code from an admin"],
              ["Terms consent", "recorded with timestamp on every signup"],
              ["Passwords", "scrypt hashes — plaintext never stored"],
              ["Sign-in abuse", "5 attempts per 5 minutes per address"],
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
                Authorized use
              </span>
            </div>
            <p className="mt-2 text-[9px] leading-[1.85] text-dim">
              Accounts may only be used to assess systems you own or have explicit written
              authorization to test. Misuse reports go to the abuse contact, and offending
              accounts are suspended.
            </p>
          </div>
        </>
      }
    >
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
              htmlFor="signup-email"
              className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
            >
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              className="field !py-[9px] font-mono text-[11.5px]"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label
              htmlFor="signup-password"
              className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="signup-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                className="field !py-[9px] pr-10 font-mono text-[11.5px]"
                placeholder="Minimum 8 characters"
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

            <div className="mt-2.5">
              <div className="flex items-center justify-between">
                <div className="flex gap-[3px]">
                  {[0, 1, 2, 3].map((i) => (
                    <span
                      key={i}
                      className="h-[3px] w-[38px] rounded-[2px]"
                      style={{
                        backgroundColor: score > i * 25 ? strength.color : "#22262c",
                        transition: "background-color 180ms ease",
                      }}
                    />
                  ))}
                </div>
                <span
                  className="font-mono text-[8px] uppercase tracking-[0.12em]"
                  style={{ color: strength.color }}
                >
                  {password ? strength.label : "—"}
                </span>
              </div>
            </div>
          </div>

          {policy === "bootstrap" ? (
            <div>
              <label
                htmlFor="signup-token"
                className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
              >
                Server access token
              </label>
              <input
                id="signup-token"
                type="password"
                autoComplete="off"
                className="field !py-[9px] font-mono text-[11.5px]"
                placeholder="From the URL printed by sentinel dashboard"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>
          ) : null}

          {policy === "invite" ? (
            <div>
              <label
                htmlFor="signup-invite"
                className="mb-1.5 block text-[9px] font-semibold uppercase tracking-[0.13em] text-faint"
              >
                Invite code
              </label>
              <input
                id="signup-invite"
                type="text"
                autoComplete="off"
                className="field !py-[9px] font-mono text-[11.5px]"
                placeholder="XXXXX-XXXXX-XXXXX"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>
          ) : null}

          <label className="flex cursor-pointer items-start gap-2 pt-0.5">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-[2px] h-[12px] w-[12px] shrink-0 accent-[#4c8dff]"
            />
            <span className="text-[9px] leading-[1.75] text-muted">
              I confirm that I will only test systems I own or have explicit written
              authorization to assess, and I accept the{" "}
              <a
                href="/terms"
                target="_blank"
                rel="noreferrer"
                className="text-[#7fa9f0] underline underline-offset-2"
              >
                terms of service
              </a>
              .
            </span>
          </label>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full !py-[10px] !text-[12px] disabled:opacity-60"
          >
            {loading ? (
              <>
                <span className="h-[11px] w-[11px] rounded-full border-[1.5px] border-[#0b0d10] border-t-transparent animate-spin" />
                Creating account…
              </>
            ) : (
              <>
                Create account
                <ArrowRight size={12} />
              </>
            )}
          </button>
        </div>
      </form>

      {/* keep ProgressBar import meaningful: hidden strength summary for screen readers */}
      <div className="sr-only" aria-live="polite">
        <ProgressBar value={score} color={strength.color} />
      </div>
    </AuthLayout>
  );
}
