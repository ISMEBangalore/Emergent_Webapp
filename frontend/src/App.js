import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { Layout } from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import GenerateReport from "@/pages/GenerateReport";
import ReportView from "@/pages/ReportView";
import History from "@/pages/History";
import Settings from "@/pages/Settings";
import ComparePage from "@/pages/ComparePage";
import CumulativeView from "@/pages/CumulativeView";
import Latest from "@/pages/Latest";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/generate" element={<GenerateReport />} />
            <Route path="/report/:id" element={<ReportView />} />
            <Route path="/history" element={<History />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/cumulative" element={<CumulativeView />} />
            <Route path="/latest" element={<Latest />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </div>
  );
}

export default App;
