import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import AppShell from "./components/layout/AppShell";
import Analytics from "./pages/Analytics";
import Dashboard from "./pages/Dashboard";
import Findings from "./pages/Findings";
import LiveInspection from "./pages/LiveInspection";
import MissionDetail from "./pages/MissionDetail";
import Missions from "./pages/Missions";
import Reports from "./pages/Reports";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/missions/:missionId/live"
          element={<LiveInspection />}
        />

        <Route element={<AppShell />}>
          <Route
            path="/"
            element={
              <Navigate
                to="/dashboard"
                replace
              />
            }
          />

          <Route
            path="/dashboard"
            element={<Dashboard />}
          />

          <Route
            path="/analytics"
            element={<Analytics />}
          />

          <Route
            path="/missions/:missionId/analytics"
            element={<Analytics />}
          />

          <Route
            path="/missions"
            element={<Missions />}
          />

          <Route
            path="/missions/:missionId"
            element={<MissionDetail />}
          />

          <Route
            path="/findings"
            element={
              <Navigate
                to="/missions/M-104/findings"
                replace
              />
            }
          />

          <Route
            path="/missions/:missionId/findings"
            element={<Findings />}
          />

          <Route
            path="/reports"
            element={
              <Navigate
                to="/reports/PV-2026-001"
                replace
              />
            }
          />

          <Route
            path="/reports/:missionId"
            element={<Reports />}
          />

          <Route
            path="/digital-twin"
            element={
              <Navigate
                to="/missions/M-104"
                replace
              />
            }
          />

          <Route
            path="*"
            element={
              <Navigate
                to="/dashboard"
                replace
              />
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;