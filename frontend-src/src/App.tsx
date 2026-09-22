import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { Overview } from "./pages/Overview";
import { Runs } from "./pages/Runs";
import { NewRun } from "./pages/NewRun";
import { Findings } from "./pages/Findings";
import { FindingDetail } from "./pages/FindingDetail";
import { Evidence } from "./pages/Evidence";
import { Targets } from "./pages/Targets";
import { TestLibrary } from "./pages/TestLibrary";
import { Reports } from "./pages/Reports";
import { Admin } from "./pages/Admin";
import { Settings } from "./pages/Settings";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname]);
  return null;
}

/**
 * Blocks the app shell until the session is confirmed. Without this the
 * console flashes its empty state for a few seconds before the first 401
 * bounces to sign-in. Plain fetch on purpose: the shared client redirects
 * on 401, which would loop here.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [state, setState] = useState<"checking" | "ok">("checking");

  useEffect(() => {
    let alive = true;
    fetch("/api/me", { credentials: "include" })
      .then((res) => {
        if (!alive) return;
        if (res.ok) {
          setState("ok");
        } else {
          const next = location.pathname + location.search;
          window.location.href = `/console/login?next=${encodeURIComponent(next)}`;
        }
      })
      .catch(() => {
        if (!alive) return;
        const next = location.pathname + location.search;
        window.location.href = `/console/login?next=${encodeURIComponent(next)}`;
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state !== "ok") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-app-900">
        <span className="h-[26px] w-[26px] rounded-[5px] border border-line-strong bg-app-800 animate-pulse-dot" />
        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-faint">
          Verifying session…
        </span>
      </div>
    );
  }
  return <>{children}</>;
}

function AppRoutes() {
  const location = useLocation();
  const needsAuth = location.pathname.startsWith("/app");
  const routes = (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
        <Route
          path="/app"
          element={
            <AppShell>
              <Overview />
            </AppShell>
          }
        />
        <Route
          path="/app/runs"
          element={
            <AppShell>
              <Runs />
            </AppShell>
          }
        />
        <Route
          path="/app/runs/new"
          element={
            <AppShell>
              <NewRun />
            </AppShell>
          }
        />
        <Route
          path="/app/findings"
          element={
            <AppShell>
              <Findings />
            </AppShell>
          }
        />
        <Route
          path="/app/findings/:id"
          element={
            <AppShell>
              <FindingDetail />
            </AppShell>
          }
        />
        <Route
          path="/app/evidence"
          element={
            <AppShell>
              <Evidence />
            </AppShell>
          }
        />
        <Route
          path="/app/targets"
          element={
            <AppShell>
              <Targets />
            </AppShell>
          }
        />
        <Route
          path="/app/tests"
          element={
            <AppShell>
              <TestLibrary />
            </AppShell>
          }
        />
        <Route
          path="/app/reports"
          element={
            <AppShell>
              <Reports />
            </AppShell>
          }
        />
        <Route
          path="/app/admin"
          element={
            <AppShell>
              <Admin />
            </AppShell>
          }
        />
        <Route
          path="/app/settings"
          element={
            <AppShell>
              <Settings />
            </AppShell>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
  );
  return (
    <>
      <ScrollToTop />
      {needsAuth ? <RequireAuth>{routes}</RequireAuth> : routes}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter basename="/console">
      <AppRoutes />
    </BrowserRouter>
  );
}
