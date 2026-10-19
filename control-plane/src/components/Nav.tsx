"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/coordinators", label: "Coordinators" },
  { href: "/topology", label: "Topology" },
  { href: "/clocks", label: "Clock explorer" },
  { href: "/workers", label: "Worker health" },
  { href: "/runs", label: "Research runs" },
  { href: "/events", label: "Event history" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="rail">
      <div className="rail-brand">OmniSignal</div>
      <div className="rail-brand-sub">Control plane</div>
      {links.map((link) => {
        const isActive = link.href === "/" ? pathname === "/" : pathname?.startsWith(link.href);
        return (
          <Link key={link.href} href={link.href} className={`rail-link${isActive ? " active" : ""}`}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
