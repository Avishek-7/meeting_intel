import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { getMeetings } from "../api/meetings";
import { useAuth } from "../context/AuthContext";

export default function DashboardPage() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => getMeetings(1, 50),
  });

  async function handleSignOut() {
    await signOut();
    navigate("/login");
  }

  return (
    <div className="page-container">
      <header className="dashboard-header">
        <h1>MeetingIntel</h1>
        <div className="header-actions">
          <span className="user-info">{user?.display_name ?? user?.email}</span>
          <Link to="/new" className="btn-primary">+ New meeting</Link>
          <button onClick={handleSignOut} className="btn-outline">Sign out</button>
        </div>
      </header>

      <h2>Your meetings</h2>

      {isLoading && <p>Loading…</p>}
      {isError && <p className="error">Failed to load meetings.</p>}

      {data && data.items.length === 0 && (
        <p>No meetings yet. <Link to="/new">Analyze your first meeting →</Link></p>
      )}

      {data && data.items.length > 0 && (
        <ul className="meeting-list">
          {data.items.map((m) => (
            <li key={m.id} className="meeting-card">
              <Link to={`/meetings/${m.id}`}>
                <h3>{m.title ?? "Untitled meeting"}</h3>
                <p className="meta">{new Date(m.created_at).toLocaleString()}</p>
                {m.summary_preview && (
                  <p className="preview">{m.summary_preview.slice(0, 140)}…</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
