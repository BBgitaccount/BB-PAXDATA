# BB-PAXDATA Quality Assurance Layer

## Metodolojik Temel
Bu katman, Grimmer & Stewart (2013)'ın "Text as Data" çerçevesine dayanmaktadır.

### İlkeler

#### 1. Yaklaşıksallık (Approximation)
Tüm nicelleştirme yaklaşıktır (All quantification is approximate). BB-PAXDATA'daki skorlar (SBI, DKI, risk_score) "kesin" değil, "gösterge"dir.

#### 2. İnsan Doğrulaması Zorunludur (Validation)
İnsan doğrulaması zorunludur (Human validation is mandatory). `quality/` katmanı, AI çıktılarının otomatik denetimini yapar; ancak nihai karar için `human_review.py` arayüzü sunar.

#### 3. Yöntemler Amaç İçin Seçilmelidir (Purpose)
Yöntemler amaç için seçilmelidir (Method selection must match purpose). VADER kısa metinlerde hızlıdır; BERT diplomatik bağlamda derindir. Pipeline'ta her aşama için doğru araç seçilmelidir.

#### 4. Keşfedici ve Doğrulayıcı Yöntemler Dengelenmelidir (Exploration)
Keşfedici ve doğrulayıcı yöntemler dengelenmelidir (Exploratory vs. confirmatory balance). `quality/evaluator.py` (doğrulayıcı) + `human_review.py` (keşfedici/insan onayı) birlikte çalışır.

### Katmanlar
- `evaluator.py`: Otomatik LLM-as-a-Judge (DeepEval)
- `consistency.py`: Duygu-Risk tutarlılık kontrolü
- `human_review.py`: İnsan doğrulama arayüzü (HITL)
