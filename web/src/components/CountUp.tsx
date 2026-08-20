import { useEffect, useRef } from "react";
import { fmt } from "../lib/format";

/** A number that lands on its value rather than appearing fully formed. Short
 *  enough not to keep anyone waiting to read it, and skipped outright for
 *  anyone who asked for less motion. */
export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!to || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.textContent = fmt(to);
      return;
    }
    let frame = 0;
    const started = performance.now();
    const ms = 620;
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / ms);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out: fast, then settles
      el.textContent = fmt(Math.round(to * eased));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [to]);

  return <b ref={ref}>0</b>;
}
