import { Calendar, FileText, MapPin, User } from 'lucide-react';
import type { TripletContext } from '@/types';

interface TripletViewProps {
  context: TripletContext;
}

export const TripletView = ({ context }: TripletViewProps) => {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <span className="label-micro">Bağlam (Triplet)</span>
        <div className="border border-hair border-carbon-550 divide-y divide-carbon-550/50">
          {context.prev && (
            <div className="px-4 py-3 bg-carbon-900/50">
              <span className="text-micro text-carbon-500 mb-1 block">Önceki</span>
              <p className="text-sm text-carbon-400 leading-relaxed">{context.prev}</p>
            </div>
          )}
          <div className="px-4 py-4 bg-carbon-900">
            <span className="text-micro text-carbon-50 mb-1 block font-semibold">Mevcut</span>
            <p className="text-base text-carbon-50 leading-relaxed font-medium">
              {context.current}
            </p>
          </div>
          {context.next && (
            <div className="px-4 py-3 bg-carbon-900/50">
              <span className="text-micro text-carbon-500 mb-1 block">Sonraki</span>
              <p className="text-sm text-carbon-400 leading-relaxed">{context.next}</p>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="border border-hair border-carbon-550 p-4">
          <div className="flex items-center gap-2 mb-3">
            <User className="w-3.5 h-3.5 text-carbon-400" strokeWidth={1.5} />
            <span className="label-micro">Konuşmacı</span>
          </div>
          <div className="space-y-1">
            <div className="text-sm font-medium text-carbon-50">{context.speaker.name}</div>
            <div className="text-2xs text-carbon-400">{context.speaker.role}</div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-micro font-mono text-carbon-300">
                Güç: {context.speaker.power_level}/10
              </span>
              <span className="text-micro font-mono text-carbon-400">
                {context.speaker.influence_tier}
              </span>
            </div>
            <div className="text-micro text-carbon-500 mt-1">Blok: {context.speaker.bloc}</div>
          </div>
        </div>

        <div className="border border-hair border-carbon-550 p-4">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-3.5 h-3.5 text-carbon-400" strokeWidth={1.5} />
            <span className="label-micro">Panel</span>
          </div>
          <div className="space-y-1">
            <div className="text-sm font-medium text-carbon-50">{context.panel.theme}</div>
            <div className="text-2xs text-carbon-400 font-mono">{context.panel.file_id}</div>
            <div className="flex items-center gap-2 mt-2">
              <Calendar className="w-3 h-3 text-carbon-500" />
              <span className="text-micro text-carbon-400">{context.panel.date}</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="w-3 h-3 text-carbon-500" />
              <span className="text-micro text-carbon-400">
                Panel #{context.panel.panel_number}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
