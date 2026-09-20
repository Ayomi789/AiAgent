import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect } from "react";
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
import { Settings } from "./pages/Settings";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname]);
  return null;
}

function AppRoutes() {
  return (
    <>
      <ScrollToTop />
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
          path="/app/settings"
          element={
            <AppShell>
              <Settings />
            </AppShell>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
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
