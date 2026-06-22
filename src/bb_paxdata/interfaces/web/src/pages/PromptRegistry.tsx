import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/apiClient';
import type { PromptListResponse } from '@/types';
import { BookOpen, Hash, Clock, FileText } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';

export const PromptRegistry = () => {
  const { t } = useTranslation();
  const { data, isPending, isError } = useQuery({
    queryKey: ['prompts'],
    queryFn: async () => {
      return apiClient.get<PromptListResponse>('/api/v1/prompts/');
    },
    staleTime: 1000 * 60 * 10, // 10 dk - prompt registry changes infrequently
  });

  if (isPending) {
    return (
      <div className="space-y-8">
        <div className="h-80 shimmer" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="border border-carbon-550 bg-carbon-900 p-6 text-sm text-carbon-300">
        <p className="font-semibold text-carbon-50">Prompt verileri alınamadı.</p>
      </div>
    );
  }

  const promptEntries = Object.entries(data.prompts);

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            {t('prompts.title')}
          </h1>
          <p className="text-sm text-carbon-400 mt-1">{t('prompts.desc')}</p>
        </div>
      </div>

      <div className="space-y-6">
        {promptEntries.length === 0 ? (
          <div className="text-sm text-carbon-400">Henüz kayıtlı prompt yok.</div>
        ) : (
          promptEntries.map(([name, versions]) => (
            <div key={name} className="bg-carbon-900 border border-hair border-carbon-550 p-6">
              <h2 className="text-lg font-semibold text-carbon-50 mb-4 capitalize">
                {name.replace('_', ' ')}
              </h2>
              <div className="space-y-4">
                {versions.map((v) => (
                  <div
                    key={v.version_id}
                    className="border border-carbon-600 bg-carbon-800 p-4 flex flex-col gap-3"
                  >
                    <div className="flex items-center justify-between border-b border-carbon-700 pb-2">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-carbon-400" />
                        <span className="font-mono text-sm text-signal-pass">{v.version_id}</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-carbon-400">
                        <div className="flex items-center gap-1">
                          <Hash className="w-3 h-3" />
                          <span className="font-mono">{v.content_hash.substring(0, 8)}...</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{new Date(v.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>

                    <div className="bg-carbon-950 p-3 text-sm font-mono text-carbon-300 whitespace-pre-wrap overflow-auto max-h-40">
                      {v.content}
                    </div>

                    {v.academic_ref && (
                      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-carbon-700">
                        <BookOpen className="w-4 h-4 text-signal-warn" />
                        <span className="text-xs font-semibold text-carbon-200">
                          Akademik Referans:
                        </span>
                        <span className="text-xs text-carbon-300 bg-carbon-700 px-2 py-0.5 rounded">
                          {v.academic_ref}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
