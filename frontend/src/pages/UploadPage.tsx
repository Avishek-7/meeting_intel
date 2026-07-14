import React, { useState, useRef, useEffect } from "react";
import { isAxiosError } from "axios";
import { useNavigate } from "react-router-dom";
import {
  analyzeMeeting,
  uploadAudio,
  getJobStatus,
  createLiveTranscriptionWebSocket,
  type LiveTranscriptionEvent,
} from "../api/meetings";
import Layout from "../components/common/Layout";

type Mode = "transcript" | "audio" | "live";
type JobState = "idle" | "queued" | "processing" | "done" | "failed";

export default function UploadPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("transcript");
  const [transcript, setTranscript] = useState("");
  const [title, setTitle] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [isLiveRecording, setIsLiveRecording] = useState(false);
  const [liveStatus, setLiveStatus] = useState("Idle");
  const [jobState, setJobState] = useState<JobState>("idle");
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recorderRestartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const liveStopRequestedRef = useRef(false);

  function clearRecorderRestartTimer() {
    if (recorderRestartTimerRef.current) {
      clearTimeout(recorderRestartTimerRef.current);
      recorderRestartTimerRef.current = null;
    }
  }

  function scheduleRecorderRestart(recorder: MediaRecorder) {
    clearRecorderRestartTimer();
    recorderRestartTimerRef.current = setTimeout(() => {
      if (liveStopRequestedRef.current || recorder.state !== "recording") {
        return;
      }
      recorder.stop();
    }, 1200);
  }

  function finalizeLiveSocket() {
    const socket = wsRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ event: "finalize" }));
    }
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      liveStopRequestedRef.current = true;
      clearRecorderRestartTimer();
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      } else {
        finalizeLiveSocket();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
        wsRef.current.close();
      }
    };
  }, []);

  async function startLiveRecording() {
    setError("");
    setLiveStatus("Starting microphone...");
    setLiveTranscript("");
    liveStopRequestedRef.current = false;

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Live transcription is not supported in this browser.");
      setLiveStatus("Unavailable");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const ws = createLiveTranscriptionWebSocket();
      wsRef.current = ws;

      ws.onopen = () => {
        setLiveStatus("Connected");
      };

      ws.onmessage = (event) => {
        try {
          const payload: LiveTranscriptionEvent = JSON.parse(event.data);
          if (payload.event === "ready") {
            setLiveStatus("Listening...");
            return;
          }
          if (payload.event === "partial") {
            const fullText = payload.full_text ?? payload.text ?? "";
            setLiveTranscript(fullText);
            setTranscript(fullText);
            setLiveStatus("Transcribing...");
            return;
          }
          if (payload.event === "final") {
            if (payload.text) {
              setLiveTranscript(payload.text);
              setTranscript(payload.text);
            }
            setLiveStatus("Finalized");
            return;
          }
          if (payload.event === "error") {
            setError(payload.detail ?? "Live transcription error.");
            setLiveStatus("Error");
          }
        } catch {
          // ignore malformed event
        }
      };

      ws.onerror = () => {
        setError("WebSocket error during live transcription.");
        setLiveStatus("Error");
      };

      ws.onclose = () => {
        setLiveStatus((prev) => (prev === "Finalized" ? prev : "Disconnected"));
      };

      const preferredMimeType = "audio/webm;codecs=opus";
      const options = MediaRecorder.isTypeSupported(preferredMimeType)
        ? { mimeType: preferredMimeType }
        : undefined;
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = async (evt: BlobEvent) => {
        if (!evt.data || evt.data.size === 0) {
          return;
        }
        const socket = wsRef.current;
        if (!socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }
        const buffer = await evt.data.arrayBuffer();
        socket.send(buffer);
      };

      recorder.onstop = () => {
        if (liveStopRequestedRef.current) {
          finalizeLiveSocket();
          return;
        }

        recorder.start();
        scheduleRecorderRestart(recorder);
      };

      recorder.start();
      scheduleRecorderRestart(recorder);
      setIsLiveRecording(true);
      setLiveStatus("Listening...");
    } catch {
      setError("Unable to access your microphone.");
      setLiveStatus("Unavailable");
    }
  }

  function stopLiveRecording() {
    liveStopRequestedRef.current = true;
    clearRecorderRestartTimer();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    } else {
      finalizeLiveSocket();
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    setIsLiveRecording(false);
    setLiveStatus("Stopped");
  }

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
      } else if (mode === "live") {
        const text = liveTranscript.trim() || transcript.trim();
        if (text.length < 10) {
          setError("Record a longer live transcript before analyzing.");
          setJobState("idle");
          return;
        }
        const { job_id } = await analyzeMeeting(text, title || undefined);
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
    <Layout title="New Meeting" subtitle="Upload audio or paste transcript" showSidebar>
      <div className="page-container">
        <div className="mi-section-head">
          <h2>Create analysis job</h2>
          <span className="mi-count-pill">Async processing</span>
        </div>

        <div className="tab-bar">
          <button
            type="button"
            className={mode === "transcript" ? "tab active" : "tab"}
            onClick={() => setMode("transcript")}
          >
            Paste transcript
          </button>
          <button
            type="button"
            className={mode === "audio" ? "tab active" : "tab"}
            onClick={() => setMode("audio")}
          >
            Upload audio
          </button>
          <button
            type="button"
            className={mode === "live" ? "tab active" : "tab"}
            onClick={() => setMode("live")}
          >
            Live audio
          </button>
        </div>

        <div className="mi-content-panel">
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

            {mode === "live" && (
              <div className="live-controls">
                <div className="live-row">
                  {!isLiveRecording ? (
                    <button type="button" onClick={startLiveRecording}>Start live capture</button>
                  ) : (
                    <button type="button" className="btn-outline" onClick={stopLiveRecording}>
                      Stop live capture
                    </button>
                  )}
                  <span className="hint">Status: {liveStatus}</span>
                </div>
                <label>
                  Live transcript
                  <textarea
                    rows={10}
                    value={liveTranscript}
                    onChange={(e) => {
                      setLiveTranscript(e.target.value);
                      setTranscript(e.target.value);
                    }}
                    placeholder="Live transcript will appear here..."
                  />
                </label>
              </div>
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
      </div>
    </Layout>
  );
}
