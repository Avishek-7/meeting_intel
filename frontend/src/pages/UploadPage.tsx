import React, { useState, useRef, useEffect } from "react";
import { isAxiosError } from "axios";
import { useNavigate } from "react-router-dom";
import { analyzeMeeting, uploadAudio, getJobStatus } from "../api/meetings";

type Mode = "transcript" | "audio";
type JobState = "idle" | "queued" | "processing" | "done" | "failed";

export default function UploadPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("transcript");
  const [transcript, setTranscript] = useState("");
  const [title, setTitle] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [jobState, setJobState] = useState<JobState>("idle");
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  function startPolling(jobId: string) {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId);
        if (status.status === "finished" || status.status === "complete") {
          clearInterval(pollRef.current!);
          setJobState("done");
          if (status.result?.meeting_id) {
            navigate(`/meetings/${status.result.meeting_id}`);
          }
        } else if (status.status === "failed") {
          clearInterval(pollRef.current!);
          setJobState("failed");
          setError(status.error ?? "Job failed");
        } else {
          setJobState("processing");
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 2000);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setJobState("queued");

    try {
      if (mode === "transcript") {
        if (transcript.trim().length < 10) {
          setError("Transcript must be at least 10 characters.");
          setJobState("idle");
          return;
        }
        const { job_id } = await analyzeMeeting(transcript, title || undefined);
        startPolling(job_id);
      } else {
        if (!audioFile) {
          setError("Please select an audio file.");
          setJobState("idle");
          return;
        }
        const { job_id } = await uploadAudio(audioFile);
        startPolling(job_id);
      }
    } catch (err: unknown) {
      if (isAxiosError(err)) {
        setError(err.response?.data?.detail ?? "Submission failed.");
      } else {
        setError("Submission failed.");
      }
      setJobState("failed");
    }
  }

  return (
    <div className="page-container">
      <h2>New Meeting</h2>

      <div className="tab-bar">
        <button
          className={mode === "transcript" ? "tab active" : "tab"}
          onClick={() => setMode("transcript")}
        >
          Paste transcript
        </button>
        <button
          className={mode === "audio" ? "tab active" : "tab"}
          onClick={() => setMode("audio")}
        >
          Upload audio
        </button>
      </div>

      <form onSubmit={handleSubmit} className="upload-form">
        <label>
          Meeting title (optional)
          <input
            type="text"
            value={title}
            maxLength={500}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>

        {mode === "transcript" && (
          <label>
            Transcript
            <textarea
              rows={12}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Paste your meeting transcript here…"
              required
            />
          </label>
        )}

        {mode === "audio" && (
          <label>
            Audio file <span className="hint">(audio/*, video/mp4, video/webm — max 200 MB)</span>
            <input
              ref={fileRef}
              type="file"
              accept="audio/*,video/mp4,video/webm"
              onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
              required
            />
          </label>
        )}

        {error && <p className="error">{error}</p>}

        {jobState === "idle" || jobState === "failed" ? (
          <button type="submit">Analyze</button>
        ) : (
          <p className="status-message">
            {jobState === "queued" && "Queued…"}
            {jobState === "processing" && "Processing… this may take a minute."}
            {jobState === "done" && "Done! Redirecting…"}
          </p>
        )}
      </form>
    </div>
  );
}
