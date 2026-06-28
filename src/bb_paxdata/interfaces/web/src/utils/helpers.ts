import type {
  ConfidenceLevel,
  HumanVerdict,
  QueueStatus,
  RiskLevel,
  TriagePriority,
} from '@/types';

export const formatDate = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatNumber = (n: number, digits = 2): string => n.toFixed(digits);

export const priorityWeight = (p: TriagePriority): number => {
  const map: Record<TriagePriority, number> = {
    NORMAL: 1,
    HIGH_PRIORITY: 2,
    SOVEREIGN_PRIORITY: 3,
    CRITICAL: 4,
  };
  return map[p];
};

export const priorityLabel = (p: TriagePriority): string => {
  const map: Record<TriagePriority, string> = {
    NORMAL: 'NORMAL',
    HIGH_PRIORITY: 'HIGH',
    SOVEREIGN_PRIORITY: 'SOVEREIGN',
    CRITICAL: 'CRITICAL',
  };
  return map[p];
};

export const riskWeight = (r: RiskLevel): number => {
  const map: Record<RiskLevel, number> = {
    LOW: 1,
    MED: 2,
    HIGH: 3,
    CRITICAL: 4,
  };
  return map[r];
};

export const statusLabel = (s: QueueStatus): string => {
  const map: Record<QueueStatus, string> = {
    PENDING: 'BEKLEMEDE',
    ASSIGNED: 'ATANDI',
    IN_REVIEW: 'İNCELENİYOR',
    APPROVED: 'ONAYLANDI',
    REJECTED: 'REDDEDİLDİ',
    MODIFIED: 'DEĞİŞTİRİLDİ',
    ESCALATED: 'ESKALE',
  };
  return map[s];
};

export const verdictLabel = (v: HumanVerdict): string => {
  const map: Record<HumanVerdict, string> = {
    CONFIRMED_FAIL: 'HATA ONAYLANDI',
    CONFIRMED_PASS: 'YANLIŞ ALARM',
    CORRECTED: 'DÜZELTİLDİ',
  };
  return map[v];
};

export const confidenceLabel = (c: ConfidenceLevel): string => {
  const map: Record<ConfidenceLevel, string> = {
    LOW: 'DÜŞÜK',
    MEDIUM: 'ORTA',
    HIGH: 'YÜKSEK',
  };
  return map[c];
};

export const truncate = (s: string, len = 80): string =>
  s.length > len ? s.slice(0, len) + '…' : s;

export const cn = (...classes: (string | false | null | undefined)[]): string =>
  classes.filter(Boolean).join(' ');

/**
 * Data sampling utility for performance optimization.
 * Reduces large datasets to a manageable size for charts.
 * @param data - Array of data points to sample
 * @param maxPoints - Maximum number of points to return (default: 100)
 * @returns Sampled data array
 */
export const sampleData = <T>(data: T[], maxPoints = 100): T[] => {
  if (data.length <= maxPoints) return data;

  const step = Math.ceil(data.length / maxPoints);
  return data.filter((_, index) => index % step === 0);
};
