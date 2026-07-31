import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { getToken } from "./lib/api";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Board from "./pages/Board";
import Leads from "./pages/Leads";
import LeadDetailPage from "./pages/LeadDetailPage";
import Inbox from "./pages/Inbox";
import Meetings from "./pages/Meetings";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getToken()) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Board />} />
        <Route path="leads" element={<Leads />} />
        <Route path="leads/:id" element={<LeadDetailPage />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="meetings" element={<Meetings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
