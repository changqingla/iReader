import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { ToastProvider } from "@/hooks/useToast";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/RouteGuards/AdminRoute";
import Home from "@/pages/Home";
import ChatDetail from "@/pages/ChatDetail";
import Knowledge from "@/pages/Knowledge";
import KnowledgeDetail from "@/pages/KnowledgeDetail";
import Auth from "@/pages/Auth";
import Favorites from "@/pages/Favorites";
import Notes from "@/pages/Notes";
import OrganizationDetail from "@/pages/OrganizationDetail";
import AdminPanel from "@/pages/AdminPanel";

export default function App() {
  return (
    <ToastProvider>
      <Router>
        <Routes>
          {/* 公开路由 */}
          <Route path="/auth" element={<Auth />} />
          
          {/* 受保护的路由 - 需要登录 */}
          <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
          <Route path="/chat/:chatId" element={<ProtectedRoute><ChatDetail /></ProtectedRoute>} />
          <Route path="/knowledge" element={<ProtectedRoute><Knowledge /></ProtectedRoute>} />
          <Route path="/knowledge/:kbId" element={<ProtectedRoute><KnowledgeDetail /></ProtectedRoute>} />
          <Route path="/favorites" element={<ProtectedRoute><Favorites /></ProtectedRoute>} />
          <Route path="/notes" element={<ProtectedRoute><Notes /></ProtectedRoute>} />
          <Route path="/organizations/:id" element={<ProtectedRoute><OrganizationDetail /></ProtectedRoute>} />
          
          {/* 管理员路由 - 需要管理员权限 */}
          <Route path="/admin" element={<ProtectedRoute><AdminRoute><AdminPanel /></AdminRoute></ProtectedRoute>} />
          
          <Route path="/other" element={<ProtectedRoute><div className="text-center text-xl">Other Page - Coming Soon</div></ProtectedRoute>} />
        </Routes>
      </Router>
    </ToastProvider>
  );
}
