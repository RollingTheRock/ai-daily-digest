import { Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Star from "./pages/Star";
import Note from "./pages/Note";

function App() {
  return (
    <div className="min-h-screen bg-notion-bg">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/star" element={<Star />} />
        <Route path="/note" element={<Note />} />
      </Routes>
    </div>
  );
}

export default App;
