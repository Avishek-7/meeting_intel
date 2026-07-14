import React, { useState } from "react";
import { isAxiosError } from "axios";
import { useNavigate, Link } from "react-router-dom";
import { register } from "../api/auth";
import { useAuth } from "../context/AuthContext";

export default function RegisterPage() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const { user } = await register(email, password, displayName || undefined);
      setUser(user);
      navigate("/");
    } catch (err: unknown) {
      if (isAxiosError(err)) {
        setError(err.response?.data?.detail ?? "Registration failed. Please try again.");
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-container">
      <h1>MeetingIntel</h1>
      <h2>Create account</h2>
      <form onSubmit={handleSubmit} className="auth-form">
        <label>
          Display name (optional)
          <input
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </label>
        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password <span className="hint">(min 8 characters)</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
