import { Link, useLocation } from "react-router-dom";

const links = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Analytics", to: "/analytics" },
  { label: "Live Cockpit", to: "/missions/M-104/live" },
  { label: "Missions", to: "/missions" },
  { label: "Findings", to: "/findings" },
  { label: "Reports", to: "/reports" },
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
          return (
            <Link
              key={link.to}
              to={link.to}
              aria-current={active ? "page" : undefined}
              className={active ? "nav-item active" : "nav-item"}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}