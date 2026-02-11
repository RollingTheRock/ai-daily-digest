import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { config } from "./config";
import App from "./App";
import "./index.css";

// GitHub Pages SPA 路由恢复
const redirectPath = sessionStorage.getItem("redirect_path");
if (redirectPath) {
  sessionStorage.removeItem("redirect_path");
  window.history.replaceState(null, "", redirectPath);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={config.basePath}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
