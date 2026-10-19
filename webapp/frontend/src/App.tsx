import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Apps from "./pages/Apps";
import ChatPage from "./pages/ChatPage";
import Dashboard from "./pages/Dashboard";
import Help from "./pages/Help";
import Inbox from "./pages/Inbox";
import JobInspector from "./pages/JobInspector";
import Logs from "./pages/Logs";
import NewTheorem from "./pages/NewTheorem";
import ProblemLibrary from "./pages/ProblemLibrary";
import Settings from "./pages/Settings";
import Skills from "./pages/Skills";
import Tools from "./pages/Tools";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/jobs/:jobId" element={<JobInspector />} />
        <Route path="/problems" element={<ProblemLibrary />} />
        <Route path="/submit" element={<NewTheorem />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/tools" element={<Tools />} />
        <Route path="/skills" element={<Skills />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/apps" element={<Apps />} />
        <Route path="/help" element={<Help />} />
      </Routes>
    </Layout>
  );
}
