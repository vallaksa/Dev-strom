import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { RequireAuth } from "./components/RequireAuth";
import { LoadingState } from "./components/StateBlocks";
import { refreshAuth } from "./lib/auth";

const LandingPage = lazy(() =>
  import("./pages/LandingPage").then((m) => ({ default: m.LandingPage })),
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const IdeasPage = lazy(() => import("./pages/IdeasPage").then((m) => ({ default: m.IdeasPage })));
const AdvisorPage = lazy(() => import("./pages/AdvisorPage").then((m) => ({ default: m.AdvisorPage })));
const RunDetailPage = lazy(() =>
  import("./pages/RunDetailPage").then((m) => ({ default: m.RunDetailPage })),
);
const AnalysisDetailPage = lazy(() =>
  import("./pages/AnalysisDetailPage").then((m) => ({ default: m.AnalysisDetailPage })),
);

function isKnownAppPath(pathname: string): boolean {
  if (pathname === "/ideas" || pathname === "/advisor") return true;
  return /^\/history\/[^/]+$/.test(pathname) || /^\/analysis\/[^/]+$/.test(pathname);
}

/** Everything under the app shell. Keeps the two main tabs mounted (hidden
 *  when inactive) so async work survives navigation. */
function AppRoutes() {
  const { pathname } = useLocation();

  if (pathname === "/cartographer") return <Navigate to="/advisor" replace />;
  if (pathname === "/history") return <Navigate to="/ideas" replace />;
  if (!isKnownAppPath(pathname)) return <Navigate to="/ideas" replace />;

  const showIdeas = pathname === "/ideas";
  const showAdvisor = pathname === "/advisor";

  return (
    <>
      <div className="tab-panel" hidden={!showIdeas} aria-hidden={!showIdeas}>
        <IdeasPage />
      </div>
      <div className="tab-panel" hidden={!showAdvisor} aria-hidden={!showAdvisor}>
        <AdvisorPage />
      </div>

      <Routes>
        <Route path="/history/:runId" element={<RunDetailPage />} />
        <Route path="/analysis/:runId" element={<AnalysisDetailPage />} />
      </Routes>
    </>
  );
}

function App() {
  useEffect(() => {
    void refreshAuth();
  }, []);

  return (
    <Suspense fallback={<LoadingState label="Loading page" />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="*"
          element={
            <RequireAuth>
              <AppShell>
                <AppRoutes />
              </AppShell>
            </RequireAuth>
          }
        />
      </Routes>
    </Suspense>
  );
}

export default App;
