import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { speakerService } from '../services/speakerService';
import { Speaker } from '../types';
import { useToast } from './useToast';

export const useSpeakers = (params: {
  page: number;
  limit: number;
  query?: string;
  country?: string;
  bloc?: string;
  sort_by?: string;
  sort_order?: string;
}) => {
  return useQuery({
    queryKey: ['speakers', params],
    queryFn: () => speakerService.getSpeakers(params),
  });
};

export const useSpeaker = (id: string | null) => {
  return useQuery({
    queryKey: ['speaker', id],
    queryFn: () => speakerService.getSpeakerById(id!),
    enabled: !!id,
  });
};

export const useSpeakerStatsSummary = () => {
  return useQuery({
    queryKey: ['speakers', 'stats', 'summary'],
    queryFn: () => speakerService.getStatsSummary(),
  });
};

export const useSpeakerStatsByCountry = () => {
  return useQuery({
    queryKey: ['speakers', 'stats', 'by-country'],
    queryFn: () => speakerService.getStatsByCountry(),
  });
};

export const useSpeakerStatsByBloc = () => {
  return useQuery({
    queryKey: ['speakers', 'stats', 'by-bloc'],
    queryFn: () => speakerService.getStatsByBloc(),
  });
};

export const useSpeakerAppearances = (id: string | null) => {
  return useQuery({
    queryKey: ['speaker', id, 'appearances'],
    queryFn: () => speakerService.getSpeakerAppearances(id!),
    enabled: !!id,
  });
};

export const useSpeakerSentimentHistory = (id: string | null) => {
  return useQuery({
    queryKey: ['speaker', id, 'sentiment-history'],
    queryFn: () => speakerService.getSpeakerSentimentHistory(id!),
    enabled: !!id,
  });
};

export const useCreateSpeaker = () => {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (payload: Partial<Speaker>) => speakerService.createSpeaker(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      toast.success('Konuşmacı başarıyla oluşturuldu.');
    },
    onError: (err: Error) => {
      toast.error(`Konuşmacı oluşturulamadı: ${err.message || err}`);
    },
  });
};

export const useUpdateSpeaker = () => {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Speaker> }) =>
      speakerService.updateSpeaker(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['speakers'] });
      queryClient.invalidateQueries({ queryKey: ['speaker', data.speaker_id] });
      toast.success('Konuşmacı başarıyla güncellendi.');
    },
    onError: (err: Error) => {
      toast.error(`Konuşmacı güncellenemedi: ${err.message || err}`);
    },
  });
};
