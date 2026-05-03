import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getMeetingDetail } from "../api/meetings";

const PRIORITY_BADGE: Record<string, string> = {
  high: "badge-red",
  medium: "badge-yellow",
  low: "badge-green",
};

export default function MeetingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => getMeetingDetail(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="page-container"><p>Loading…</p></div>;
  if (isError || !data) return (
    <div className="page-container">
      <p className="error">Meeting not found or you don't have access.</p>
      <Link to="/">← Back to dashboard</Link>
    </div>
  );

  return (
    <div className="page-container">
      <Link to="/" className="back-link">← Dashboard</Link>
      <h2>{data.title ?? "Untitled meeting"}</h2>
      <p className="meta">{new Date(data.created_at).toLocaleString()}</p>

      {data.transcription_status && data.transcription_status !== "done" && (
        <div className="status-banner">
          Transcription status: <strong>{data.transcription_status}</strong>
        </div>
      )}

      <section>
        <h3>Summary</h3>
        <p className="summary-text">{data.summary_text}</p>
      </section>

      {Array.isArray(data.action_items) && data.action_items.length > 0 && (
        <section>
          <h3>Action items ({data.action_items.length})</h3>
          <ul className="action-items">
            {data.action_items.map((item, i) => (
              <li key={i} className="action-item">
                <span className={`badge ${PRIORITY_BADGE[item.priority] ?? ""}`}>
                  {item.priority}
                </span>
                <strong>{item.task}</strong>
                <span className="meta">
                  {item.owner !== "Not specified" && `Owner: ${item.owner} · `}
                  {item.due_date !== "N/A" && `Due: ${item.due_date}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.transcript_text && (
        <details className="transcript-section">
          <summary>View full transcript</summary>
          <pre className="transcript-text">{data.transcript_text}</pre>
        </details>
      )}
    </div>
  );
}
