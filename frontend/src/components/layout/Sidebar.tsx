import { NavLink } from "react-router-dom";

const links = [
  { label: "Dashboard", to: "/dashboard" },
  { label: "Missions", to: "/missions" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">P</div>
        <div>
          <strong>PipeVision</strong>
          <span>Inspection System</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              isActive ? "nav-item active" : "nav-item"
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}