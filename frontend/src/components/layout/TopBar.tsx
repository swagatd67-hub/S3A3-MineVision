export default function TopBar() {
  return (
    <header className="topbar">
      <div>
        <span className="topbar-label">PIPE INSPECTION COMMAND</span>
        <h1>PipeVision</h1>
      </div>

      <div className="system-status">
        <span className="status-dot" />
        System Online
      </div>
    </header>
  );
}