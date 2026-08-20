import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Applied before the first render so a reload never flashes the wrong theme.
const savedTheme = localStorage.getItem("seekr_theme");
if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
