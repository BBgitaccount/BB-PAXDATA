// src/bb_paxdata/interfaces/web/src/api/visualizationApi.ts

import type {
  BilateralFlow,
  CountryNode,
  CountryRiskProfile,
  ReferenceContext,
  ReferenceFlow,
  RelationshipType,
  SentimentMatrix,
  SessionTimeline,
} from '../types/visualization';

interface ImportMetaEnv {
  VITE_API_BASE_URL?: string;
  VITE_API_URL?: string;
}

interface CustomImportMeta {
  env: ImportMetaEnv;
}

const BASE_URL =
  (import.meta as unknown as CustomImportMeta).env?.VITE_API_BASE_URL ||
  (import.meta as unknown as CustomImportMeta).env?.VITE_API_URL ||
  'http://localhost:8000';

/**
 * Recursively converts object keys from snake_case to camelCase
 */
export function camelizeKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(camelizeKeys);
  } else if (
    obj !== null &&
    obj !== undefined &&
    typeof obj === 'object' &&
    obj.constructor === Object
  ) {
    const record = obj as Record<string, unknown>;
    const newObj: Record<string, unknown> = {};
    for (const key of Object.keys(record)) {
      const camelKey = key.replace(/_([a-z0-9])/g, (_, letter) => letter.toUpperCase());
      newObj[camelKey] = camelizeKeys(record[key]);
    }
    return newObj;
  }
  return obj;
}

/**
 * Recursively converts object keys from camelCase to snake_case
 */
export function decamelizeKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.map(decamelizeKeys);
  } else if (
    obj !== null &&
    obj !== undefined &&
    typeof obj === 'object' &&
    obj.constructor === Object
  ) {
    const record = obj as Record<string, unknown>;
    const newObj: Record<string, unknown> = {};
    for (const key of Object.keys(record)) {
      const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
      newObj[snakeKey] = decamelizeKeys(record[key]);
    }
    return newObj;
  }
  return obj;
}

/**
 * Encodes query parameters converting camelCase keys to snake_case
 * and correctly handling array values (multi-value query params).
 */
function buildQueryString(params: object): string {
  const parts: string[] = [];
  const snakeParams = decamelizeKeys(params) as Record<string, unknown>;
  for (const key of Object.keys(snakeParams)) {
    const val = snakeParams[key];
    if (val === undefined || val === null) continue;
    if (Array.isArray(val)) {
      for (const item of val) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`);
      }
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(val))}`);
    }
  }
  return parts.length > 0 ? `?${parts.join('&')}` : '';
}

/**
 * Base request fetch wrapper
 */
async function apiRequest<T>(path: string, params: object = {}, signal?: AbortSignal): Promise<T> {
  const queryStr = buildQueryString(params);
  const url = `${BASE_URL}/api/v1/viz${path}${queryStr}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    let message = 'API Error';
    try {
      const parsed = JSON.parse(errorText);
      message = parsed.detail || parsed.message || message;
    } catch {
      message = errorText || message;
    }
    throw new Error(message);
  }

  const rawJson = await response.json();
  return camelizeKeys(rawJson) as T;
}

export interface GetCountryNodesParams {
  sessionId?: string[];
  relationshipType?: RelationshipType[];
}

export function getCountryNodes(
  params?: GetCountryNodesParams,
  signal?: AbortSignal,
): Promise<CountryNode[]> {
  return apiRequest<CountryNode[]>('/country-nodes', params || {}, signal);
}

export interface GetBilateralFlowsParams {
  sessionId?: string[];
  minInteractions?: number;
  relationshipTypes?: RelationshipType[];
  minAffinity?: number;
}

export function getBilateralFlows(
  params?: GetBilateralFlowsParams,
  signal?: AbortSignal,
): Promise<BilateralFlow[]> {
  return apiRequest<BilateralFlow[]>('/bilateral-flows', params || {}, signal);
}

export function getSentimentMatrix(signal?: AbortSignal): Promise<SentimentMatrix> {
  return apiRequest<SentimentMatrix>('/sentiment-matrix', {}, signal);
}

export function getSessionTimeline(signal?: AbortSignal): Promise<SessionTimeline[]> {
  return apiRequest<SessionTimeline[]>('/session-timeline', {}, signal);
}

export interface GetReferenceFlowsParams {
  sessionId?: string;
  contextType?: ReferenceContext;
}

export function getReferenceFlows(
  params?: GetReferenceFlowsParams,
  signal?: AbortSignal,
): Promise<ReferenceFlow[]> {
  return apiRequest<ReferenceFlow[]>('/reference-flows', params || {}, signal);
}

export function getCountryRiskProfile(
  country: string,
  signal?: AbortSignal,
): Promise<CountryRiskProfile> {
  return apiRequest<CountryRiskProfile>('/country-risk-profile', { country }, signal);
}
