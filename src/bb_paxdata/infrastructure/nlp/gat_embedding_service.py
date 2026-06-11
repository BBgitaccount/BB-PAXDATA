"""GAT Embedding Service — PyTorch Geometric tabanlı Graf Dikkat Ağı.

Bu servis, Fischer DNA'dan (aktörler + kavramlar) bir heterojen graf oluşturur,
2 katmanlı GATConv ağından geçirir ve her aktör için 256 boyutlu bir gömülme üretir.
Anomaly skoru, bir 'normal prototype' vektöründen kosinüs uzaklığı hesaplanarak elde edilir.

CPU-only çevrede çalışacak şekilde tasarlanmıştır (torch 2.x+cpu).

========== DESIGN NOTES ==========

C-01: GATConv.forward() kullanılır, edge_updater() değil — tam mesaj paslama.
C-02: Çift yönlü kenarlar (Actor→Concept + Concept→Actor) ile iki-atlamalı mesaj geçişi.
C-03: Normal prototip *training sonrası* kaydedilir; anomaly_score gerçek mesafe.
C-04: asyncio.to_thread ile ağır torch işlemleri event loop dışına taşınır.
M-07: Dropout regularizasyonu (layer-level, attention-level).
M-09: att_weights.shape = [E, heads] — doğru dokümantasyon.
m-01: GATContrastiveTrainer ayrı sınıf (SRP korunur).
m-02: Eksik düğüm özellikleri loglanır.
m-03: İzole aktörler ValueError fırlatır.
m-04: Aktör/kavram ID çakışması kontrolü.
GAP-06: Edge weight normalizasyonu (min-max).

Tüm formüller AGENTS.md'deki referans değerlerle uyumludur.
"""

from __future__ import annotations

import asyncio
import logging
import os

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

try:
    from torch_geometric.data import Data
    from torch_geometric.nn import GATConv

    _PYG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYG_AVAILABLE = False

from bb_paxdata.application.domain.models.discourse_network import DiscourseFlow
from bb_paxdata.application.domain.models.gat_models import (
    ANOMALY_SENTINEL,
    EMBEDDING_DIM,
    GATEmbedding,
)
from bb_paxdata.application.domain.ports.i_gat_embedding_service import (
    IGATEmbeddingService,
)

logger = logging.getLogger(__name__)

# ── Sabitler ──────────────────────────────────────────────────────────────────
HIDDEN_DIM = 128  # Ara katman boyutu
NUM_HEADS = 4  # Dikkat başı sayısı (GATConv)
DROPOUT = 0.3  # Düğüm dropout oranı
ATT_DROPOUT = 0.1  # Dikkat katsayısı dropout oranı
FEATURE_DIM = 384  # SBERT all-MiniLM-L6-v2 çıktı boyutu
MARGIN_DEFAULT = 0.1  # Triplet loss margin (cosine distance space)
LR_DEFAULT = 1e-4
WEIGHT_DECAY_DEFAULT = 1e-5

# ── PyTorch Geometric Kontrolü ────────────────────────────────────────────────


def _require_pyg() -> None:
    """Raise ImportError if PyTorch Geometric is not available."""
    if not _PYG_AVAILABLE:
        raise ImportError(
            "torch_geometric bulunamadı. "
            "`pip install torch-geometric` veya pyproject.toml'a ekleyin."
        )


# ── PyTorch Modeli ────────────────────────────────────────────────────────────


class GATNetwork(nn.Module):
    """İki katmanlı Graf Dikkat Ağı (GATConv).

    Layer 1: concat multi-head (hidden_channels → hidden_channels * heads)
    Layer 2: averaging single-head (hidden_channels * heads → out_channels=256)

    Dropout:
        - projection layer sonrası (DROPOUT=0.3)
        - conv1 sonrası (DROPOUT=0.3)
        - attention katsayılarında (ATT_DROPOUT=0.1)
    """

    def __init__(
        self,
        in_channels: int = FEATURE_DIM,
        hidden_channels: int = HIDDEN_DIM,
        out_channels: int = EMBEDDING_DIM,
        heads: int = NUM_HEADS,
        dropout: float = DROPOUT,
        attention_dropout: float = ATT_DROPOUT,
    ) -> None:
        super().__init__()
        self.proj = nn.Linear(in_channels, hidden_channels)
        self.proj_dropout = nn.Dropout(p=dropout)
        self.conv1 = GATConv(
            in_channels=hidden_channels,
            out_channels=hidden_channels,
            heads=heads,
            concat=True,
            edge_dim=1,
            dropout=attention_dropout,
        )
        self.conv1_dropout = nn.Dropout(p=dropout)
        self.conv2 = GATConv(
            in_channels=hidden_channels * heads,
            out_channels=out_channels,
            heads=1,
            concat=False,
            edge_dim=1,
            dropout=attention_dropout,
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # (C-01) Doğru çağrı: edge_updater değil, full __call__ ile message-passing
        x = self.proj_dropout(F.relu(self.proj(x)))

        # Layer 1: concat multi-head, return_attention_weights=True
        x, (_, att_weights) = self.conv1(
            x, edge_index, edge_attr=edge_attr, return_attention_weights=True
        )  # x: [N, hidden * heads], att_weights: [E, heads]
        x = self.conv1_dropout(F.relu(x))

        # Layer 2: averaging single head
        x = self.conv2(x, edge_index, edge_attr=edge_attr)
        # x: [N, EMBEDDING_DIM]

        return x, att_weights  # att_weights: [E, heads] — (M-09) shape doğru


# ── Veri İnşa Yardımcıları ───────────────────────────────────────────────────


def _build_pyg_data(
    flow: DiscourseFlow,
    actor_features: dict[str, list[float]],
    concept_features: dict[str, list[float]],
    device: torch.device,
) -> tuple[Data, dict[str, int], list[str]]:
    """Fischer DNA DiscourseFlow'dan PyG Data objesi oluşturur.

    (C-02) Çift yönlü kenarlar: Actor→Concept + Concept→Actor.
    (m-04) Aktör/kavram ID çakışması kontrolü.
    (m-02) Eksik özellik loglaması.
    (GAP-06) Edge weight min-max normalizasyonu.

    Returns:
        (pyg_data, node_to_idx, ordered_node_ids)
    """
    actor_ids = list(flow.actor_ids)
    concept_ids = list(flow.concept_ids)

    # (m-04) ID çakışması kontrolü
    actor_set = set(actor_ids)
    concept_set = set(concept_ids)
    collision = actor_set & concept_set
    if collision:
        raise ValueError(
            f"actor_ids ve concept_ids {len(collision)} adet çakışan ID içeriyor: "
            f"{collision}. Bipartite graf ayrık düğüm kümeleri gerektirir."
        )

    # (m-03) İzole aktör kontrolü — hiç kenarı olmayan aktör
    edge_actor_ids = {e.actor_id for e in flow.edges}
    isolated_actors = [a for a in actor_ids if a not in edge_actor_ids]
    if isolated_actors:
        # Uyarı: izole aktörler için kenar bulunamazsa, embedding anlamsız olur
        raise ValueError(
            f"DiscourseFlow {len(isolated_actors)} izole aktör içeriyor "
            f"(hiç kenarı yok). Anlamlı GAT embedding hesaplanamaz. "
            f"ID'ler: {isolated_actors}"
        )

    # Düğüm sırası: önce aktörler, sonra kavramlar
    all_ids = actor_ids + concept_ids
    id_to_idx = {nid: i for i, nid in enumerate(all_ids)}

    # Boyut denetimi
    sample_feat: list[float] | None = None
    for d in (actor_features, concept_features):
        for v in d.values():
            if sample_feat is None:
                sample_feat = v
            elif len(v) != len(sample_feat):
                raise ValueError(
                    f"Özellik boyutu tutarsız: {len(v)} ≠ {len(sample_feat)}"
                )

    feat_dim = len(sample_feat) if sample_feat else FEATURE_DIM

    # (m-02) Özellik matrisi — eksik düğümleri logla
    x_rows: list[list[float]] = []
    missing_count = 0
    for nid in all_ids:
        feat = actor_features.get(nid) or concept_features.get(nid)
        if feat is None:
            missing_count += 1
            feat = [0.0] * feat_dim
        x_rows.append(feat)

    if missing_count > 0:
        logger.warning(
            "_build_pyg_data: %d düğüm için özellik bulunamadı — sıfır vektör kullanıldı",
            missing_count,
        )

    x = torch.tensor(x_rows, dtype=torch.float32, device=device)

    # (C-02) Kenar indeksleri — çift yönlü
    src_list: list[int] = []
    dst_list: list[int] = []
    edge_weights: list[float] = []

    for edge in flow.edges:
        if edge.actor_id not in id_to_idx:
            logger.warning("Bilinmeyen aktör düğüm: %s", edge.actor_id)
            continue
        if edge.concept_id not in id_to_idx:
            logger.warning("Bilinmeyen kavram düğüm: %s", edge.concept_id)
            continue
        s = id_to_idx[edge.actor_id]
        d = id_to_idx[edge.concept_id]
        w = float(edge.weight)
        # Actor → Concept
        src_list.append(s)
        dst_list.append(d)
        edge_weights.append(w)
        # Concept → Actor (çift yönlü)
        src_list.append(d)
        dst_list.append(s)
        edge_weights.append(w)

    # (GAP-06) Edge weight min-max normalizasyonu
    if edge_weights:
        w_tensor = torch.tensor(edge_weights, dtype=torch.float32, device=device)
        w_min, w_max = w_tensor.min(), w_tensor.max()
        if (w_max - w_min) > 1e-8:
            w_tensor = (w_tensor - w_min) / (w_max - w_min)
        edge_attr = w_tensor.unsqueeze(1)  # [E] → [E, 1]; GATConv edge_dim=1 bekler
    else:
        edge_attr = torch.empty((0, 1), dtype=torch.float32, device=device)

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long, device=device)

    return Data(x=x, edge_index=edge_index, edge_attr=edge_attr), id_to_idx, all_ids


# ── Anomaly Skoru ─────────────────────────────────────────────────────────────


def _compute_anomaly_score(
    embedding: torch.Tensor,
    normal_prototype: torch.Tensor | None,
) -> float:
    """Kosinüs uzaklığını [0, 1] aralığında hesaplar.

    (C-03) Prototip None ise -1.0 sentinel döner.
    """
    if normal_prototype is None:
        return ANOMALY_SENTINEL

    emb_norm = F.normalize(embedding.unsqueeze(0), p=2, dim=1)
    proto_norm = F.normalize(normal_prototype.unsqueeze(0), p=2, dim=1)
    cos_sim = F.cosine_similarity(emb_norm, proto_norm).item()
    # [0, 2] aralığındaki kosinüs uzaklığını [0, 1]'e normalize et
    cosine_dist = (1.0 - cos_sim) / 2.0
    return cosine_dist


# ── Ana Servis ────────────────────────────────────────────────────────────────


class GATEmbeddingService:
    """Actor gömülmeleri üretir ve anomaly skoru hesaplar.

    Kullanım:
        service = GATEmbeddingService()
        embeddings = await service.compute_embeddings(flow, actor_features, concept_features)
    """

    def __init__(
        self,
        model: GATNetwork | None = None,
        model_path: str | None = None,
        device: torch.device | None = None,
    ) -> None:
        _require_pyg()

        self._device = device or torch.device("cpu")

        if model is not None:
            self._model = model
        else:
            self._model = GATNetwork(in_channels=FEATURE_DIM)

        self._model.to(self._device)
        self._model.eval()

        # (C-03) Normal prototip: eğitim sonrası kaydedilir/dosyadan yüklenir
        self._normal_prototype: torch.Tensor | None = None
        self._model_path: str | None = model_path

        if model_path is not None:
            prototype_path = self._resolve_prototype_path(model_path)
            if os.path.exists(prototype_path):
                logger.info("Normal prototip yükleniyor: %s", prototype_path)
                self._normal_prototype = torch.load(
                    prototype_path, map_location=self._device, weights_only=True
                )

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_prototype_path(model_path: str) -> str:
        """Model dosya yolundan prototip dosya yolunu türetir."""
        base, ext = os.path.splitext(model_path)
        return f"{base}_prototype{ext}"

    def update_normal_prototype(self, normal_embeddings: list[list[float]]) -> None:
        """Verilen gömülmelerin L2-normalize ortalamasını prototip yap.

        (C-03) Eğitim sonunda tüm 'normal' etiketli embedding'lerle çağrılır.
        """
        if not normal_embeddings:
            logger.warning("update_normal_prototype: boş liste, prototip güncellenmedi")
            return
        emb_tensor = torch.tensor(
            normal_embeddings, dtype=torch.float32, device=self._device
        )
        emb_normalized = F.normalize(emb_tensor, p=2, dim=1)
        self._normal_prototype = emb_normalized.mean(dim=0)

        # (C-03) Prototipi dosyaya kaydet
        if self._model_path is not None:
            proto_path = self._resolve_prototype_path(self._model_path)
            torch.save(self._normal_prototype, proto_path)
            logger.info("Normal prototip kaydedildi: %s", proto_path)

    # ── Çekirdek Hesaplama (senkron) ─────────────────────────────────────────

    def _compute_embeddings_sync(
        self,
        flow: DiscourseFlow,
        actor_features: dict[str, list[float]],
        concept_features: dict[str, list[float]],
    ) -> list[GATEmbedding]:
        """CPU üzerinde senkron olarak graf inferans çalıştırır."""
        data, _, _ = _build_pyg_data(
            flow,
            actor_features,
            concept_features,
            self._device,
        )

        with torch.no_grad():
            embeddings_tensor, att_weights = self._model(
                data.x,
                data.edge_index,
                data.edge_attr,
            )
            # embeddings_tensor: [N, EMBEDDING_DIM]
            # att_weights: [E, heads]

        # Aktör index'leri (ordered_ids'de aktörler önce gelir)
        actor_count = len(flow.actor_ids)
        actor_embs = embeddings_tensor[:actor_count]  # [actor_count, 256]

        # (M-09) att_weights: [E, heads] → per-edge mean across heads
        mean_att = att_weights.mean(dim=-1)  # [E]

        # Actor → Concept attention mapping (sadece Actor→Concept yönü)
        # edges çift yönlü eklendi: [A→C, C→A, A→C, C→A, ...]
        # Tek index'ler (0, 2, 4, ...) Actor→Concept yönüdür
        forward_edge_count = len(flow.edges)
        forward_att = mean_att[:forward_edge_count]  # ilk yarı aktör→kavram

        # Actor→Concept attention mapping: her aktör için toplam dikkat
        actor_concept_att: dict[str, list[tuple[str, float]]] = {}
        for i, edge in enumerate(flow.edges):
            if i >= forward_edge_count:
                break
            aid = edge.actor_id
            cid = edge.concept_id
            att_val = float(forward_att[i].item()) if i < forward_att.shape[0] else 0.0
            actor_concept_att.setdefault(aid, []).append((cid, att_val))

        # Sonuçları oluştur
        results: list[GATEmbedding] = []
        for i, aid in enumerate(flow.actor_ids):
            vec = actor_embs[i]  # sadece aktör satırları
            vec_numpy = vec.cpu().numpy().astype(np.float32)

            # Top-5 characteristic concepts
            att_list = actor_concept_att.get(aid, [])
            sorted_concepts = sorted(att_list, key=lambda x: x[1], reverse=True)
            top_concepts = [c[0] for c in sorted_concepts[:5]]

            # Anomaly skoru
            anomaly_score = _compute_anomaly_score(vec, self._normal_prototype)

            results.append(
                GATEmbedding(
                    actor_id=aid,
                    session_id=flow.session_id,
                    embedding=vec_numpy,
                    characteristic_concepts=top_concepts,
                    anomaly_score=anomaly_score,
                )
            )

        return results

    # ── Asenkron Arayüz ──────────────────────────────────────────────────────

    async def compute_embeddings(
        self,
        flow: DiscourseFlow,
        actor_features: dict[str, list[float]],
        concept_features: dict[str, list[float]],
    ) -> list[GATEmbedding]:
        """(C-04) Ağır Torch hesaplamalarını ayrı thread'de çalıştırır."""
        return await asyncio.to_thread(
            self._compute_embeddings_sync,
            flow,
            actor_features,
            concept_features,
        )

    # ── Model / Prototip erişimi (m-01: trainer için) ────────────────────────

    @property
    def model(self) -> GATNetwork:
        return self._model

    @property
    def normal_prototype(self) -> torch.Tensor | None:
        return self._normal_prototype

    @property
    def device(self) -> torch.device:
        return self._device


# ── Kontrastif Eğitici (m-01: ayrı sınıf, SRP korunur) ────────────────────────


class GATContrastiveTrainer:
    """GAT modelini triplet loss ile eğitir.

    (M-08: semi-hard negative mining + M-07: dropout train/eval geçişi)
    """

    def __init__(
        self,
        service: GATEmbeddingService,
        lr: float = LR_DEFAULT,
        margin: float = MARGIN_DEFAULT,
        weight_decay: float = WEIGHT_DECAY_DEFAULT,
    ) -> None:
        self._service = service
        self._model = service.model
        self._device = service.device
        self._margin = margin
        self._optimizer = torch.optim.AdamW(
            self._model.parameters(), lr=lr, weight_decay=weight_decay
        )

    # ── Semi-Hard Negative Mining (M-08) ──────────────────────────────────────

    @staticmethod
    def _mine_triplets(
        embeddings: torch.Tensor,  # [N, D]
        labels: torch.Tensor,  # [N] — 0=normal, 1=anomaly
        margin: float,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Semi-hard negative mining.

        Returns:
            (anchor_indices, positive_indices, negative_indices)
        """
        N = embeddings.size(0)
        emb_norm = F.normalize(embeddings, p=2, dim=1)
        # Kosinüs uzaklık matrisi [N, N]
        dist_matrix = 1.0 - torch.mm(emb_norm, emb_norm.T)

        anchors, positives, negatives = [], [], []
        for i in range(N):
            label_i = labels[i].item()
            pos_mask = (labels == label_i) & (
                torch.arange(N, device=embeddings.device) != i
            )
            neg_mask = labels != label_i

            if pos_mask.sum() == 0 or neg_mask.sum() == 0:
                continue

            # En zor positive: aynı sınıfta en uzak
            pos_distances = dist_matrix[i][pos_mask]
            pos_global = torch.where(pos_mask)[0][pos_distances.argmax()]

            d_ap = dist_matrix[i, pos_global].item()
            neg_distances = dist_matrix[i][neg_mask]

            # Semi-hard: d(a,n) in (d_ap, d_ap + margin)
            semi_hard = (neg_distances > d_ap) & (neg_distances < d_ap + margin)

            if semi_hard.sum() == 0:
                # Fallback: hardest negative (en yakın)
                neg_idx = neg_distances.argmin()
            else:
                neg_sub = torch.where(semi_hard)[0]
                # semi-hard içinden en zoru (en yakın)
                neg_idx = neg_sub[neg_distances[semi_hard].argmin()]

            anchors.append(i)
            positives.append(pos_global.item())
            # neg_idx scalar veya tensor olabilir
            if isinstance(neg_idx, torch.Tensor):
                neg_idx = neg_idx.item()
            negatives.append(neg_idx)

        return (
            torch.tensor(anchors, device=embeddings.device),
            torch.tensor(positives, device=embeddings.device),
            torch.tensor(negatives, device=embeddings.device),
        )

    # ── Eğitim Adımı ──────────────────────────────────────────────────────────

    def train_epoch(
        self,
        session_graphs: list[
            tuple[DiscourseFlow, dict[str, list[float]], dict[str, list[float]]]
        ],
        labels: dict[str, torch.Tensor],  # flow.session_id + actor_id → label
    ) -> float:
        """Bir epoch eğitim çalıştırır.

        Args:
            session_graphs: (flow, actor_features, concept_features) triple listesi.
            labels: {f"{flow.session_id}:{actor_id}": 0/1} etiketleri.

        Returns:
            Ortalama loss değeri.
        """
        self._model.train()
        total_loss = 0.0
        batch_count = 0
        loss_fn = torch.nn.TripletMarginWithDistanceLoss(
            distance_function=lambda u, v: 1.0 - F.cosine_similarity(u, v),
            margin=self._margin,
            reduction="mean",
        )

        for flow, actor_feats, concept_feats in session_graphs:
            # Embedding'leri hesapla
            data, _, _ = _build_pyg_data(
                flow,
                actor_feats,
                concept_feats,
                self._device,
            )
            embeddings, _ = self._model(data.x, data.edge_index, data.edge_attr)

            # Aktör embedding'lerini ve etiketlerini topla
            actor_count = len(flow.actor_ids)
            actor_embs = embeddings[:actor_count]
            actor_labels_list: list[int] = []
            actor_indices: list[int] = []
            for idx, aid in enumerate(flow.actor_ids):
                key = f"{flow.session_id}:{aid}"
                lbl = labels.get(key)
                if lbl is not None:
                    actor_labels_list.append(
                        int(lbl.item() if isinstance(lbl, torch.Tensor) else lbl)
                    )
                    actor_indices.append(idx)

            if len(actor_labels_list) < 2:
                continue  # en az 2 etiket gerekli (anchor + positive)

            label_tensor = torch.tensor(
                actor_labels_list, dtype=torch.long, device=self._device
            )
            emb_subset = actor_embs[torch.tensor(actor_indices, device=self._device)]

            # Semi-hard negative mining
            anchor_i, pos_i, neg_i = self._mine_triplets(
                emb_subset, label_tensor, self._margin
            )
            if anchor_i.numel() == 0:
                continue

            # Loss hesapla
            anchor_emb = emb_subset[anchor_i]
            pos_emb = emb_subset[pos_i]
            neg_emb = emb_subset[neg_i]

            loss = loss_fn(anchor_emb, pos_emb, neg_emb)

            self._optimizer.zero_grad()
            loss.backward()
            self._optimizer.step()

            total_loss += loss.item()
            batch_count += 1

        self._model.eval()
        return total_loss / max(1, batch_count)

    def save_checkpoint(
        self, model_path: str, prototype_embeddings: list[list[float]] | None = None
    ) -> None:
        """Model ağırlıklarını ve prototipi kaydeder."""
        torch.save(self._model.state_dict(), model_path)
        logger.info("Model kaydedildi: %s", model_path)

        if prototype_embeddings:
            self._service.update_normal_prototype(prototype_embeddings)


# ── Port conformance guard ────────────────────────────────────────────────────
_svc_stub = GATEmbeddingService.__new__(GATEmbeddingService)
assert isinstance(
    _svc_stub, IGATEmbeddingService
), "GATEmbeddingService must satisfy IGATEmbeddingService port"
del _svc_stub
