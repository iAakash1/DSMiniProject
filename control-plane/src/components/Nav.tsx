"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function Icon({ path }: { path: string }) {
  return (
    <svg className="rail-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const ICONS = {
  overview: "M3 13h8V3H3v10Zm10 8h8V3h-8v18ZM3 21h8v-6H3v6Z",
  coordinators: "M4 4h16v6H4V4Zm0 10h16v6H4v-6ZM8 7h.01M8 17h.01",
  topology: "M12 3v4m0 10v4M3 12h4m10 0h4M6.3 6.3l2.8 2.8m5.8 5.8 2.8 2.8M17.7 6.3l-2.8 2.8m-5.8 5.8-2.8 2.8M12 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm0 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm-7-6a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm14 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  clocks: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-14v5l3 3",
  workers: "M22 12h-4l-3 9-6-18-3 9H2",
  runs: "M5 3v18l15-9L5 3Z",
  events: "M3 12a9 9 0 1 0 9-9 9.7 9.7 0 0 0-6.74 2.74L3 8M3 3v5h5m4-1v5l4 2",
};

const links = [
  { href: "/", label: "Overview", icon: ICONS.overview },
  { href: "/coordinators", label: "Coordinators", icon: ICONS.coordinators },
  { href: "/topology", label: "Topology", icon: ICONS.topology },
  { href: "/clocks", label: "Clock explorer", icon: ICONS.clocks },
  { href: "/workers", label: "Worker health", icon: ICONS.workers },
  { href: "/runs", label: "Research runs", icon: ICONS.runs },
  { href: "/events", label: "Event history", icon: ICONS.events },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="rail">
      <div className="rail-brand-row">
        <span className="rail-mark" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="5" r="2.6" fill="currentColor" />
            <circle cx="5" cy="18" r="2.6" fill="currentColor" opacity="0.55" />
            <circle cx="19" cy="18" r="2.6" fill="currentColor" opacity="0.55" />
            <path d="M12 7.6 6.3 16M12 7.6 17.7 16M6.8 18h10.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </span>
        <div>
          <div className="rail-brand">OmniSignal</div>
          <div className="rail-brand-sub">Control plane</div>
        </div>
      </div>
      {links.map((link) => {
        const isActive = link.href === "/" ? pathname === "/" : pathname?.startsWith(link.href);
        return (
          <Link key={link.href} href={link.href} className={`rail-link${isActive ? " active" : ""}`}>
            <Icon path={link.icon} />
            <span>{link.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
