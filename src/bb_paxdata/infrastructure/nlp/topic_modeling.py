# src/bb_paxdata/infrastructure/nlp/topic_modeling.py
import asyncio
import logging

import numpy as np
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from umap import UMAP

from bb_paxdata.domain.models.segment import Segment
from bb_paxdata.domain.models.topic import TopicAssignment, TopicResult
from bb_paxdata.domain.services.prompt_registry import PromptRegistry
from bb_paxdata.domain.services.topic_modeling_protocol import TopicModelingProtocol

logger = logging.getLogger(__name__)


class TopicModelingService(TopicModelingProtocol):
    """Grootendorst (2022) BERTopic implementasyonu.

    c-TF-IDF formülü: c-TF-IDF(w, c) = tf(w, c) × log(1 + A / tf(w))
    A = ortalama kelime sayısı tüm konularda.
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        umap_n_neighbors: int = 15,
        umap_n_components: int = 5,
        umap_min_dist: float = 0.0,
        umap_metric: str = "cosine",
        hdbscan_min_cluster_size: int = 5,
        hdbscan_min_samples: int = 1,
        hdbscan_metric: str = "euclidean",
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._embedding_model_name = embedding_model
        self._umap_params = {
            "n_neighbors": umap_n_neighbors,
            "n_components": umap_n_components,
            "min_dist": umap_min_dist,
            "metric": umap_metric,
            "random_state": 42,
        }
        self._hdbscan_params = {
            "min_cluster_size": hdbscan_min_cluster_size,
            "min_samples": hdbscan_min_samples,
            "metric": hdbscan_metric,
        }
        self._prompt_registry = prompt_registry
        self._embedding_model: SentenceTransformer | None = None
        self._topic_model: BERTopic | None = None

    async def extract_topics(
        self,
        segments: list[Segment],
        language: str = "en",
        min_topic_size: int = 5,
        nr_topics: str | int = "auto",
    ) -> TopicResult:
        """Diplomatik segment listesinden BERTopic konularını çıkarır."""
        if not segments:
            return TopicResult(assignments=[], topic_keywords={}, model_metadata={})

        # 1. Akademik referans kaydı
        academic_ref = None
        if self._prompt_registry:
            try:
                # Faz 0'da academic_ref alanı eklendiği belirtilmiş
                prompt_meta = await self._prompt_registry.get("Grootendorst2022")
                academic_ref = (
                    prompt_meta.academic_ref if prompt_meta else "Grootendorst2022"
                )
            except Exception:
                academic_ref = "Grootendorst, M. (2022). BERTopic: Neural Topic Modeling. arXiv:2203.05794."

        # 2. Dokümanları hazırla
        # Segment modelinin 'sentences' listesi üzerinden metni birleştiriyoruz
        docs = []
        for seg in segments:
            text = " ".join(s.text for s in seg.sentences)
            docs.append(text)

        doc_ids = [seg.id for seg in segments]

        # 3. Embedding (CPU-bound → thread pool)
        embeddings = await self._embed_documents(docs)

        # 4. BERTopic pipeline (CPU-bound → thread pool)
        topic_model, topics, probs = await self._fit_bertopic(
            docs, embeddings, min_topic_size, nr_topics
        )

        # 5. Custom c-TF-IDF validation / override
        ctfidf_scores = await self._calculate_custom_ctfidf(topic_model, docs, topics)

        # 6. Olasılıksal dağılım normalize et
        assignments = self._normalize_probabilities(
            doc_ids, topics, probs, ctfidf_scores
        )

        # 7. Konu etiketleri
        topic_keywords = self._extract_topic_labels(topic_model, ctfidf_scores)

        metadata = {
            "academic_ref": academic_ref,
            "embedding_model": self._embedding_model_name,
            "umap_params": self._umap_params,
            "hdbscan_params": self._hdbscan_params,
            "language": language,
            "document_count": len(docs),
            "outlier_count": sum(1 for t in topics if t == -1),
        }

        return TopicResult(
            assignments=assignments,
            topic_keywords=topic_keywords,
            model_metadata=metadata,
        )

    async def embed_segments(self, segments: list[Segment]) -> dict[str, list[float]]:
        """Segment listesi için embedding vektörleri döner."""
        if not segments:
            return {}

        docs = [" ".join(s.text for s in seg.sentences) for seg in segments]
        embeddings = await self._embed_documents(docs)

        return {seg.id: embeddings[i].tolist() for i, seg in enumerate(segments)}

    async def get_frame_reference_embeddings(self) -> dict[str, list[float]]:
        """Entman (1993) 4 fonksiyonu için referans embedding'ler."""
        # Note: In a real scenario, these would be pre-computed or loaded.
        # Here we use representative keywords as proxies.
        frames = {
            "problem": ["problem", "crisis", "threat", "danger", "harm"],
            "cause": ["cause", "because", "due to", "reason", "source"],
            "moral": ["moral", "justice", "right", "wrong", "ethical"],
            "remedy": ["solution", "remedy", "fix", "improve", "address"],
        }

        results: dict[str, list[float]] = {}
        for name, keywords in frames.items():
            vecs = await self._embed_documents(keywords)
            results[name] = np.mean(vecs, axis=0).tolist()

        return results

    async def _embed_documents(self, docs: list[str]) -> np.ndarray:
        """SBERT embedding. Async thread pool."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self._embedding_model_name)
        return await asyncio.to_thread(
            self._embedding_model.encode, docs, show_progress_bar=False
        )

    async def _fit_bertopic(
        self,
        docs: list[str],
        embeddings: np.ndarray,
        min_topic_size: int,
        nr_topics: str | int,
    ) -> tuple[BERTopic, list[int], np.ndarray]:
        """UMAP + HDBSCAN + c-TF-IDF pipeline."""
        umap_model = UMAP(**self._umap_params)
        hdbscan_model = HDBSCAN(**self._hdbscan_params)

        topic_model = BERTopic(
            embedding_model=None,  # Zaten embed ettik
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            calculate_probabilities=True,
            verbose=False,
            nr_topics=nr_topics,
        )

        def _fit() -> tuple[BERTopic, list[int], np.ndarray]:
            topics, probs = topic_model.fit_transform(docs, embeddings)
            return topic_model, topics, probs

        return await asyncio.to_thread(_fit)

    async def _calculate_custom_ctfidf(
        self,
        topic_model: BERTopic,
        docs: list[str],
        topics: list[int],
    ) -> dict[int, dict[str, float]]:
        """Custom c-TF-IDF: tf(w,c) × log(1 + A / tf(w))

        A = ortalama kelime sayısı tüm konularda.
        tf(w) = kelimenin tüm konulardaki toplam frekansı.
        """

        def _calc() -> dict[int, dict[str, float]]:
            from collections import Counter, defaultdict

            topic_docs: dict[int, list[str]] = defaultdict(list)
            for doc, topic in zip(docs, topics):
                if topic != -1:
                    topic_docs[topic].append(doc)

            # Her konu için meta-doküman kelime frekansı
            topic_word_freq: dict[int, Counter[str]] = {}
            global_word_freq: Counter[str] = Counter()

            for topic_id, doc_list in topic_docs.items():
                text = (
                    " ".join(doc_list).lower().split()
                )  # Basit tokenizasyon; spaCy kullanılabilir
                freq = Counter(text)
                topic_word_freq[topic_id] = freq
                global_word_freq.update(freq)

            # A: ortalama kelime sayısı
            total_words = sum(len(" ".join(d).split()) for d in topic_docs.values())
            A = total_words / len(topic_docs) if topic_docs else 0.0

            # c-TF-IDF hesaplama
            ctfidf: dict[int, dict[str, float]] = {}
            for topic_id, freq in topic_word_freq.items():
                scores = {}
                for word, tf_wc in freq.items():
                    tf_w = global_word_freq[word]
                    if tf_w > 0 and A > 0:
                        score = tf_wc * np.log(1 + A / tf_w)
                        scores[word] = float(score)
                ctfidf[topic_id] = scores

            return ctfidf

        return await asyncio.to_thread(_calc)

    def _normalize_probabilities(
        self,
        doc_ids: list[str],
        topics: list[int],
        probs: np.ndarray,
        ctfidf_scores: dict[int, dict[str, float]],
    ) -> list[TopicAssignment]:
        """P(topic_k | doc) olasılıksal dağılımı normalize et."""
        assignments = []
        for idx, doc_id in enumerate(doc_ids):
            topic_id = topics[idx]

            if topic_id == -1:
                # Outlier: gürültü kategorisi
                topic_scores = {"-1": 1.0}
            else:
                # BERTopic prob vektörünü kullan
                if probs.ndim > 1 and idx < probs.shape[0]:
                    doc_probs = probs[idx]
                    # Sadece geçerli konuları al (-1 hariç)
                    # Not: doc_probs indeksi topic_id ile eşleşir
                    topic_scores = {
                        str(t): float(doc_probs[t])
                        for t in range(len(doc_probs))
                        if doc_probs[t] > 0.001  # Threshold
                    }
                else:
                    topic_scores = {str(topic_id): 1.0}

                # Normalize
                total = sum(topic_scores.values())
                if total > 0:
                    topic_scores = {k: v / total for k, v in topic_scores.items()}

            assignments.append(
                TopicAssignment(
                    segment_id=doc_id,
                    primary_topic=str(topic_id),
                    topic_scores=topic_scores,
                )
            )
        return assignments

    def _extract_topic_labels(
        self,
        topic_model: BERTopic,
        ctfidf_scores: dict[int, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Her konu için top-N c-TF-IDF kelime skorlarını döner."""
        labels = {}
        for topic_id, scores in ctfidf_scores.items():
            sorted_scores = dict(
                sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
            )
            labels[str(topic_id)] = sorted_scores
        return labels
