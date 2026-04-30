import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

// ── Types ─────────────────────────────────────────────────────────────────────

export type JobStatus = "queued" | "processing" | "completed" | "failed" | "finalized";

export interface ProcessingLog {
  id: string;
  event: string;
  message: string | null;
  progress: number;
  created_at: string;
}

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  file_type: string;
  mime_type: string | null;
  status: JobStatus;
  celery_task_id: string | null;
  retry_count: number;
  error_message: string | null;
  progress: number;
  current_stage: string | null;
  extracted_data: Record<string, unknown> | null;
  reviewed_data: Record<string, unknown> | null;
  is_finalized: boolean;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  processing_logs?: ProcessingLog[];
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UploadResponse {
  uploaded: Document[];
  failed: { filename: string; error: string }[];
}

export interface ProgressEvent {
  document_id: string;
  event: string;
  message: string;
  progress: number;
  status: string;
  timestamp: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const uploadDocuments = async (files: File[]): Promise<UploadResponse> => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await api.post<UploadResponse>("/api/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
};

export const listDocuments = async (params: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  sort_by?: string;
  sort_order?: string;
}): Promise<DocumentListResponse> => {
  const { data } = await api.get<DocumentListResponse>("/api/documents", { params });
  return data;
};

export const getDocument = async (id: string): Promise<Document> => {
  const { data } = await api.get<Document>(`/api/documents/${id}`);
  return data;
};

export const updateReview = async (id: string, reviewed_data: unknown): Promise<Document> => {
  const { data } = await api.patch<Document>(`/api/documents/${id}/review`, { reviewed_data });
  return data;
};

export const finalizeDocument = async (id: string, reviewed_data?: unknown): Promise<Document> => {
  const { data } = await api.post<Document>(`/api/documents/${id}/finalize`, { reviewed_data });
  return data;
};

export const retryDocument = async (id: string): Promise<Document> => {
  const { data } = await api.post<Document>(`/api/documents/${id}/retry`);
  return data;
};

export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/api/documents/${id}`);
};

export const getProgressStatus = async (id: string): Promise<ProgressEvent> => {
  const { data } = await api.get<ProgressEvent>(`/api/progress/${id}/status`);
  return data;
};

export const getExportUrl = (id: string, format: "json" | "csv") =>
  `${API_URL}/api/documents/${id}/export/${format}`;

export const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};
