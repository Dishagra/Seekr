import { useEffect, useState } from "react";

/** Marks the whole page as working, so the watermark animates and any caller
 *  can show its own message underneath. */
export function useWorking(active: boolean): void {
  useEffect(() => {
    document.body.classList.toggle("is-working", active);
    return () => document.body.classList.remove("is-working");
  }, [active]);
}

/** The topbar earns its shadow only once there is something scrolled under it. */
export function useScrollShade(): boolean {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return scrolled;
}

const THEME_KEY = "seekr_theme";

/** The choice lives on <html data-theme>, which is what the stylesheet reads,
 *  and is applied before first paint by a snippet in main.tsx so the page does
 *  not flash the wrong theme on reload. */
export function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "light",
  );
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    setTheme(next);
  };
  return [theme, toggle];
}
