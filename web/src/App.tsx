import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LoadingState } from "./components/StateBlocks";

const IdeasPage = lazy(() => import("./pages/IdeasPage").then((m) => ({ default: m.IdeasPage })));
const CartographerPage = lazy(() =>
  import("./pages/CartographerPage").then((m) => ({ default: m.CartographerPage })),
);
const AdvisorPage = lazy(() => import("./pages/AdvisorPage").then((m) => ({ default: m.AdvisorPage })));
const HistoryPage = lazy(() => import("./pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const RunDetailPage = lazy(() =>
  import("./pages/RunDetailPage").then((m) => ({ default: m.RunDetailPage })),
);
const AnalysisDetailPage = lazy(() =>
  import("./pages/AnalysisDetailPage").then((m) => ({ default: m.AnalysisDetailPage })),
);

function isKnownPath(pathname: string): boolean {
  if (pathname === "/" || pathname === "/cartographer" || pathname === "/advisor" || pathname === "/history") {
    return true;
  }
  return /^\/history\/[^/]+$/.test(pathname) || /^\/analysis\/[^/]+$/.test(pathname);
}

/** Keep main tabs mounted (hidden when inactive) so async work survives navigation. */
function TabbedRoutes() {
  const { pathname } = useLocation();

  if (!isKnownPath(pathname)) {
    return <Navigate to="/" replace />;
  }

  const showIdeas = pathname === "/";
  const showCartographer = pathname === "/cartographer";
  const showAdvisor = pathname === "/advisor";
  const showHistory = pathname === "/history";

  return (
    <>
      <div className="tab-panel" hidden={!showIdeas} aria-hidden={!showIdeas}>
        <IdeasPage />
      </div>
      <div className="tab-panel" hidden={!showCartographer} aria-hidden={!showCartographer}>
        <CartographerPage />
      </div>
      <div className="tab-panel" hidden={!showAdvisor} aria-hidden={!showAdvisor}>
        <AdvisorPage />
      </div>
      <div className="tab-panel" hidden={!showHistory} aria-hidden={!showHistory}>
        <HistoryPage />
      </div>

      <Routes>
        <Route path="/history/:runId" element={<RunDetailPage />} />
        <Route path="/analysis/:runId" element={<AnalysisDetailPage />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingState label="Loading page" />}>
        <TabbedRoutes />
      </Suspense>
    </AppShell>
  );
}

export default App;
