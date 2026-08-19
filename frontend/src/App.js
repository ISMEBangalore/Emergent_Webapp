import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { Layout } from "@/components/Layout";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import GenerateReport from "@/pages/GenerateReport";
import ReportView from "@/pages/ReportView";
import History from "@/pages/History";
import Settings from "@/pages/Settings";
import ComparePage from "@/pages/ComparePage";
import CumulativeView from "@/pages/CumulativeView";
import Latest from "@/pages/Latest";
import ApplicationInsight from "@/pages/ApplicationInsight";

function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth();
  const loc = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: loc }} replace />;
  }
  return children;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <RequireAuth>
                  <Layout>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/generate" element={<GenerateReport />} />
                      <Route path="/report/:id" element={<ReportView />} />
                      <Route path="/history" element={<History />} />
                      <Route path="/compare" element={<ComparePage />} />
                      <Route path="/cumulative" element={<CumulativeView />} />
                      <Route path="/latest" element={<Latest />} />
                      <Route path="/insights" element={<ApplicationInsight />} />
                      <Route path="/settings" element={<Settings />} />
                    </Routes>
                  </Layout>
                </RequireAuth>
              }
            />
          </Routes>
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
