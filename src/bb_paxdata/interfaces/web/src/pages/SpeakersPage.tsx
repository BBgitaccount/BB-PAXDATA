import { useState, useMemo } from 'react';
import {
  useSpeakers,
  useSpeakerStatsSummary,
  useSpeakerStatsByCountry,
  useSpeakerStatsByBloc,
  useSpeakerAppearances,
  useSpeakerSentimentHistory,
  useCreateSpeaker,
  useUpdateSpeaker,
  useSpeaker,
} from '@/hooks/useSpeakers';
import {
  Users,
  Plus,
  Search,
  Filter,
  Award,
  Globe,
  RefreshCw,
  X,
  Check,
  TrendingUp,
  Sliders,
  ChevronLeft,
  ChevronRight,
  Briefcase,
  Calendar,
  Layers,
  MapPin,
  Building,
} from 'lucide-react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts';
import { cn } from '@/utils/helpers';
import { Speaker } from '@/types';

const CHART_COLORS = ['#f4f4f5', '#e4e4e7', '#d4d4d8', '#a1a1aa', '#71717a', '#52525b', '#3f3f46'];

export const SpeakersPage = () => {
  // Page parameters state
  const [page, setPage] = useState(1);
  const [limit] = useState(15);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [blocFilter, setBlocFilter] = useState('');
  const [sortBy, setSortBy] = useState('canonical_name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Modal & Drawer State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // New Speaker Form State
  const [newSpeaker, setNewSpeaker] = useState({
    canonical_name: '',
    display_name: '',
    country_code: '',
    country_name: '',
    bloc: '',
    power_level: 0.5,
    role: 'panelist',
    title: '',
    organization: '',
    is_active: true,
  });

  // Queries
  const { data: statsSummary, refetch: refetchSummary } = useSpeakerStatsSummary();
  const { data: statsByCountry, refetch: refetchCountry } = useSpeakerStatsByCountry();
  const { data: statsByBloc, refetch: refetchBloc } = useSpeakerStatsByBloc();

  const {
    data: speakersData,
    isLoading,
    isFetching,
    refetch: refetchList,
  } = useSpeakers({
    page,
    limit,
    query: debouncedSearch,
    country: countryFilter || undefined,
    bloc: blocFilter || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  // Selected Speaker Detail Queries
  const { data: speakerDetail } = useSpeaker(selectedSpeakerId);
  const { data: appearances } = useSpeakerAppearances(selectedSpeakerId);
  const { data: sentimentHistory } = useSpeakerSentimentHistory(selectedSpeakerId);

  // Mutations
  const createSpeakerMutation = useCreateSpeaker();
  const updateSpeakerMutation = useUpdateSpeaker();

  // Search Debounce Handler
  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    const timeoutId = setTimeout(() => {
      setDebouncedSearch(val);
      setPage(1);
    }, 500);
    return () => clearTimeout(timeoutId);
  };

  const handleRefreshAll = () => {
    void refetchSummary();
    void refetchCountry();
    void refetchBloc();
    void refetchList();
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
    setPage(1);
  };

  // Add Speaker Form Submit
  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSpeaker.canonical_name) return;

    try {
      await createSpeakerMutation.mutateAsync({
        canonical_name: newSpeaker.canonical_name,
        display_name: newSpeaker.display_name || null,
        country_code: newSpeaker.country_code || null,
        country_name: newSpeaker.country_name || null,
        bloc: newSpeaker.bloc || null,
        power_level: newSpeaker.power_level,
        role: newSpeaker.role,
        title: newSpeaker.title || null,
        organization: newSpeaker.organization || null,
        is_active: newSpeaker.is_active,
        aliases: [newSpeaker.canonical_name],
        metadata: {},
      });
      setIsAddModalOpen(false);
      setNewSpeaker({
        canonical_name: '',
        display_name: '',
        country_code: '',
        country_name: '',
        bloc: '',
        power_level: 0.5,
        role: 'panelist',
        title: '',
        organization: '',
        is_active: true,
      });
    } catch {
      // Handled by mutation hook toasts
    }
  };

  // Detail Drawer Update Action
  const [editFields, setEditFields] = useState<Partial<Speaker>>({});
  const [newAlias, setNewAlias] = useState('');

  const openSpeakerDrawer = (speaker: Speaker) => {
    setSelectedSpeakerId(speaker.speaker_id);
    setEditFields({
      display_name: speaker.display_name,
      title: speaker.title,
      organization: speaker.organization,
      power_level: speaker.power_level,
      is_active: speaker.is_active,
      aliases: speaker.aliases || [],
    });
    setIsDrawerOpen(true);
  };

  const handleSaveDrawer = async () => {
    if (!selectedSpeakerId) return;
    try {
      await updateSpeakerMutation.mutateAsync({
        id: selectedSpeakerId,
        payload: editFields,
      });
    } catch {
      // Toast handles error feedback
    }
  };

  const handleAddAlias = () => {
    if (!newAlias.trim()) return;
    const currentAliases = editFields.aliases || [];
    if (!currentAliases.includes(newAlias.trim())) {
      setEditFields({
        ...editFields,
        aliases: [...currentAliases, newAlias.trim()],
      });
    }
    setNewAlias('');
  };

  const handleRemoveAlias = (aliasToRemove: string) => {
    const currentAliases = editFields.aliases || [];
    setEditFields({
      ...editFields,
      aliases: currentAliases.filter((a) => a !== aliasToRemove),
    });
  };

  // TanStack Table Column Definitions
  const columnHelper = createColumnHelper<Speaker>();
  const columns = useMemo(
    () => [
      columnHelper.accessor('canonical_name', {
        header: () => (
          <button
            type="button"
            onClick={() => handleSort('canonical_name')}
            className="flex items-center gap-1 hover:text-carbon-50"
          >
            KONUŞMACI ADI {sortBy === 'canonical_name' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        ),
        cell: (info) => {
          const s = info.row.original;
          return (
            <div className="flex flex-col">
              <span className="font-semibold text-carbon-100 tracking-tight">
                {s.canonical_name}
              </span>
              {s.display_name && (
                <span className="text-3xs text-carbon-400 font-normal mt-0.5">
                  ({s.display_name})
                </span>
              )}
            </div>
          );
        },
      }),
      columnHelper.accessor('country_code', {
        header: () => (
          <button
            type="button"
            onClick={() => handleSort('country_code')}
            className="flex items-center gap-1 hover:text-carbon-50"
          >
            ÜLKE {sortBy === 'country_code' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        ),
        cell: (info) => {
          const s = info.row.original;
          return (
            <div className="flex items-center gap-2">
              {s.country_code ? (
                <span className="px-1.5 py-0.5 rounded text-3xs font-mono font-bold bg-carbon-800 text-carbon-300 border border-carbon-700">
                  {s.country_code}
                </span>
              ) : (
                <span className="text-carbon-500 italic text-2xs">—</span>
              )}
              {s.country_name && (
                <span className="text-2xs text-carbon-350 hidden sm:inline">{s.country_name}</span>
              )}
            </div>
          );
        },
      }),
      columnHelper.accessor('bloc', {
        header: () => (
          <button
            type="button"
            onClick={() => handleSort('bloc')}
            className="flex items-center gap-1 hover:text-carbon-50"
          >
            BLOK {sortBy === 'bloc' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        ),
        cell: (info) =>
          info.getValue() ? (
            <span className="text-2xs text-carbon-300 capitalize">{info.getValue()}</span>
          ) : (
            <span className="text-carbon-500 italic text-2xs">—</span>
          ),
      }),
      columnHelper.accessor('power_level', {
        header: () => (
          <button
            type="button"
            onClick={() => handleSort('power_level')}
            className="flex items-center gap-1 hover:text-carbon-50"
          >
            GÜÇ SEVİYESİ {sortBy === 'power_level' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        ),
        cell: (info) => {
          const val = info.getValue();
          if (val === null) return <span className="text-carbon-500 italic text-2xs">—</span>;
          const percentage = Math.round(val * 100);
          return (
            <div className="flex items-center gap-2 min-w-[100px]">
              <div className="flex-1 bg-carbon-800 h-1.5 rounded-full overflow-hidden border border-carbon-750">
                <div
                  className="bg-zinc-400 h-full transition-all"
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <span className="font-mono text-2xs font-bold text-carbon-200">
                {(val * 10).toFixed(1)}
              </span>
            </div>
          );
        },
      }),
      columnHelper.accessor('appearance_count', {
        header: () => (
          <button
            type="button"
            onClick={() => handleSort('appearance_count')}
            className="flex items-center gap-1 hover:text-carbon-50"
          >
            KATILIM {sortBy === 'appearance_count' && (sortOrder === 'asc' ? '↑' : '↓')}
          </button>
        ),
        cell: (info) => (
          <span className="font-mono text-2xs font-bold text-carbon-250 font-tabular">
            {info.getValue()} panel
          </span>
        ),
      }),

      columnHelper.display({
        id: 'actions',
        header: '',
        cell: (info) => (
          <button
            type="button"
            onClick={() => openSpeakerDrawer(info.row.original)}
            className="px-2.5 py-1 text-3xs uppercase tracking-diplomatic text-carbon-350 hover:text-carbon-50 border border-carbon-700 hover:bg-carbon-800 transition-all font-medium rounded"
          >
            İncele
          </button>
        ),
      }),
    ],
    [sortBy, sortOrder],
  );

  const table = useReactTable({
    data: speakersData?.items || [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="space-y-8 animate-[fade-in-up_300ms_ease-out_both] text-carbon-200">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-carbon-50">
            Konuşmacı Master Veri Tabanı
          </h1>
          <p className="text-sm text-carbon-450 mt-1">
            Diplomatik analiz platformunun merkezi aktör master listeleri ve söylem profilleri
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRefreshAll}
            className="btn-secondary flex items-center justify-center p-2 border-carbon-700 hover:bg-carbon-800"
            title="Yenile"
          >
            <RefreshCw className={cn('w-4 h-4 text-carbon-400', isFetching && 'animate-spin')} />
          </button>
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="btn-primary flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-carbon-900 bg-carbon-50 hover:bg-carbon-200 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Konuşmacı Ekle
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-24">
          <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" />
            Toplam Aktör
          </span>
          <div className="text-xl font-mono font-bold text-carbon-100">
            {statsSummary?.total_speakers ?? '—'}
          </div>
        </div>

        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-24">
          <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
            <Check className="w-3.5 h-3.5" />
            Aktif Kayıtlar
          </span>
          <div className="text-xl font-mono font-bold text-carbon-100">
            {statsSummary?.active_speakers ?? '—'}
          </div>
        </div>

        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-24">
          <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5" />
            Ülke Temsiliyeti
          </span>
          <div className="text-xl font-mono font-bold text-carbon-100">
            {statsSummary?.represented_countries ?? '—'}
          </div>
        </div>

        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 flex flex-col justify-between h-24">
          <span className="text-3xs font-semibold tracking-wider text-carbon-450 uppercase flex items-center gap-1.5">
            <Award className="w-3.5 h-3.5" />
            Ortalama Güç Seviyesi
          </span>
          <div className="text-xl font-mono font-bold text-carbon-100">
            {statsSummary?.average_power_level
              ? (statsSummary.average_power_level * 10).toFixed(1)
              : '—'}
          </div>
        </div>
      </div>

      {/* Analytics Distributions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-carbon-400 uppercase tracking-widest">
            Ülke Bazlı Aktör Dağılımı
          </h3>
          <div className="h-60 w-full">
            {statsByCountry && statsByCountry.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statsByCountry}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                  <XAxis dataKey="country_code" stroke="#737373" fontSize={10} />
                  <YAxis stroke="#737373" fontSize={10} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040' }}
                    labelStyle={{ color: '#E5E5E5' }}
                  />
                  <Bar dataKey="count" fill="#a1a1aa" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-carbon-500 italic">
                Veri bulunamadı.
              </div>
            )}
          </div>
        </div>

        <div className="border border-hair border-carbon-550 bg-carbon-900 p-5 space-y-4">
          <h3 className="text-xs font-semibold text-carbon-400 uppercase tracking-widest">
            Diplomatik Blok Dağılımı
          </h3>
          <div className="h-60 w-full flex items-center justify-center">
            {statsByBloc && statsByBloc.length > 0 ? (
              <div className="flex flex-col sm:flex-row items-center w-full justify-around gap-4">
                <div className="h-44 w-44 flex-shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statsByBloc}
                        dataKey="count"
                        nameKey="bloc"
                        innerRadius={50}
                        outerRadius={70}
                        paddingAngle={4}
                      >
                        {statsByBloc.map((_, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={CHART_COLORS[index % CHART_COLORS.length]}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="text-xs font-mono space-y-1.5 w-full max-w-[200px]">
                  {statsByBloc.map((b, idx) => (
                    <div key={b.bloc} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
                        />
                        <span className="text-carbon-350 capitalize">{b.bloc || 'Diğer'}</span>
                      </div>
                      <span className="text-carbon-100 font-bold">{b.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-carbon-500 italic">
                Veri bulunamadı.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Speakers Database Grid */}
      <div className="border border-hair border-carbon-550 bg-carbon-900 p-6 space-y-6">
        {/* Table Filters */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-carbon-450" />
            <input
              type="text"
              placeholder="Konuşmacı adı, unvan veya rumuz ara..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full bg-carbon-950 text-carbon-100 pl-10 pr-4 py-2 text-xs border border-carbon-700 focus:border-carbon-500 focus:outline-none placeholder-carbon-500"
            />
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 text-xs text-carbon-400">
              <Filter className="w-3.5 h-3.5" />
              Filtreler:
            </div>

            <select
              value={countryFilter}
              onChange={(e) => {
                setCountryFilter(e.target.value);
                setPage(1);
              }}
              className="bg-carbon-950 text-xs border border-carbon-700 px-3 py-1.5 rounded text-carbon-200 focus:outline-none"
            >
              <option value="">Tüm Ülkeler</option>
              {statsByCountry?.map((c) => (
                <option key={c.country_code} value={c.country_code || ''}>
                  {c.country_name || c.country_code}
                </option>
              ))}
            </select>

            <select
              value={blocFilter}
              onChange={(e) => {
                setBlocFilter(e.target.value);
                setPage(1);
              }}
              className="bg-carbon-950 text-xs border border-carbon-700 px-3 py-1.5 rounded text-carbon-200 focus:outline-none"
            >
              <option value="">Tüm Bloklar</option>
              {statsByBloc?.map((b) => (
                <option key={b.bloc} value={b.bloc || ''}>
                  {b.bloc ? b.bloc.toUpperCase() : 'Diğer'}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Table View */}
        <div className="border border-carbon-800 overflow-x-auto">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-carbon-500" />
              <span className="text-xs text-carbon-450">Konuşmacı verileri yükleniyor...</span>
            </div>
          ) : !speakersData?.items || speakersData.items.length === 0 ? (
            <div className="py-20 text-center text-xs text-carbon-450 italic">
              Aranan kriterlere uygun konuşmacı bulunamadı.
            </div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr
                    key={headerGroup.id}
                    className="border-b border-carbon-800 bg-carbon-950 text-carbon-400 font-semibold tracking-wider uppercase"
                  >
                    {headerGroup.headers.map((header) => (
                      <th
                        key={header.id}
                        className="p-4 py-3 font-semibold text-3xs tracking-widest"
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-carbon-800 bg-carbon-900/50">
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-carbon-850/40 transition-colors">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="p-4 py-3.5 align-middle">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination controls */}
        {speakersData && speakersData.total > 0 && (
          <div className="flex items-center justify-between text-2xs text-carbon-400 pt-2 border-t border-carbon-800">
            <div className="font-mono">
              Toplam <span className="text-carbon-200 font-bold">{speakersData.total}</span> kayıt
              listeleniyor
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1 border border-carbon-700 hover:bg-carbon-800 transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="font-mono text-carbon-300">
                Sayfa <span className="text-carbon-100 font-bold">{page}</span> /{' '}
                {speakersData.pages}
              </div>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(speakersData.pages, p + 1))}
                disabled={page === speakersData.pages}
                className="p-1 border border-carbon-700 hover:bg-carbon-800 transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ADD SPEAKER MODAL */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-black/75 z-[100] flex items-center justify-center p-4">
          <div className="bg-carbon-900 border border-carbon-550 w-full max-w-lg p-6 space-y-6 animate-[fade-in-up_200ms_ease-out]">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-carbon-100 uppercase">
                Yeni Konuşmacı Kaydı
              </h3>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="text-carbon-450 hover:text-carbon-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">
                    Kanonik İsim (SOYAD, Ad)*
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="LAVROV, Sergei"
                    value={newSpeaker.canonical_name}
                    onChange={(e) =>
                      setNewSpeaker({ ...newSpeaker, canonical_name: e.target.value })
                    }
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">
                    Ekran İsmi (Görünen İsim)
                  </label>
                  <input
                    type="text"
                    placeholder="Sergei Lavrov"
                    value={newSpeaker.display_name}
                    onChange={(e) => setNewSpeaker({ ...newSpeaker, display_name: e.target.value })}
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">
                    Ülke Kodu (ISO 3-Letter)
                  </label>
                  <input
                    type="text"
                    maxLength={3}
                    placeholder="RUS"
                    value={newSpeaker.country_code}
                    onChange={(e) =>
                      setNewSpeaker({ ...newSpeaker, country_code: e.target.value.toUpperCase() })
                    }
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500 font-mono"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">
                    Ülke Adı
                  </label>
                  <input
                    type="text"
                    placeholder="Russia"
                    value={newSpeaker.country_name}
                    onChange={(e) => setNewSpeaker({ ...newSpeaker, country_name: e.target.value })}
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">
                    Diplomatik Blok
                  </label>
                  <input
                    type="text"
                    placeholder="brics"
                    value={newSpeaker.bloc}
                    onChange={(e) => setNewSpeaker({ ...newSpeaker, bloc: e.target.value })}
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-400 font-semibold uppercase text-3xs">Unvan</label>
                  <input
                    type="text"
                    placeholder="Foreign Minister"
                    value={newSpeaker.title}
                    onChange={(e) => setNewSpeaker({ ...newSpeaker, title: e.target.value })}
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-2 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-carbon-400 font-semibold uppercase text-3xs">
                  Güç Seviyesi (Scale 1-10)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={newSpeaker.power_level}
                    onChange={(e) =>
                      setNewSpeaker({ ...newSpeaker, power_level: parseFloat(e.target.value) })
                    }
                    className="flex-1 accent-carbon-100"
                  />
                  <span className="font-mono font-bold text-carbon-100">
                    {(newSpeaker.power_level * 10).toFixed(1)}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-carbon-800 pt-4 mt-6">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="isActive"
                    checked={newSpeaker.is_active}
                    onChange={(e) => setNewSpeaker({ ...newSpeaker, is_active: e.target.checked })}
                    className="h-3.5 w-3.5 accent-carbon-100 cursor-pointer"
                  />
                  <label
                    htmlFor="isActive"
                    className="text-carbon-300 font-semibold select-none cursor-pointer"
                  >
                    Aktif Kayıt Olarak Başlat
                  </label>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsAddModalOpen(false)}
                    className="px-4 py-2 border border-carbon-700 hover:bg-carbon-800 text-carbon-300 font-medium"
                  >
                    Vazgeç
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-carbon-900 bg-carbon-50 hover:bg-carbon-200 transition-colors font-bold"
                  >
                    Oluştur
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DETAIL DRAWER */}
      {isDrawerOpen && speakerDetail && (
        <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-carbon-900 border-l border-carbon-550 z-[90] shadow-2xl flex flex-col justify-between animate-[slide-in-right_300ms_ease-out]">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-carbon-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 bg-carbon-800 border border-carbon-750 flex items-center justify-center font-bold text-carbon-100 text-sm">
                  {speakerDetail.canonical_name.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-sm font-semibold tracking-tight text-carbon-50 leading-tight">
                    {speakerDetail.canonical_name}
                  </h3>
                  <span className="text-3xs text-carbon-450 tracking-wider font-mono">
                    ID: {speakerDetail.speaker_id}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsDrawerOpen(false)}
                className="text-carbon-450 hover:text-carbon-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Profile Stats Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="border border-carbon-800 p-3 bg-carbon-950/40 rounded space-y-1">
                <span className="text-3xs uppercase text-carbon-450 font-semibold flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> Ülke / Blok
                </span>
                <p className="text-2xs text-carbon-200 font-medium">
                  {speakerDetail.country_name || 'Bilinmiyor'} ({speakerDetail.country_code || '—'})
                  / <span className="capitalize">{speakerDetail.bloc || '—'}</span>
                </p>
              </div>

              <div className="border border-carbon-800 p-3 bg-carbon-950/40 rounded space-y-1">
                <span className="text-3xs uppercase text-carbon-450 font-semibold flex items-center gap-1">
                  <Building className="w-3 h-3" /> Organizasyon
                </span>
                <p className="text-2xs text-carbon-200 font-medium truncate">
                  {speakerDetail.organization || 'Bilinmiyor'}
                </p>
              </div>

              <div className="border border-carbon-800 p-3 bg-carbon-950/40 rounded space-y-1">
                <span className="text-3xs uppercase text-carbon-450 font-semibold flex items-center gap-1">
                  <Briefcase className="w-3 h-3" /> Görev & Rol
                </span>
                <p className="text-2xs text-carbon-200 font-medium capitalize">
                  {speakerDetail.title || 'Participant'} ({speakerDetail.role || 'panelist'})
                </p>
              </div>

              <div className="border border-carbon-800 p-3 bg-carbon-950/40 rounded space-y-1">
                <span className="text-3xs uppercase text-carbon-450 font-semibold flex items-center gap-1">
                  <Calendar className="w-3 h-3" /> İlk / Son Görülme
                </span>
                <p className="text-2xs text-carbon-200 font-medium font-mono text-3xs">
                  {speakerDetail.first_seen_at
                    ? new Date(speakerDetail.first_seen_at).toLocaleDateString()
                    : '—'}{' '}
                  /{' '}
                  {speakerDetail.last_seen_at
                    ? new Date(speakerDetail.last_seen_at).toLocaleDateString()
                    : '—'}
                </p>
              </div>
            </div>

            {/* Downstream Analytics Details */}
            <div className="border border-carbon-850 p-4 rounded bg-carbon-950/20 space-y-4">
              <h4 className="text-2xs font-semibold text-carbon-400 uppercase tracking-widest flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" /> Analitik Profil Metrikleri
              </h4>

              <div className="grid grid-cols-3 gap-2 text-center text-2xs">
                <div className="bg-carbon-950 border border-carbon-800 p-2.5 rounded">
                  <span className="block text-3xs text-carbon-500 font-semibold uppercase">
                    Toplam Segments
                  </span>
                  <span className="text-xs font-mono font-bold text-carbon-100">
                    {speakerDetail.n_segments}
                  </span>
                </div>
                <div className="bg-carbon-950 border border-carbon-800 p-2.5 rounded">
                  <span className="block text-3xs text-carbon-500 font-semibold uppercase">
                    Toplam Cümle
                  </span>
                  <span className="text-xs font-mono font-bold text-carbon-100">
                    {speakerDetail.n_sentences}
                  </span>
                </div>
                <div className="bg-carbon-950 border border-carbon-800 p-2.5 rounded">
                  <span className="block text-3xs text-carbon-500 font-semibold uppercase">
                    Ort. Sentiment
                  </span>
                  <span className="text-xs font-mono font-bold text-zinc-300">
                    {speakerDetail.avg_sentiment.toFixed(2)}
                  </span>
                </div>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-carbon-850 py-1.5">
                  <span className="text-carbon-450">Baskın Duygu:</span>
                  <span className="font-bold text-carbon-200 capitalize">
                    {speakerDetail.dominant_emotion || 'Bilinmiyor'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-carbon-850 py-1.5">
                  <span className="text-carbon-450">Baskın Söylem Konusu:</span>
                  <span className="font-bold text-carbon-200">
                    {speakerDetail.dominant_topic || 'Bilinmiyor'}
                  </span>
                </div>
                <div className="flex justify-between border-b border-carbon-850 py-1.5">
                  <span className="text-carbon-450">Baskın Çerçeveleme (Frame):</span>
                  <span className="font-bold text-carbon-200 capitalize">
                    {speakerDetail.dominant_frame?.replace('_', ' ') || 'Bilinmiyor'}
                  </span>
                </div>
                <div className="flex justify-between py-1.5">
                  <span className="text-carbon-450">İşbirlikçi Tutum (Cooperative Pct):</span>
                  <span className="font-mono font-bold text-carbon-100">
                    {Math.round(speakerDetail.cooperative_pct * 100)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Historical Sentiment Chart */}
            <div className="border border-carbon-800 p-4 rounded bg-carbon-950/20 space-y-3">
              <h4 className="text-2xs font-semibold text-carbon-400 uppercase tracking-widest flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5" /> Zamansal Duygu Trendi (Vader Compound)
              </h4>
              <div className="h-44 w-full">
                {sentimentHistory && sentimentHistory.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={sentimentHistory}>
                      <defs>
                        <linearGradient id="colorSentiment" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#a1a1aa" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#a1a1aa" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                      <XAxis dataKey="date_str" stroke="#737373" fontSize={9} />
                      <YAxis stroke="#737373" domain={[-1, 1]} fontSize={9} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#171717', border: '1px solid #404040' }}
                        labelStyle={{ color: '#E5E5E5' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="avg_sentiment"
                        stroke="#a1a1aa"
                        fillOpacity={1}
                        fill="url(#colorSentiment)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-carbon-500 italic">
                    Duygu geçmişi verisi bulunamadı.
                  </div>
                )}
              </div>
            </div>

            {/* Inline Config Adjustments */}
            <div className="border border-carbon-800 p-4 rounded bg-carbon-950/20 space-y-4">
              <h4 className="text-2xs font-semibold text-carbon-400 uppercase tracking-widest flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5" /> Manuel Bilgi & Konfigürasyon Ayarları
              </h4>

              <div className="space-y-3 text-xs">
                <div className="space-y-1">
                  <label className="text-carbon-450 uppercase text-3xs font-semibold">
                    Görünen İsim
                  </label>
                  <input
                    type="text"
                    value={editFields.display_name || ''}
                    onChange={(e) => setEditFields({ ...editFields, display_name: e.target.value })}
                    className="w-full bg-carbon-950 text-carbon-100 px-3 py-1.5 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-carbon-450 uppercase text-3xs font-semibold">
                      Unvan
                    </label>
                    <input
                      type="text"
                      value={editFields.title || ''}
                      onChange={(e) => setEditFields({ ...editFields, title: e.target.value })}
                      className="w-full bg-carbon-950 text-carbon-100 px-3 py-1.5 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-carbon-450 uppercase text-3xs font-semibold">
                      Kurum/Organizasyon
                    </label>
                    <input
                      type="text"
                      value={editFields.organization || ''}
                      onChange={(e) =>
                        setEditFields({ ...editFields, organization: e.target.value })
                      }
                      className="w-full bg-carbon-950 text-carbon-100 px-3 py-1.5 border border-carbon-700 focus:outline-none focus:border-carbon-500"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-carbon-450 uppercase text-3xs font-semibold">
                    Aktör Güç Seviyesi (Scale 1-10)
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={editFields.power_level ?? 0.5}
                      onChange={(e) =>
                        setEditFields({ ...editFields, power_level: parseFloat(e.target.value) })
                      }
                      className="flex-1 accent-carbon-100"
                    />
                    <span className="font-mono font-bold text-carbon-100">
                      {((editFields.power_level ?? 0.5) * 10).toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Aliases Config */}
                <div className="space-y-2">
                  <label className="text-carbon-450 uppercase text-3xs font-semibold block">
                    Rumuzlar & Aliases
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {editFields.aliases?.map((a) => (
                      <span
                        key={a}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-3xs font-mono bg-carbon-800 text-carbon-300 border border-carbon-750"
                      >
                        {a}
                        <button
                          type="button"
                          onClick={() => handleRemoveAlias(a)}
                          className="hover:text-red-400"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Yeni rumuz girin..."
                      value={newAlias}
                      onChange={(e) => setNewAlias(e.target.value)}
                      className="flex-1 bg-carbon-950 text-carbon-100 px-3 py-1 text-xs border border-carbon-750 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleAddAlias}
                      className="px-3 py-1 bg-carbon-800 hover:bg-carbon-700 border border-carbon-700 text-xs text-carbon-100"
                    >
                      Ekle
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="checkbox"
                    id="editIsActive"
                    checked={editFields.is_active ?? true}
                    onChange={(e) => setEditFields({ ...editFields, is_active: e.target.checked })}
                    className="h-3.5 w-3.5 accent-carbon-100 cursor-pointer"
                  />
                  <label
                    htmlFor="editIsActive"
                    className="text-carbon-300 font-semibold select-none cursor-pointer"
                  >
                    Aktör Aktif/İşlemde
                  </label>
                </div>
              </div>
            </div>

            {/* Panel Appearances List */}
            <div className="border border-carbon-800 p-4 rounded bg-carbon-950/20 space-y-3">
              <h4 className="text-2xs font-semibold text-carbon-400 uppercase tracking-widest flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" /> Katıldığı Paneller
              </h4>
              <div className="overflow-x-auto max-h-48">
                {appearances && appearances.length > 0 ? (
                  <table className="w-full text-left border-collapse text-3xs font-mono">
                    <thead>
                      <tr className="border-b border-carbon-800 text-carbon-500 uppercase tracking-wider">
                        <th className="py-1.5">Panel Başlığı</th>
                        <th className="py-1.5 text-right">Cümle Sayısı</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-carbon-850 text-carbon-300">
                      {appearances.map((app) => (
                        <tr key={app.file_id}>
                          <td className="py-2 pr-2 font-sans text-carbon-200">
                            {app.title} ({app.date_str || 'Bilinmiyor'})
                          </td>
                          <td className="py-2 text-right text-carbon-100 font-bold">
                            {app.sentence_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-center text-xs text-carbon-500 italic py-4">
                    Katılım verisi bulunamadı.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Drawer Footer Actions */}
          <div className="border-t border-carbon-800 p-4 bg-carbon-950 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsDrawerOpen(false)}
              className="px-4 py-2 border border-carbon-700 hover:bg-carbon-800 text-xs text-carbon-350"
            >
              Kapat
            </button>
            <button
              type="button"
              onClick={handleSaveDrawer}
              className="px-4 py-2 text-carbon-900 bg-carbon-50 hover:bg-carbon-200 font-bold text-xs"
            >
              Değişiklikleri Kaydet
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
