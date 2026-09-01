import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  BarChart2,
  Tv,
  Compass,
  ShieldAlert,
  FileText,
} from "lucide-react";

const links = [
  { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { label: "Analytics", to: "/analytics", icon: BarChart2 },
  { label: "Live Cockpit", to: "/missions/M-104/live", icon: Tv },
  { label: "Missions", to: "/missions", icon: Compass },
  { label: "Findings", to: "/findings", icon: ShieldAlert },
  { label: "Reports", to: "/reports", icon: FileText },
];

export default function Sidebar() {
  const location = useLocation();
  const { pathname } = location;

  const isLinkActive = (to: string) => {
    if (to === "/dashboard") {
      return pathname === "/dashboard" || pathname === "/";
    }
    if (to === "/analytics") {
      return pathname.startsWith("/analytics");
    }
    if (to === "/missions/M-104/live") {
      return pathname.includes("/live");
    }
    if (to === "/findings") {
      return pathname.includes("/findings");
    }
    if (to === "/reports") {
      return pathname.startsWith("/reports");
    }
    if (to === "/missions") {
      return (
        pathname.startsWith("/missions") &&
        !pathname.includes("/live") &&
        !pathname.includes("/findings")
      );
    }
    return false;
  };

  return (
    <aside className="sidebar" aria-label="Sidebar Navigation">
      <div className="sidebar-brand">
        <div className="brand-mark">P</div>
        <div>
          <strong>PipeVision</strong>
          <span>Inspection System</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Main Navigation">
        {links.map((link) => {
          const active = isLinkActive(link.to);
          const Icon = link.icon;
          return (
            <Link
              key={link.to}
              to={link.to}
              aria-current={active ? "page" : undefined}
              className={active ? "nav-item active" : "nav-item"}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}