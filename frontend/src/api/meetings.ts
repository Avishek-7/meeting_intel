import { api } from "./client";

export interface ActionItem {
  task: string;
  owner: string;
  due_date: string;
  priority: "high" | "medium" | "low";
}

export interface MeetingMetadata {
  id: string;
  title?: string;
  created_at: string;
  transcript_length?: number;
  summary_preview?: string;
}

export interface MeetingDetail {
  id: string;
  title?: string;
  transcript_text?: string;
  summary_text: string;
  action_items: ActionItem[];
  created_at: string;
  transcription_status?: string;
}

export interface PaginatedMeetings {
  items: MeetingMetadata[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobEnqueueResponse {
  job_id: string;
  status: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  result?: {
    meeting_id?: string;
    summary: string;
    action_items: ActionItem[];
  };
  error?: string;
}

export async function analyzeMeeting(
  transcript: string,
  title?: string
): Promise<JobEnqueueResponse> {
  const { data } = await api.post<JobEnqueueResponse>("/meetings/analyze/async", {
    transcript,
    title,
  });
  return data;
}

export async function uploadAudio(file: File): Promise<JobEnqueueResponse> {
  const form = new FormData();
  form.append("audio", file);
  const { data } = await api.post<JobEnqueueResponse>("/meetings/upload-audio", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await api.get<JobStatusResponse>(`/meetings/jobs/${jobId}`);
  return data;
}

export async function getMeetings(page = 1, pageSize = 20): Promise<PaginatedMeetings> {
  const { data } = await api.get<PaginatedMeetings>("/meetings", {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function getMeetingDetail(id: string): Promise<MeetingDetail> {
  const { data } = await api.get<MeetingDetail>(`/meetings/${id}`);
  return data;
}
