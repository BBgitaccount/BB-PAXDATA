# BB-PAXDATA HITL Command Interface v2.0

## Akromatik Lüks Tasarım Felsefesi

Bu arayüz, diplomatik analiz uzmanının saatlerce süren inceleme süreçlerinde göz yorgunluğunu önlemek, renk önyargısını kaldırmak ve verinin kendisini öne çıkarmak üzere tasarlanmıştır.

- **Monolitik Minimalizm**: Hiyerarşi yalnızca tipografi, boşluk ve ışık-gölge farklarıyla sağlanır
- **Akromatik Lüks**: Saf siyah (#0A0A0A), beyaz ve gri tonları
- **İsviçre Tipografi Ekolü**: Grid'e sıkı bağlı, matematiksel hizalama
- **Stealth Interface**: UI'nin egosu yok, yalnızca veriye hizmet eder

## Teknoloji Yığını

- React 18 + Vite + TypeScript
- TailwindCSS (custom carbon palette)
- Zustand (state management)
- Recharts (grafikler)
- TanStack Table (tablolar)
- Lucide React (ikonlar)

## Kurulum

```bash
cd bb-paxdata-hitl-ui
npm install
npm run dev
```

## Özellikler

1. **Dashboard**: KPI kartları, formül sağlığı, trend grafikleri, consensus dağılımı
2. **İnceleme Kuyruğu**: Filtreleme, öncelik badgeleri, triplet görünümü
3. **Cümle Detay**: AI vs Formül karşılaştırma, karar formu, benzer vakalar
4. **Denetim İzi**: WORM kayıtları, ikinci göz onay paneli
5. **Kalibrasyon**: Cohen's Kappa, F1, reviewer performans
6. **AI Karşılaştırma**: Human review formu, gold standard örnekler
7. **Ayarlar**: RBAC yönetimi, sistem parametreleri, JWT token

## Mock API

Tüm API çağrıları `src/services/mockApi.ts` üzerinden simüle edilir. Gerçek backend entegrasyonu için service layer'daki mockApi çağrıları gerçek fetch/axios çağrıları ile değiştirilebilir.

## Renk Paleti

| Rol | Kod |
|-----|-----|
| Arka Plan | #0A0A0A |
| Kart | #161616 |
| Kenarlık | #2A2A2A |
| Birincil Metin | #F5F5F5 |
| İkincil Metin | #8A8A8A |
| Pasif | #505050 |
| Fail Signal | #5C2626 |
| Pass Signal | #264D26 |

## Tipografi

- Arayüz: Inter, SF Pro, Helvetica Neue
- Veri: JetBrains Mono, IBM Plex Mono, SF Mono
