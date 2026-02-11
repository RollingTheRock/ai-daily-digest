import { Routes, Route, Navigate } from "react-router-dom";
import { isLoggedIn } from "./lib/github-auth";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Star from "./pages/Star";
import Note from "./pages/Note";

// 私有路由守卫
function PrivateRoute({ children }: { children: React.ReactNode }) {
  return isLoggedIn() ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <div className="min-h-screen bg-notion-bg">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/star"
          element={
            <PrivateRoute>
              <Star />
            </PrivateRoute>
          }
        />
        <Route
          path="/note"
          element={
            <PrivateRoute>
              <Note />
            </PrivateRoute>
          }
        />
      </Routes>
    </div>
  );
}

export default App;
