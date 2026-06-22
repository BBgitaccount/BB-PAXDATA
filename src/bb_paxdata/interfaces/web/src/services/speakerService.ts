import { apiClient } from './apiClient';
import {
  PaginatedSpeakers,
  Speaker,
  SpeakerStatsSummary,
  SpeakerCountryDistribution,
  SpeakerBlocDistribution,
  SpeakerAppearance,
  SpeakerSentimentHistory,
} from '../types';

export const speakerService = {
  getSpeakers: async (params: {
    page: number;
    limit: number;
    query?: string;
    country?: string;
    bloc?: string;
    sort_by?: string;
    sort_order?: string;
  }): Promise<PaginatedSpeakers> => {
    const queryParams = new URLSearchParams();
    queryParams.append('page', params.page.toString());
    queryParams.append('limit', params.limit.toString());
    if (params.query) queryParams.append('query', params.query);
    if (params.country) queryParams.append('country', params.country);
    if (params.bloc) queryParams.append('bloc', params.bloc);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);

    return apiClient.get<PaginatedSpeakers>(`/api/v1/speakers?${queryParams.toString()}`);
  },

  getSpeakerById: async (id: string): Promise<Speaker> => {
    return apiClient.get<Speaker>(`/api/v1/speakers/${id}`);
  },

  getStatsSummary: async (): Promise<SpeakerStatsSummary> => {
    return apiClient.get<SpeakerStatsSummary>('/api/v1/speakers/stats/summary');
  },

  getStatsByCountry: async (): Promise<SpeakerCountryDistribution[]> => {
    return apiClient.get<SpeakerCountryDistribution[]>('/api/v1/speakers/stats/by-country');
  },

  getStatsByBloc: async (): Promise<SpeakerBlocDistribution[]> => {
    return apiClient.get<SpeakerBlocDistribution[]>('/api/v1/speakers/stats/by-bloc');
  },

  getSpeakerAppearances: async (id: string): Promise<SpeakerAppearance[]> => {
    return apiClient.get<SpeakerAppearance[]>(`/api/v1/speakers/${id}/appearances`);
  },

  getSpeakerSentimentHistory: async (id: string): Promise<SpeakerSentimentHistory[]> => {
    return apiClient.get<SpeakerSentimentHistory[]>(`/api/v1/speakers/${id}/sentiment-history`);
  },

  createSpeaker: async (payload: Partial<Speaker>): Promise<Speaker> => {
    return apiClient.post<Speaker>('/api/v1/speakers', payload);
  },

  updateSpeaker: async (id: string, payload: Partial<Speaker>): Promise<Speaker> => {
    return apiClient.put<Speaker>(`/api/v1/speakers/${id}`, payload);
  },
};
