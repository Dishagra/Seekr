import type { ReactElement } from "react";
import { Mark } from "./mark";

/** Line icons, sized to sit on the 15px text baseline of the rail and buttons.
 *  They inherit colour, so a button's hover state carries into its icon. */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

export const Icon = {
  logo: (): ReactElement => <Mark size={15} />,

  search: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" {...stroke} strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="M16 16l5 5" />
    </svg>
  ),

  review: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" {...stroke} strokeWidth="1.9">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  ),

  plug: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" {...stroke} strokeWidth="1.9">
      <path d="M9 2v6M15 2v6" />
      <path d="M6 8h12v3a6 6 0 0 1-12 0z" />
      <path d="M12 17v5" />
    </svg>
  ),

  caret: () => (
    <svg
      className="caret"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      {...stroke}
      strokeWidth="2.4"
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  ),

  back: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" {...stroke} strokeWidth="2.2">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  ),

  thumbUp: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    >
      <path d="M7 22V10l5-8a2.5 2.5 0 0 1 2.4 3.2L13.5 9H19a2.5 2.5 0 0 1 2.4 3.1l-1.7 7A2.5 2.5 0 0 1 17.3 22z" />
      <rect x="2" y="10" width="5" height="12" rx="1" />
    </svg>
  ),

  thumbDown: () => (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    >
      <path d="M17 2v12l-5 8a2.5 2.5 0 0 1-2.4-3.2l.9-3.8H5a2.5 2.5 0 0 1-2.4-3.1l1.7-7A2.5 2.5 0 0 1 6.7 2z" />
      <rect x="17" y="2" width="5" height="12" rx="1" />
    </svg>
  ),

  eye: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" {...stroke} strokeWidth="1.7">
      <path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z" />
      <circle cx="12" cy="12" r="2.7" />
    </svg>
  ),

  eyeOff: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" {...stroke} strokeWidth="1.7">
      <path d="M10.7 6.2A9.9 9.9 0 0 1 12 5.5c6.4 0 10 6.5 10 6.5a18 18 0 0 1-3.2 4M6.3 7.9A17.7 17.7 0 0 0 2 12s3.6 6.5 10 6.5a10 10 0 0 0 4-.8" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
      <path d="m3 3 18 18" />
    </svg>
  ),

  bookmark: () => (
    <svg width="13" height="13" viewBox="0 0 24 24" {...stroke} strokeWidth="1.9">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  ),

  empty: () => (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="M16 16l5 5" />
    </svg>
  ),
};
