import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
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

function App() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingState label="Loading page" />}>
        <Routes>
          <Route path="/" element={<IdeasPage />} />
          <Route path="/cartographer" element={<CartographerPage />} />
          <Route path="/advisor" element={<AdvisorPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:runId" element={<RunDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}

export default App;
