// src/bb_paxdata/interfaces/web/src/utils/visualizationHelpers.ts

import { isoNumericToAlpha3 } from '../data/isoNumericToAlpha3';
import type { RelationshipType } from '../types/visualization';

/**
 * Maps a country ID (numeric string/number, or alpha3 code) to its ISO Alpha-3 code.
 * If numeric, pads with leading zeros (e.g., 32 -> '032' -> 'ARG').
 */
export function getAlpha3FromNumeric(id: string | number | undefined): string | undefined {
  if (id === undefined || id === null) return undefined;
  const idStr = String(id).trim();
  if (/^\d+$/.test(idStr)) {
    return isoNumericToAlpha3[idStr.padStart(3, '0')];
  }
  return idStr;
}

export const RELATIONSHIP_COLORS: Record<RelationshipType, string> = {
  ALLY: '#10b981', // emerald
  PARTNER: '#3b82f6', // blue
  NEUTRAL: '#6b7280', // gray
  CAUTIOUS: '#f59e0b', // amber
  ADVERSARY: '#ef4444', // red
};

/**
 * Converts a sentiment score in [-1.0, 1.0] to a hex color code.
 * Smoothly interpolates from red (#ef4444) at -1.0 to gray (#6b7280) at 0.0,
 * and from gray (#6b7280) to emerald (#10b981) at +1.0.
 */
export function sentimentToColor(score: number): string {
  const clamped = Math.max(-1.0, Math.min(1.0, score));

  if (clamped < 0) {
    // Interpolate between red (#ef4444) and gray (#6b7280)
    // Red:   R = 239, G = 68,  B = 68
    // Gray:  R = 107, G = 114, B = 128
    const ratio = clamped + 1; // 0 (at -1) to 1 (at 0)
    const r = Math.round(239 + (107 - 239) * ratio);
    const g = Math.round(68 + (114 - 68) * ratio);
    const b = Math.round(68 + (128 - 68) * ratio);

    const rs = r.toString(16).padStart(2, '0');
    const gs = g.toString(16).padStart(2, '0');
    const bs = b.toString(16).padStart(2, '0');
    return `#${rs}${gs}${bs}`;
  } else {
    // Interpolate between gray (#6b7280) and emerald (#10b981)
    // Gray:    R = 107, G = 114, B = 128
    // Emerald: R = 16,  G = 185, B = 129
    const ratio = clamped; // 0 (at 0) to 1 (at 1)
    const r = Math.round(107 + (16 - 107) * ratio);
    const g = Math.round(114 + (185 - 114) * ratio);
    const b = Math.round(128 + (129 - 128) * ratio);

    const rs = r.toString(16).padStart(2, '0');
    const gs = g.toString(16).padStart(2, '0');
    const bs = b.toString(16).padStart(2, '0');
    return `#${rs}${gs}${bs}`;
  }
}

/**
 * Normalizes any country name string to its canonical form
 */
export function normalizeCountryName(name: string): string {
  if (!name) return '';
  const n = name.trim().toLowerCase();
  if (n === 'turkey' || n === 'türkiye' || n === 'turkiye') {
    return 'Türkiye';
  }
  if (n === 'usa' || n === 'united states' || n === 'united states of america') {
    return 'USA';
  }
  if (n === 'united kingdom' || n === 'uk' || n === 'gbr' || n === 'great britain') {
    return 'United Kingdom';
  }
  if (n === 'russian federation' || n === 'russia' || n === 'rus') {
    return 'Russia';
  }
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/**
 * Maps interaction counts to visual bubble radius sizes in px
 */
export function interactionToRadius(count: number, max: number): number {
  const minRadius = 5;
  const maxRadius = 30;
  if (max <= 0) return minRadius;
  const ratio = Math.sqrt(count / max); // Square root area scaling
  return minRadius + (maxRadius - minRadius) * ratio;
}

export const SESSION_LABELS: Record<string, string> = {
  'session-1': 'Session 1 (Inaugural)',
  'session-2': 'Session 2 (Bilateral Discussion)',
};
