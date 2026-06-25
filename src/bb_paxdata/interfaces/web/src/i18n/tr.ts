export const tr = {
  // Navigation & TopBar
  'nav.group.general': 'GENEL',
  'nav.group.logic': 'HITL LOGIC',
  'nav.group.ai': 'HITL AI',
  'nav.dashboard': 'Özet',
  'nav.speakers': 'Konuşmacı Veri Tabanı',
  'nav.bilateral': 'İkili İlişkiler',
  'nav.worldmap': 'Dünya Haritası',
  'nav.discourse': 'Söylem Ağı',
  'nav.anomalies': 'Anomali Zaman Çizelgesi',
  'nav.drift': 'Zamansal Kayma',
  'nav.health': 'Sistem Sağlığı',
  'nav.monitor': 'Pipeline Monitör',
  'nav.provenance': 'Provenance Grafiği',
  'nav.logic_queue': 'Formula Kuyruğu',
  'nav.logic_audit': 'Denetim İzi',
  'nav.logic_calib': 'Kalibrasyon',
  'nav.logic_prompts': 'Prompt Registry',
  'nav.ai_queue': 'AI Kuyruğu',
  'nav.comparison': 'AI Karşılaştırma',
  'nav.settings': 'Ayarlar',
  'topbar.logout': 'Oturum Kapat',
  'topbar.logout_toast': 'Oturum sonlandırıldı.',
  'topbar.light_mode': 'Açık Mod',
  'topbar.dark_mode': 'Karanlık Mod',

  // Common UI Elements
  'common.refresh': 'Tazele',
  'common.retry': 'Yeniden Dene',
  'common.save': 'KAYDET',
  'common.approve': 'ONAYLA',
  'common.reject': 'REDDET',
  'common.review': 'İNCELE',
  'common.status': 'Durum',
  'common.actions': 'Aksiyonlar',
  'common.loading': 'Yükleniyor...',
  'common.error': 'Hata',

  // Dashboard
  'dashboard.title': 'Özet',
  'dashboard.desc': "Diplomatik analiz pipeline'ının HITL operasyonel görünümü",
  'dashboard.kpi.total_logs': 'Toplam Log',
  'dashboard.kpi.total_pass': 'Toplam PASS',
  'dashboard.kpi.total_fail': 'Toplam FAIL',
  'dashboard.kpi.pending_review': 'Bekleyen İnceleme',
  'dashboard.kpi.confirmed_fail': 'Onaylanan FAIL',
  'dashboard.kpi.false_positive': 'False Positive',
  'dashboard.kpi.corrected': 'Düzeltilen',
  'dashboard.kpi.accuracy': 'Doğruluk',
  'dashboard.kpi.error_rate': 'Formül Hata Oranı',
  'dashboard.kpi.latency': 'Ortalama Gecikme',
  'dashboard.kpi.participation': 'Reviewer Katılımı',
  'dashboard.chart.consensus': 'İkili Söylem Mutabakatı',
  'dashboard.chart.trends': 'Günlük Anomali ve Formül Hata Trendleri',
  'dashboard.chart.priorities': 'Öncelik Dağılımı (Fischer DNA)',
  'dashboard.chart.triggers': 'Tetikleyici Dağılımı',
  'dashboard.chart.consensus_dist': 'Konsensüs Seviyesi Dağılımı',
  'dashboard.timeline': 'İnceleme Çizelgesi',
  'dashboard.chart.daily_trend': 'Günlük PASS/FAIL Trendi',
  'dashboard.chart.last_30_days': 'Son 30 gün',
  'dashboard.chart.triage_dist': 'Triage Dağılımı',
  'dashboard.chart.priority_levels': 'Öncelik seviyeleri',
  'dashboard.chart.formula_health': 'Formül Sağlığı',
  'dashboard.chart.fp_correction_rates': 'False positive ve düzeltme oranları',
  'dashboard.chart.trigger_dist': 'Trigger Dağılımı',
  'dashboard.chart.triage_reasons': 'Kuyruğa düşme nedenleri',
  'dashboard.chart.consensus_level_dist': 'Consensus Level Dağılımı',
  'dashboard.chart.dualgate_outputs': 'DualGate çıktıları',
  'dashboard.chart.bilateral_heatmap': 'İkili İlişkiler Heatmap',
  'dashboard.chart.bilateral_heatmap_desc':
    'Aktörler arası diplomatik tutum (Affinity) — zaman kaydırıcısı ile panel bazında görüntüle',

  // Settings
  'settings.title': 'Sistem Ayarları',
  'settings.desc': 'Reviewer yönetimi, sistem parametreleri ve token yönetimi',
  'settings.reviewers': 'Reviewer Yönetimi',
  'settings.params': 'Sistem Parametreleri',
  'settings.token': 'Token Yönetimi',
  'settings.save_toast': 'Ayarlar başarıyla kaydedildi.',
  'settings.token_toast': 'Yeni token başarıyla oluşturuldu.',
  'settings.no_permission': 'Bu sayfaya erişim yetkiniz bulunmamaktadır.',

  // Discourse Network
  'discourse.title': 'Söylem Ağı Gezgini',
  'discourse.desc': 'Fischer DNA Bipartite (İki Parçalı) Aktör-Kavram Söylem Ağ Analizi',
  'discourse.actors': 'Aktörler',
  'discourse.concepts': 'Söylem Kavramları',
  'discourse.select_session':
    'Lütfen söylem ağını yüklemek için bir Analiz Oturumu (Session ID) seçin.',

  // Anomaly Timeline
  'anomalies.title': 'Anomali Zaman Çizelgesi',
  'anomalies.desc':
    'Fischer DNA ve CrossAnomalyService tarafından tespit edilen çelişki ve sapmaların kronolojik akışı',

  // Audit Trail
  'audit.title': 'Denetim İzi',
  'audit.desc': 'WORM denetim kayıtları ve değişiklik geçmişi',

  // System Health
  'health.title': 'Sistem Sağlığı',
  'health.desc': 'Veri tabanı durum tespiti, tablo doluluk oranları ve canlı sistem metrikleri',

  // Temporal Drift
  'drift.title': 'Zamansal Kayma Analizi',
  'drift.desc': 'GARCH Volatilite, Entity Konuşma Yarı-Ömrü ve longitudinal DKI trend takipleri',

  // Review Queue
  'queue.logic_title': 'HITL Logic — Formül Doğrulama Kuyruğu',
  'queue.ai_title': 'HITL AI — İnceleme Kuyruğu',
  'queue.logic_desc': 'FAIL durumundaki formül logları ve insan inceleme bekleyen kayıtlar',
  'queue.ai_desc': 'Yapay zeka analiz çıktıları ve insan inceleme bekleyen kayıtlar',
  'queue.records_count': '{count} kayıt',

  // Calibration
  'calibration.title': 'Kalibrasyon & Performans',
  'calibration.desc': 'AI-İnsan uyum metrikleri ve reviewer performans analizi',

  // Pipeline Monitor
  'monitor.title': 'Pipeline Monitör',
  'monitor.desc': 'Asenkron diplomatik transkript ingestion akışı ve işlem yükü izleme paneli',

  // Prompt Registry
  'prompts.title': 'Prompt Registry',
  'prompts.desc': 'Akademik referans zinciri ve prompt versiyonları',

  // AI Comparison
  'comparison.title': 'AI Karşılaştırma İncelemesi',
  'comparison.desc': 'AI çıktıları ile insan değerlendirmelerinin karşılaştırılması',
};
