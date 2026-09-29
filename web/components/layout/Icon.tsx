/** Line icons (24px grid, stroke = currentColor), drawn for this app so no icon library is needed. */
const PATHS = {
  home: ["M3 10.5 12 3l9 7.5", "M5 9.5V21h14V9.5", "M9.5 21v-6h5v6"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "m20 20-4-4"],
  assistant: ["M4 5h16v11H9l-5 4z", "M8 9h8", "M8 12h5"],
  map: ["M9 4 3 6.5V20l6-2.5 6 2.5 6-2.5V4l-6 2.5z", "M9 4v13.5", "M15 6.5V20"],
  dashboard: ["M4 4h7v9H4z", "M13 4h7v5h-7z", "M13 11h7v9h-7z", "M4 15h7v5H4z"],
  chart: ["M4 4v16h16", "m7 15 4-4 3 3 5-6"],
  flask: ["M9 3h6", "M10 3v6l-5.4 9.4A1.7 1.7 0 0 0 6.1 21h11.8a1.7 1.7 0 0 0 1.5-2.6L14 9V3", "M7.2 15h9.6"],
  users: ["M9 4.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z", "M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6", "M16 4.6a3.5 3.5 0 0 1 0 6.8", "M18 14.4c1.8.8 3 2.9 3 5.6"],
  bulb: ["M9 18h6", "M10 21h4", "M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2v.5h5V16c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"],
  database: ["M12 3c3.9 0 7 1.1 7 2.5S15.9 8 12 8 5 6.9 5 5.5 8.1 3 12 3z", "M5 5.5v13C5 19.9 8.1 21 12 21s7-1.1 7-2.5v-13", "M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"],
  shield: ["M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z", "m9 12 2 2 4-4"],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  sidebar: ["M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M9 4v16", "m16 10-2 2 2 2"],
  sidebarOpen: ["M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M9 4v16", "m14 10 2 2-2 2"],
  moon: ["M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"],
  sun: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M12 2v2", "M12 20v2", "m4.9 4.9 1.4 1.4", "m17.7 17.7 1.4 1.4", "M2 12h2", "M20 12h2", "m4.9 19.1 1.4-1.4", "m17.7 6.3 1.4-1.4"],
  user: ["M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8z", "M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"],
  chevronDown: ["m6 9 6 6 6-6"],
  close: ["M6 6l12 12", "M18 6 6 18"],
  arrowRight: ["M5 12h14", "m13 6 6 6-6 6"],
  logout: ["M15 4h4v16h-4", "m10 17 5-5-5-5", "M15 12H3"],
  corner: ["m9 10-5 5 5 5", "M20 4v7a4 4 0 0 1-4 4H4"],
  check: ["m5 12.5 4.5 4.5L19 7"],
  arrowLeft: ["M19 12H5", "m11 18-6-6 6-6"],
  eye: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"],
  eyeOff: ["m3 3 18 18", "M10.6 5.1A10.8 10.8 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-3.2 4.2", "M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a10 10 0 0 0 5.4-1.6", "M9.9 9.9a3 3 0 0 0 4.2 4.2"],
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "h-[18px] w-[18px]", label }: { name: IconName; className?: string; label?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round"
      className={`shrink-0 ${className}`} aria-hidden={label ? undefined : true} role={label ? "img" : undefined} aria-label={label}>
      {PATHS[name].map((d) => <path key={d} d={d} />)}
    </svg>
  );
}
