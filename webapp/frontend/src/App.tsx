import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import JobInspector from "./pages/JobInspector";
import ProblemLibrary from "./pages/ProblemLibrary";
import NewTheorem from "./pages/NewTheorem";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs/:jobId" element={<JobInspector />} />
        <Route path="/problems" element={<ProblemLibrary />} />
        <Route path="/submit" element={<NewTheorem />} />
      </Routes>
    </Layout>
  );
}
