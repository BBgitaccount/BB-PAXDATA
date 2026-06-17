import type { GoldStandardExample } from '@/types';

export const GOLD_STANDARDS: GoldStandardExample[] = [
  {
    frame_type: 'conflict_frame',
    sentence_text:
      'Taraflar arasindaki catisma derinlesmekte ve askeri cozum olasiligi artmaktadir.',
    explanation: 'Dogrudan catisma vurgusu, taraflarin karsitligi.',
  },
  {
    frame_type: 'security_frame',
    sentence_text:
      'Bolgesel guvenlik tehditleri, uluslararasi toplumun acil mudahalesini gerektirmektedir.',
    explanation: 'Guvenlik odakli terminoloji, tehdit algisi.',
  },
  {
    frame_type: 'peace_frame',
    sentence_text: 'Bariscil cozum yollari arastirilmali ve diyalog kanallari canlandirilmalidir.',
    explanation: 'Baris vurgusu, yapici cozum cagrisi.',
  },
  {
    frame_type: 'legal_frame',
    sentence_text:
      'Uluslararasi hukuk cercevesindeki yukumluluklerin ihlali ciddi sonuclar doguracaktir.',
    explanation: 'Hukuki cerceve, yukumluluk vurgusu.',
  },
  {
    frame_type: 'sovereignty_frame',
    sentence_text: 'Devletin toprak butunlugu ve egemenlik haklari tartismasiz korunmalidir.',
    explanation: 'Egemenlik vurgusu, toprak butunlugu.',
  },
  {
    frame_type: 'neutral',
    sentence_text:
      'Toplanti saat 14:00de baslayacak ve gundem maddeleri sirasiyla ele alinacaktir.',
    explanation: 'Notr bilgi aktarimi, degerlendirme icermez.',
  },
];
