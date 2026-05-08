export default function Footer() {
  return (
    <footer className="mi-footer">
      <p>© {new Date().getFullYear()} MeetingIntel</p>
      <p className="mi-footer-muted">AI summaries and action items from your meetings.</p>
    </footer>
  );
}