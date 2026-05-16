from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class WordscoresCalibrator:
    """
    Implements Wordscores calibration (Laver et al. 2003).

    Academic Source:
    Laver, M., Benoit, K., & Garry, J. (2003). Extracting policy positions
    from political texts using words as data. American Political Science Review, 97(2), 311-331.
    """

    def __init__(self, smoothing: float = 1e-6):
        self.smoothing = smoothing
        self.word_scores_: np.ndarray | None = None
        self._is_calibrated = False

    async def calibrate(
        self,
        doc_term_matrix: np.ndarray,
        reference_scores: dict[str, float],  # document_id → a_priori score
        target_ids: list[str],
        all_document_ids: list[str],
    ) -> dict[str, float]:
        """
        Calibrate word scores using reference documents and score target documents.
        """
        n_docs, n_terms = doc_term_matrix.shape
        logger.info("wordscores.calibration_started", n_docs=n_docs, n_terms=n_terms)

        # 1. Map document IDs to matrix indices
        id_to_idx = {doc_id: i for i, doc_id in enumerate(all_document_ids)}
        ref_indices = [
            id_to_idx[rid] for rid in reference_scores.keys() if rid in id_to_idx
        ]
        target_indices = [id_to_idx[tid] for tid in target_ids if tid in id_to_idx]

        if not ref_indices:
            logger.error("wordscores.no_reference_docs")
            return {}

        # 2. Extract reference matrix and scores
        ref_matrix = doc_term_matrix[ref_indices]
        ref_values = np.array(
            [reference_scores[all_document_ids[idx]] for idx in ref_indices]
        )

        # 3. Compute relative frequency P_ij for reference docs
        # P_ij = f_ij / Σ_j f_ij
        row_sums = ref_matrix.sum(axis=1)[:, np.newaxis]
        P_ij = ref_matrix / (row_sums + self.smoothing)

        # 4. Compute word scores S_j
        # S_j = Σ_i (P_ij × a_priori_i) / Σ_i P_ij
        # Note: Σ_i P_ij is the sum of relative frequencies across all ref docs for word j
        sum_P_ij = P_ij.sum(axis=0)
        word_scores = (P_ij.T @ ref_values) / (sum_P_ij + self.smoothing)
        self.word_scores_ = word_scores

        # 5. Score target documents T_k
        # T_k = Σ_j (P_kj × S_j)
        target_matrix = doc_term_matrix[target_indices]
        target_row_sums = target_matrix.sum(axis=1)[:, np.newaxis]
        P_kj = target_matrix / (target_row_sums + self.smoothing)

        T_k = P_kj @ word_scores

        self._is_calibrated = True
        logger.info("wordscores.calibration_completed", n_targets=len(target_ids))

        return {target_id: float(score) for target_id, score in zip(target_ids, T_k)}
