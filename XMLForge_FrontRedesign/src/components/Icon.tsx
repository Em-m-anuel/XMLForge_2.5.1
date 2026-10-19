import type { ReactNode } from "react";

const S: Record<string, ReactNode> = {
  home: <path d="M3.5 10.6 12 3.5l8.5 7.1V20a.8.8 0 0 1-.8.8h-4.4v-6H8.7v6H4.3a.8.8 0 0 1-.8-.8z" />,
  database: (
    <>
      <path d="M12 3.2c4.3 0 7.8 1.1 7.8 2.5S16.3 8.2 12 8.2 4.2 7.1 4.2 5.7 7.7 3.2 12 3.2z" />
      <path d="M4.2 5.7v12.6c0 1.4 3.5 2.5 7.8 2.5s7.8-1.1 7.8-2.5V5.7" />
      <path d="M4.2 12c0 1.4 3.5 2.5 7.8 2.5s7.8-1.1 7.8-2.5" />
    </>
  ),
  table: (
    <>
      <path d="M3.5 5.2h17v13.6h-17z" />
      <path d="M3.5 9.7h17M9.2 9.7v9.1M14.8 9.7v9.1" />
    </>
  ),
  rows: (
    <>
      <path d="M8.5 6.5h12M8.5 12h12M8.5 17.5h12" />
      <path d="M4.2 6.5h.01M4.2 12h.01M4.2 17.5h.01" />
    </>
  ),
  columns: (
    <>
      <path d="M4 4.5h16v15H4z" />
      <path d="M9.3 4.5v15M14.7 4.5v15" />
    </>
  ),
  terminal: (
    <>
      <path d="M5 7.5 8.8 12 5 16.5" />
      <path d="M11.5 17h7.5" />
    </>
  ),
  code: (
    <>
      <path d="M9 7.5 4.5 12 9 16.5" />
      <path d="M15 7.5 19.5 12 15 16.5" />
    </>
  ),
  relations: (
    <>
      <path d="M4 6.5h5.5v5.5H4z" />
      <path d="M14.5 13h5.5v5.5h-5.5z" />
      <path d="M9.5 9h2.5a3 3 0 0 1 3 3v1" />
    </>
  ),
  download: (
    <>
      <path d="M12 3.5v10.5" />
      <path d="M7.5 10 12 14.5 16.5 10" />
      <path d="M4.5 19.5h15" />
    </>
  ),
  upload: (
    <>
      <path d="M12 20V9.5" />
      <path d="M7.5 14 12 9.5 16.5 14" />
      <path d="M4.5 4.5h15" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7.5h6M14 7.5h6M4 16.5h6M14 16.5h6" />
      <circle cx="11.6" cy="7.5" r="1.9" />
      <circle cx="11.6" cy="16.5" r="1.9" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 7.5h4M12 7.5h8M4 16.5h8M16 16.5h4" />
      <circle cx="10" cy="7.5" r="2" />
      <circle cx="14" cy="16.5" r="2" />
    </>
  ),
  server: (
    <>
      <path d="M3.5 5h17v6.5h-17zM3.5 13h17v6.5h-17z" />
      <path d="M7 8.2h.01M7 16.2h.01" />
    </>
  ),
  logs: (
    <>
      <path d="M6.5 3.5h8l4.5 4.5v12.5H6.5z" />
      <path d="M14.5 3.5V8h4.5" />
      <path d="M9.5 13h6M9.5 17h4" />
    </>
  ),
  users: (
    <>
      <path d="M15.5 20.2v-1.2a3.8 3.8 0 0 0-3.8-3.8H7.3a3.8 3.8 0 0 0-3.8 3.8v1.2" />
      <circle cx="9.5" cy="7.8" r="3.4" />
      <path d="M16.8 20.2v-1.2a3.8 3.8 0 0 0-2.9-3.7" />
      <path d="M15.6 4.6a3.4 3.4 0 0 1 0 6.5" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.2" r="3.8" />
      <path d="M4.8 20.2a7.2 7.2 0 0 1 14.4 0" />
    </>
  ),
  shield: <path d="M12 3.4 19 6.2v5.6c0 4.3-2.9 7.4-7 8.8-4.1-1.4-7-4.5-7-8.8V6.2z" />,
  lock: (
    <>
      <path d="M6 11h12v9.2H6z" />
      <path d="M9 11V8.2a3 3 0 0 1 6 0V11" />
    </>
  ),
  unlock: (
    <>
      <path d="M6 11h12v9.2H6z" />
      <path d="M9 11V8.2a3 3 0 0 1 5.6-1.6" />
    </>
  ),
  key: (
    <>
      <circle cx="15.5" cy="8.5" r="4.2" />
      <path d="M12.6 11.4 4 20v0h3l1.2-1.2v-2.1h2.1v-2.1h2.1l1.4-1.4" />
    </>
  ),
  link: (
    <>
      <path d="M9.6 14.4 14.4 9.6" />
      <path d="M8.2 11.8 6 14a3.9 3.9 0 0 0 5.5 5.5l2.2-2.2" />
      <path d="M15.8 12.2 18 10a3.9 3.9 0 0 0-5.5-5.5L10.3 6.7" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.8" />
      <path d="M16.2 16.2 20.8 20.8" />
    </>
  ),
  plus: <path d="M12 5.2v13.6M5.2 12h13.6" />,
  minus: <path d="M5.5 12h13" />,
  chevronRight: <path d="M9.5 5.5 16 12l-6.5 6.5" />,
  chevronDown: <path d="M5.5 9.5 12 16l6.5-6.5" />,
  chevronUp: <path d="M5.5 14.5 12 8l6.5 6.5" />,
  check: <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />,
  x: <path d="M6.5 6.5 17.5 17.5M17.5 6.5 6.5 17.5" />,
  trash: (
    <>
      <path d="M4.5 7h15" />
      <path d="M9.5 7V4.8h5V7" />
      <path d="M6.5 7l.9 12.2h9.2L17.5 7" />
      <path d="M10.2 10.6v5.6M13.8 10.6v5.6" />
    </>
  ),
  pencil: (
    <>
      <path d="M4.5 19.5h4L19 9l-4-4L4.5 15.5z" />
      <path d="M13.5 6.5 17.5 10.5" />
    </>
  ),
  play: <path d="M7.5 4.8 19 12 7.5 19.2z" />,
  copy: (
    <>
      <path d="M9.5 9.5h9.8v9.8H9.5z" />
      <path d="M5 15.5V5.2h10.3" />
    </>
  ),
  filter: <path d="M3.8 5h16.4l-6.4 7.6v5.6l-3.6-2v-3.6z" />,
  sort: (
    <>
      <path d="M7 4.5v15M4 16.5l3 3 3-3" />
      <path d="M17 19.5v-15M14 7.5l3-3 3 3" />
    </>
  ),
  more: <path d="M6 12h.01M12 12h.01M18 12h.01" />,
  bell: (
    <>
      <path d="M18 16.2V11a6 6 0 1 0-12 0v5.2L4.2 19h15.6z" />
      <path d="M9.8 21.8h4.4" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-2.4-5.7" />
      <path d="M19.6 3.8v4.4h-4.4" />
    </>
  ),
  history: (
    <>
      <path d="M12 7.8v4.4l3 1.8" />
      <path d="M3.2 12a8.8 8.8 0 1 0 2.6-6.2" />
      <path d="M3 4.2v4.2h4.2" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" />
      <circle cx="12" cy="12" r="2.6" />
    </>
  ),
  eyeOff: (
    <>
      <path d="M4 5.5 20 19" />
      <path d="M9.6 6.6A9.6 9.6 0 0 1 12 6.4c6 0 9.5 5.6 9.5 5.6a17 17 0 0 1-2.6 3.1" />
      <path d="M6.2 8.3A16.6 16.6 0 0 0 2.5 12S6 17.6 12 17.6c1 0 2-.15 2.9-.4" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4.2 21 19.8H3z" />
      <path d="M12 10v4M12 16.6h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 11v5.2M12 8h.01" />
    </>
  ),
  checkCircle: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M8.2 12.4 11 15.2l4.8-5.6" />
    </>
  ),
  xCircle: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M9.2 9.2 14.8 14.8M14.8 9.2 9.2 14.8" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M12 7.4V12l3 1.8" />
    </>
  ),
  cpu: (
    <>
      <path d="M6.2 6.2h11.6v11.6H6.2z" />
      <path d="M9.4 9.4h5.2v5.2H9.4z" />
      <path d="M9.8 3.4v2.8M14.2 3.4v2.8M9.8 17.8v2.8M14.2 17.8v2.8M3.4 9.8h2.8M3.4 14.2h2.8M17.8 9.8h2.8M17.8 14.2h2.8" />
    </>
  ),
  hdd: (
    <>
      <path d="M3.5 7.2h17v9.6h-17z" />
      <path d="M7 16.8v1.6h10v-1.6" />
      <path d="M6.8 11.6h.01M9.6 11.6h.01" />
    </>
  ),
  wifi: (
    <>
      <path d="M2.5 9.2a14 14 0 0 1 19 0" />
      <path d="M5.8 12.8a9.2 9.2 0 0 1 12.4 0" />
      <path d="M9 16.4a4.4 4.4 0 0 1 6 0" />
      <path d="M12 19.6h.01" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3.4 21 8.2l-9 4.8-9-4.8z" />
      <path d="M3 12.6 12 17.4l9-4.8" />
    </>
  ),
  braces: (
    <>
      <path d="M9 4.5H7.6A2.6 2.6 0 0 0 5 7.1v2.6c0 1-.8 1.8-1.8 1.8.9 0 1.8.9 1.8 1.9v2.5A2.6 2.6 0 0 0 7.6 19.5H9" />
      <path d="M15 4.5h1.4A2.6 2.6 0 0 1 19 7.1v2.6c0 1 .8 1.8 1.8 1.8-.9 0-1.8.9-1.8 1.9v2.5a2.6 2.6 0 0 1-2.6 2.6H15" />
    </>
  ),
  panelLeft: (
    <>
      <path d="M3.5 5h17v14h-17z" />
      <path d="M9.5 5v14" />
    </>
  ),
  share: (
    <>
      <circle cx="18" cy="5.5" r="2.6" />
      <circle cx="6" cy="12" r="2.6" />
      <circle cx="18" cy="18.5" r="2.6" />
      <path d="M8.4 10.7 15.6 7M8.4 13.3l7.2 3.7" />
    </>
  ),
  save: (
    <>
      <path d="M5.5 3.8h9.7l3.5 3.5v12.9H5.5z" />
      <path d="M8.5 3.8v5.2h7V3.8" />
      <path d="M8.5 14.2h7v5.9h-7z" />
    </>
  ),
  folder: <path d="M3.5 7h5.8l2 2.2h9.2v9.6H3.5z" />,
  bolt: <path d="M13.2 3.2 5.5 13.8h5.4L10 20.8l8.5-11.2h-5.6z" />,
  command: (
    <path d="M9 6.5a2.8 2.8 0 1 0-2.8 2.8h11.6A2.8 2.8 0 1 0 15 6.5v11a2.8 2.8 0 1 0 2.8-2.8H6.2A2.8 2.8 0 1 0 9 17.5z" />
  ),
  arrowRight: <path d="M4.5 12h15M13.5 6l6 6-6 6" />,
  logout: (
    <>
      <path d="M14.5 8.2V5.5H5.5v13h9v-2.7" />
      <path d="M10.5 12h9M16.5 8.8l3.2 3.2-3.2 3.2" />
    </>
  ),
  grid: (
    <>
      <path d="M4 4.5h6.4v6.4H4zM13.6 4.5H20v6.4h-6.4zM4 13.1h6.4v6.4H4zM13.6 13.1H20v6.4h-6.4z" />
    </>
  ),
  index: (
    <>
      <path d="M12 3.5v17" />
      <path d="M5 8.5 12 3.5l7 5" />
      <path d="M5.5 12.5h4M14.5 12.5h4M5.5 16h4M14.5 16h4" />
    </>
  ),
  power: (
    <>
      <path d="M12 3.5v7" />
      <path d="M6.8 7.2A7.8 7.8 0 1 0 17.2 7.2" />
    </>
  ),
};

export type IconName = keyof typeof S;

export function Icon({
  name,
  size = 16,
  className = "",
  strokeWidth = 1.6,
}: {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {S[name]}
    </svg>
  );
}
