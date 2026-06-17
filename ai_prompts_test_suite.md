# AI Prompts Test Suite - Real System Requests
# Cümle: "Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."

**NOT:** Bu dosya BB-PAXDATA sisteminde gerçekten kullanılan promptları içerir. Sistem dil bazlı prompt seçimi yapar:
- diplomatic_analysis: Türkçe sistem promptu (language="any")
- Diğer tüm promptlar: İngilizce

---

## 1. Ana AI Analizi (diplomatic_analysis) - TÜRKÇE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:223-246`
**Prompt ID:** `diplomatic_analysis@v2.1`
**Dil:** Türkçe sistem promptu + İngilizce metin

### Full Prompt (Sistemden Giden Gerçek İstek)
```
Sen, uluslararası diplomasi ve jeopolitik analizde uzman bir yapay zeka asistanısın.
Aşağıdaki metni çok katmanlı olarak analiz et.

İnceleme kriterleri:
- Siyasi risk düzeyi (gerginlik esnekliği, retorik şiddeti, sözde diplomasi tespiti)
- Duygusal ton (matematiksel olarak: -1.0 = aşırı negatif, +1.0 = aşırı pozitif)
- Ana iddialar ve bunların diplomatik doğruluk riski

YANIT FORMATI (sadece geçerli JSON, markdown veya açıklama olmadan):
{"sentiment_score": <float>, "risk_score": <float>, "sentiment_label": "<positive|negative|neutral|mixed>", "risk_factors": [<string>], "summary": "<string>", "key_claims": [<string>]}

Metin: Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like.
```

### API Request Parameters
```python
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=True
)
```

### Expected Response Schema
```json
{
  "sentiment_score": "float between -1.0 and 1.0",
  "risk_score": "float between 0.0 and 1.0",
  "sentiment_label": "one of: positive, negative, neutral, mixed",
  "risk_factors": ["array of strings describing risk factors"],
  "summary": "string - brief summary of analysis",
  "key_claims": ["array of strings - main claims extracted"]
}
```

### Example Expected Response
```json
{
  "sentiment_score": 0.15,
  "risk_score": 0.35,
  "sentiment_label": "neutral",
  "risk_factors": ["constitutional uncertainty", "transitional period ambiguity"],
  "summary": "The statement discusses legislative processes within a constitutional framework focusing on post-transition period details.",
  "key_claims": ["Legislations will be enacted", "Voting will occur", "Focus on post-five-year transitional period"]
}
```

---

## 2. Frame Detection - Concept Extraction - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/infrastructure/ai/frame_detection/concept_extractor.py:80-95`
**Prompt ID:** `concept_extraction@6.1.0`
**Dil:** İngilizce

### Full Prompt (Sistemden Giden Gerçek İstek)
```
Extract the key target concepts from the following diplomatic text segment.
These are the main subjects of dispute, negotiation, or discussion.

Text:
Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like.

Return a JSON object with a "concepts" array containing strings.
Each concept should be a noun phrase representing a key issue.
Example: {"concepts": ["border security", "bilateral trade", "human rights"]}
```

### API Request Parameters
```python
await self._llm.generate(
    prompt=prompt,
    temperature=0.0  # Deterministik
)
```

### Expected Response Schema
```json
{
  "concepts": ["array of strings - key concepts extracted"]
}
```

### Example Expected Response
```json
{
  "concepts": ["constitution", "legislations", "transitional period", "constitutional framework"]
}
```

---

## 3. Frame Detection - 5W1H Extraction - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/infrastructure/ai/frame_detection/five_w_one_h_extractor.py:124-148`
**Prompt ID:** `5w1h_extraction@6.1.0`
**Dil:** İngilizce

### Full Prompt (Sistemden Giden Gerçek İstek)
```
Extract the 5W1H information and classify the speech acts from the following diplomatic text segment.
Answer the questions: Who, What, When, Where, Why, and How based on the text.
Also classify the speech act of the main action. Choose primary and secondary speech acts from: ASSERTIVE, DIRECTIVE, COMMISSIVE, EXPRESSIVE, DECLARATIVE, INTERROGATIVE.
Identify any force modifier (e.g., "strongly", "categorically", "respectfully", "saygıyla", "şiddetle", "kesinlikle") used in the main action.

Text:
Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like.

Return a JSON object with the following structure:
{
  "who": ["list of actors/entities involved"],
  "what": ["the main event or action described"],
  "when": ["temporal information or timestamps"],
  "where": ["geographical or contextual locations"],
  "why": ["reasons or motivations cited"],
  "how": ["mechanisms, methods, or conditions described"],
  "primary_speech_act": "ASSERTIVE|DIRECTIVE|COMMISSIVE|EXPRESSIVE|DECLARATIVE|INTERROGATIVE",
  "secondary_speech_act": "ASSERTIVE|DIRECTIVE|COMMISSIVE|EXPRESSIVE|DECLARATIVE|INTERROGATIVE or null",
  "speech_act_confidence": 0.95,
  "force_modifier": "strongly|categorically|respectfully|null"
}
If a 5W1H field is not found in the text, return an empty array for that field.
```

### API Request Parameters
```python
await self._llm.generate(
    prompt=prompt,
    temperature=0.0
)
```

### Expected Response Schema
```json
{
  "who": ["array of strings - actors/entities"],
  "what": ["array of strings - main events/actions"],
  "when": ["array of strings - temporal information"],
  "where": ["array of strings - locations"],
  "why": ["array of strings - reasons/motivations"],
  "how": ["array of strings - mechanisms/methods"],
  "primary_speech_act": "one of: ASSERTIVE, DIRECTIVE, COMMISSIVE, EXPRESSIVE, DECLARATIVE, INTERROGATIVE",
  "secondary_speech_act": "one of: ASSERTIVE, DIRECTIVE, COMMISSIVE, EXPRESSIVE, DECLARATIVE, INTERROGATIVE or null",
  "speech_act_confidence": "float between 0.0 and 1.0",
  "force_modifier": "string or null"
}
```

### Example Expected Response
```json
{
  "who": ["legislative body", "constitutional authorities"],
  "what": ["enactment of legislations", "voting on legislations", "defining post-five-year transitional period"],
  "when": ["post-five-year transitional period"],
  "where": ["constitutional framework"],
  "why": ["to establish legislative details for transitional period"],
  "how": ["through enactment and voting"],
  "primary_speech_act": "ASSERTIVE",
  "secondary_speech_act": null,
  "speech_act_confidence": 0.85,
  "force_modifier": null
}
```

---

## 4. LLM Position Estimator - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/infrastructure/ai/llm_position_estimator.py:197-217`
**Prompt ID:** `llm_position@1.0`
**Dil:** İngilizce

### Full Prompt (Sistemden Giden Gerçek İstek) - general_policy dimension
```
You are an expert political text analyst performing policy position estimation.

TASK: Rate the following diplomatic statement on a continuous scale of 0 to 100.

SCALE DEFINITION:
- 0 = Maximally opposed, dovish, conciliatory, status-quo challenging
- 50 = Neutral, balanced, purely descriptive
- 100 = Maximally supportive, hawkish, confrontational, status-quo defending

POLICY DIMENSION: general_policy

STATEMENT: "Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."

INSTRUCTIONS:
1. Consider only the explicit policy position conveyed in this sentence.
2. Ignore diplomatic politeness formulas unless they encode substantive position.
3. Respond ONLY in valid JSON matching the schema: {"position": int, "confidence": float, "rationale": str}
4. Do not include markdown code blocks or explanatory text outside JSON.

OUTPUT:
```

### API Request Parameters
```python
await self._client.generate(prompt, temperature=0.0)
```

### Expected Response Schema
```json
{
  "position": "integer between 0 and 100",
  "confidence": "float between 0.0 and 1.0",
  "rationale": "string - explanation of the position rating"
}
```

### Example Expected Response
```json
{
  "position": 50,
  "confidence": 0.75,
  "rationale": "The statement is descriptive and procedural, focusing on legislative processes without taking a clear ideological stance."
}
```

---

## 5. Anomaly Validation (Koşullu - Sadece Anomali Tespit Edilirse) - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/infrastructure/ai/anomaly_controller.py:96-145`
**Prompt ID:** `anomaly_validation@v1.0`
**Dil:** İngilizce
**Not:** Bu prompt sadece deterministik anomali tespit edildiğinde çağrılır

### Full Prompt (Sistemden Giden Gerçek İstek) - Örnek Context ile
```
You are an expert in diplomatic discourse analysis acting as an anomaly validation judge.

## CONTEXT (last 5 sentences):
[1] The constitutional framework provides the foundation for all legislative processes.
[2] We must ensure transparency in all governmental proceedings.
[3] The transitional period requires careful planning and execution.
[4] All stakeholders should be consulted during this process.
[5] The constitution mandates democratic participation in decision-making.

## SENTENCE UNDER ANALYSIS:
"Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."

## DETERMINISTIC ANOMALY ENGINE RESULT:
Triggered Rules: []
Anomaly Score: 0.000
Confidence: 0.000

## YOUR TASK:
Analyze the sentence in its diplomatic context and validate or challenge the deterministic result.
Consider:
- Is this genuine contradiction or strategic irony/rhetoric?
- Does the speaker use diplomatic subtext that rules cannot capture?
- Are there hidden coercive signals or tone shifts the rules missed?

Respond ONLY with a valid JSON object:
{
  "decision": "<CONFIRMED|DISMISSED|ESCALATED|AI_ONLY|INCONCLUSIVE>",
  "coherence_score": <0.0-1.0, where 1.0=fully coherent/no anomaly>,
  "reasoning": "<concise explanation in the same language as the sentence>",
  "detected_subtype": "<irony|rhetorical_strategy|coercive_signal|tone_drift|null>",
  "confidence": <0.0-1.0>
}
```

### API Request Parameters
```python
CompletionOptions(temperature=0.1, max_tokens=512)
```

### Expected Response Schema
```json
{
  "decision": "one of: CONFIRMED, DISMISSED, ESCALATED, AI_ONLY, INCONCLUSIVE",
  "coherence_score": "float between 0.0 and 1.0",
  "reasoning": "string - explanation",
  "detected_subtype": "one of: irony, rhetorical_strategy, coercive_signal, tone_drift, null",
  "confidence": "float between 0.0 and 1.0"
}
```

### Example Expected Response
```json
{
  "decision": "DISMISSED",
  "coherence_score": 0.90,
  "reasoning": "The sentence is procedurally coherent and consistent with the constitutional framework context. No anomalies detected.",
  "detected_subtype": null,
  "confidence": 0.85
}
```

---

## 6. Frame Analysis - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:318-332`
**Prompt ID:** `frame_analysis@v2.1`
**Dil:** İngilizce

### Full Prompt (Sistemden Giden Gerçek İstek)
```
Analyze the following sentence in the context of international relations and determine its primary discourse frame (e.g. conflict, cooperation, trade, security).
Sentence: "Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."
Response format: JSON with "frame" and "explanation".
```

### API Request Parameters
```python
# Frame analysis uses the standard completion options
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=True
)
```

### Expected Response Schema
```json
{
  "frame": "string - primary discourse frame",
  "explanation": "string - explanation of frame classification"
}
```

### Example Expected Response
```json
{
  "frame": "cooperation",
  "explanation": "The sentence describes legislative cooperation and constitutional processes, indicating a cooperative frame focused on governance and procedural development."
}
```

---

## 7. RAG Synthesis - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:299-316`
**Prompt ID:** `rag_synthesis@v2.0`
**Dil:** İngilizce
**Not:** Bu prompt RAG (Retrieval-Augmented Generation) için kullanılır, kullanıcı sorgusu ile çağrılır

### Full Prompt (Sistemden Giden Gerçek İstek) - Örnek Kullanım
```
You are an expert AI Diplomatic Analyst. Use the following retrieved context sentences (total: 3) to answer the user query.
If the retrieved context does not contain enough information to answer the query, prioritize the retrieved context but you may use general diplomatic knowledge to bridge the gaps, clearly indicating what is sourced from the context and what is inferred.

Retrieved Context:
[1] The constitutional framework establishes the basis for legislative authority.
[2] Transitional periods require specific legal frameworks to ensure stability.
[3] Democratic processes mandate public participation in legislative decisions.

User Query: What is the purpose of the post-five-year transitional period legislation?

Synthesized Diplomatic Analysis:
```

### API Request Parameters
```python
# RAG synthesis uses standard completion options
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=False  # Free-form text response
)
```

### Expected Response
Free-form text response synthesizing the retrieved context to answer the query.

---

## 8. DKI Judge - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:334-370`
**Prompt ID:** `dki_judge@v2.1`
**Dil:** İngilizce
**Not:** Bu prompt DKI (Dynamic Knowledge Integration) kalite kontrolü için kullanılır

### Full Prompt (Sistemden Giden Gerçek İstek) - Örnek Değerler
```
## ROLE & MISSION:
You are an expert AI Diplomatic Analyst acting as a quality judge for the BB-PAXDATA pipeline.
Evaluate the current statement analysis against the historical baseline metrics for the actor.

## TARGET TRANSCRIPT CONTENT:
Actor: Constitutional Authority (CountryX)
Target Sentence: "Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."

## PIPELINE ANALYSIS OUTPUT:
Assigned Sentiment: 0.15
Assigned Risk Score: 3.5 (0-10)
Assigned Discourse Frame: cooperation

## HISTORICAL BASELINE METRICS:
Baseline Sentiment Average: 0.10
Baseline Risk Average: 3.2
Primary Historical Frame: cooperation

## EVALUATION CRITERIA:
1. Semantic Shift Check: Does the target statement represent an uncalibrated jump in stance?
2. Frame Consistency: Is the shift in frame logically supported by the sentence semantics?

## JSON OUTPUT FORMAT:
Provide the evaluation strictly in JSON format:
{
  "semantic_shift_score": float (0.0 to 1.0),
  "is_consistent": boolean,
  "calibration_drift": float (-1.0 to 1.0),
  "reasoning": "Detailed textual explanation"
}
```

### API Request Parameters
```python
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=True
)
```

### Expected Response Schema
```json
{
  "semantic_shift_score": "float between 0.0 and 1.0",
  "is_consistent": "boolean",
  "calibration_drift": "float between -1.0 and 1.0",
  "reasoning": "string - detailed explanation"
}
```

### Example Expected Response
```json
{
  "semantic_shift_score": 0.05,
  "is_consistent": true,
  "calibration_drift": 0.03,
  "reasoning": "The target statement shows minimal semantic shift from historical baseline. The sentiment and frame remain consistent with the actor's typical constitutional discourse patterns."
}
```

---

## 9. Presupposition Verification - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:372-408`
**Prompt ID:** `presupposition_verification_v1@v1.0`
**Dil:** İngilizce
**Not:** Bu prompt TASK-A06 Presupposition Verification için kullanılır

### Full Prompt (Sistemden Giden Gerçek İstek) - Örnek Değerler
```
You are an expert in linguistic presupposition analysis (Lewis 1979, Beaver & Geurts 2014).

Analyze the following diplomatic utterance and determine if the presupposition candidate is valid.

## UTTERANCE:
Speaker: Constitutional Authority
Text: "Within the constitution, many legislations will be enacted and voted upon, which will delve into the details of what the post-five-year transitional period will look like."

## PRESUPPOSITION CANDIDATE:
Trigger word: "will"
Trigger type: future_tense
Presupposed content: "legislations exist to be enacted"
Rule-based confidence: 0.75

## YOUR TASK:
Determine if this is a genuine presupposition (content taken for granted by the speaker) or a false positive.
Consider:
- Does the trigger word actually induce a presupposition in this context?
- Is the presupposed content indeed taken for granted?
- Is this a genuine commitment or merely rhetorical?

Respond ONLY with valid JSON:
{
  "is_valid": <boolean>,
  "confidence": <float 0.0-1.0>,
  "refined_content": "<string - refined presupposed content if valid, otherwise null>",
  "reasoning": "<brief explanation>"
}
```

### API Request Parameters
```python
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=True
)
```

### Expected Response Schema
```json
{
  "is_valid": "boolean",
  "confidence": "float between 0.0 and 1.0",
  "refined_content": "string or null",
  "reasoning": "string - brief explanation"
}
```

### Example Expected Response
```json
{
  "is_valid": true,
  "confidence": 0.80,
  "refined_content": "The existence of a constitutional framework and legislative processes is presupposed",
  "reasoning": "The future tense 'will' presupposes that the constitutional framework exists and legislative processes are available, which is a reasonable presupposition in this context."
}
```

---

## 10. Event Coreference Verification - İNGİLİZCE PROMPT

**Sistemde kullanılan gerçek prompt:** `src/bb_paxdata/application/domain/services/prompt_registry.py:410-429`
**Prompt ID:** `event_coreference_verify@1`
**Dil:** İngilizce
**Not:** Bu prompt TASK-E04 Event Coreference için kullanılır

### Full Prompt (Sistemden Giden Gerçek İstek) - Örnek Değerler
```
Do these two event descriptions refer to the same real-world event?
Event A: Constitutional legislation enactment (date: post-five-year period, actors: legislative body)
Event B: Voting on constitutional legislations (date: transitional period, actors: constitutional authorities)
Answer YES or NO with a confidence score between 0.0 and 1.0.
Format: {"answer": "YES"|"NO", "confidence": float}
```

### API Request Parameters
```python
CompletionOptions(
    system_prompt="You are a diplomatic discourse analyst. Always respond with valid JSON.",
    temperature=0.3,
    max_tokens=1000,
    json_mode=True
)
```

### Expected Response Schema
```json
{
  "answer": "YES or NO",
  "confidence": "float between 0.0 and 1.0"
}
```

### Example Expected Response
```json
{
  "answer": "YES",
  "confidence": 0.75
}
```

---

## Test Talimatları

### Nasıl Kullanılır

1. **Her "Full Prompt (Sistemden Giden Gerçek İstek)" bölümünü kopyalayın** ve AI chat arayüzüne yapıştırın
2. **AI yanıtını** "Expected Response Schema" ile karşılaştırarak yapısını doğrulayın
3. **"Example Expected Response" ile kontrol ederek** içeriğin mantıklı olup olmadığını kontrol edin
4. **Koşullu promptlar için** (örneğin Anomaly Validation), test senaryonuza göre context/anomaly_block'u ayarlamanız gerekebilir

### Test Checklist

- [ ] Test 1: Ana AI Analizi (diplomatic_analysis) - **TÜRKÇE PROMPT**
- [ ] Test 2: Concept Extraction - İngilizce
- [ ] Test 3: 5W1H Extraction - İngilizce
- [ ] Test 4: LLM Position Estimator - İngilizce
- [ ] Test 5: Anomaly Validation - İngilizce (sadece anomali senaryosunda)
- [ ] Test 6: Frame Analysis - İngilizce
- [ ] Test 7: RAG Synthesis - İngilizce (context ile)
- [ ] Test 8: DKI Judge - İngilizce (historical data ile)
- [ ] Test 9: Presupposition Verification - İngilizce
- [ ] Test 10: Event Coreference Verification - İngilizce

### Önemli Notlar

- Tüm promptlar JSON yanıtı bekler (RAG Synthesis hariç - o free-form text)
- Temperature ayarları prompt'a göre değişir (deterministik için 0.0, analitik için 0.1-0.3)
- Bazı promptlar koşulludur ve sadece belirli pipeline senaryolarında çalışır
- Sistem "Recovery Engine" kullanarak bozuk JSON yanıtlarını 6-seviyeli kurtarma ile işler

### Pipeline Akışı Özeti

**Phase 1 (Local - AI Yok):**
- NER extraction
- Tokenization
- Negation detection
- Risk signal detection
- Power calculation
- Frame cues detection
- Stance density calculation
- Engagement scoring
- Country reference collection
- Appraisal vector analysis

**Phase 2 (Heavy - AI Çağrıları):**
1. **AI Analyst** - Ana diplomatik analiz (diplomatic_analysis - **TÜRKÇE PROMPT**)
2. **Frame Detection Pipeline:**
   - Concept Extraction (LLM - İngilizce)
   - Coreference Resolution (spaCy - lokal)
   - Embedding Frame Matching (sentence-transformers - lokal)
   - Perspective Clustering (lokal)
   - 5W1H Extraction (LLM - İngilizce)
   - Bias Detection (cosine similarity - lokal)
3. **Episodic/Thematic Classifier** - Frame classification (lokal)
4. **LLM Position Estimator** - Policy position scoring (İngilizce)
5. **Semantic Shift Calculator** - (koşullu) Historical comparison (İngilizce)

**Phase 3 (Detect - Koşullu AI):**
- **Anomaly Validation** - (koşullu) Sadece deterministik anomali tespit edilirse (İngilizce)

**Toplam AI Çağrısı:** Normal şartlarda 4-5 farklı LLM çağrısı (anomali yoksa)

### Dil Dağılımı

- **Türkçe Prompt:** diplomatic_analysis (sadece bu)
- **İngilizce Prompt:** Diğer tüm promptlar

Sistem dil bazlı prompt seçimi yapar ama şu anki aktif diplomatic_analysis prompt'u `language="any"` ile her dildeki metni analiz edebilir.
