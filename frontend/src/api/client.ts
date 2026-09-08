import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    Accept: 'application/json',
  },
  timeout: 30_000,
});

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  task_id: string;
}

export interface Document {
  id: string;
  filename: string;
  status: string;
  page_count: number | null;
  created_at: string;
  processed_at: string | null;
}

export interface JobStatusResult {
  document_id?: string;
  filename?: string;
  status?: string;
  page_count?: number;
  chunk_count?: number;
  fact_count?: number;
  needs_review_count?: number;
  sha256?: string;
}

export interface JobStatusResponse {
  task_id: string;
  status: string;
  result?: JobStatusResult;
  error: string | null;
}

export interface EvidenceRef {
  document_id: string;
  page_number: number;
  chunk_id?: string | null;
  quoted_text: string;
  char_start?: number | null;
  char_end?: number | null;
}

export interface Fact {
  id: string;
  document_id: string;
  chunk_id?: string | null;
  entity_id: string;
  fact_type_id: string;
  attribute: string;
  value: unknown;
  unit?: string | null;
  temporal_scope?: Record<string, unknown> | null;
  evidence: EvidenceRef[];
  confidence: number;
  needs_review: boolean;
  extraction_method: string;
  raw_extraction?: Record<string, unknown> | null;
  created_at?: string;
}

export interface Relationship {
  id: string;
  source_fact_id: string;
  target_fact_id: string;
  relationship_type: string;
  confidence: number;
  explanation: string;
  evidence: string[];
  needs_review: boolean;
  created_at?: string;
}

export async function uploadDocument(
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<DocumentUploadResponse>(
    '/documents/upload',
    formData,
  );

  return response.data;
}

export async function getDocuments(params?: {
  limit?: number;
  offset?: number;
}): Promise<Document[]> {
  const response = await apiClient.get<Document[]>('/documents', {
    params,
  });

  return response.data;
}

export async function getJobStatus(
  taskId: string,
): Promise<JobStatusResponse> {
  const response = await apiClient.get<JobStatusResponse>(
    `/jobs/${encodeURIComponent(taskId)}`,
  );

  return response.data;
}

interface FactListResponse {
  items: Fact[];
  total: number;
  limit: number;
  offset: number;
}

export async function getFacts(params?: {
  document_id?: string;
  entity_id?: string;
  attribute?: string;
  limit?: number;
  offset?: number;
}): Promise<Fact[]> {
  const response = await apiClient.get<FactListResponse>('/facts', {
    params,
  });

  return response.data.items;
}

export async function getFact(factId: string): Promise<Fact> {
  const response = await apiClient.get<Fact>(
    `/facts/${encodeURIComponent(factId)}`,
  );

  return response.data;
}

interface RelationshipListResponse {
  items: Relationship[];
  total: number;
  limit: number;
  offset: number;
}

export async function getRelationships(params?: {
  fact_id?: string;
  relationship_type?: string;
  limit?: number;
  offset?: number;
}): Promise<Relationship[]> {
  const response = await apiClient.get<RelationshipListResponse>(
    '/relationships',
    { params },
  );

  return response.data.items;
}

export async function getRelationship(
  relationshipId: string,
): Promise<Relationship> {
  const response = await apiClient.get<Relationship>(
    `/relationships/${encodeURIComponent(relationshipId)}`,
  );

  return response.data;
}
