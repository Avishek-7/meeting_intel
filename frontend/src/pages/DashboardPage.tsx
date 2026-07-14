import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { getMeetings } from "../api/meetings";
import { useAuth } from "../context/AuthContext";
import Layout from "../components/common/Layout";
import LogoutButton from "../components/common/LogoutButton";
import ReusableCard from "../components/common/ReusableCard";

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => getMeetings(1, 50),
  });

  function formatCreatedAt(value: string) {
    const createdAtDate = new Date(value);
    return Number.isNaN(createdAtDate.getTime()) ? "Unknown date" : createdAtDate.toLocaleString();
  }

  const totalMeetings = data?.items.length ?? 0;

  return (
    <Layout
      title="MeetingIntel"
      subtitle="Meeting summaries, action items, and searchable history"
      showSidebar
      headerRight={
        <div className="header-actions">
          <span className="user-info">{user?.display_name ?? user?.email}</span>
          <Link to="/new" className="btn-primary">
            + New meeting
          </Link>
          <LogoutButton />
        </div>
      }
    >
      <div className="page-container">
        <div className="mi-section-head">
          <h2>Your meetings</h2>
          <span className="mi-count-pill">{totalMeetings} total</span>
        </div>

        {isLoading && <p>Loading…</p>}
        {isError && <p className="error">Failed to load meetings.</p>}

        {data && data.items.length === 0 && (
          <ReusableCard
            title="No meetings yet"
            description="Upload audio or paste transcript to generate your first summary."
            buttonText="Create first meeting"
            onButtonClick={() => navigate("/new")}
          />
        )}

        {data && data.items.length > 0 && (
          <ul className="meeting-list mi-elevated-list">
            {data.items.map((m) => (
              <li key={m.id} className="meeting-card">
                <Link to={`/meetings/${m.id}`}>
                  <div className="mi-card-topline">
                    <span className="mi-status-dot" aria-hidden="true" />
                    <p className="meta">{formatCreatedAt(m.created_at)}</p>
                  </div>
                  <h3>{m.title ?? "Untitled meeting"}</h3>
                  {m.summary_preview && (
                    <p className="preview">
                      {m.summary_preview.length > 140
                        ? `${m.summary_preview.slice(0, 140)}…`
                        : m.summary_preview}
                    </p>
                  )}
                  <p className="mi-link-hint">Open meeting details</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Layout>
  );
}
