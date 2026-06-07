from __future__ import annotations

import numpy as np
import structlog
from scipy.optimize import minimize

from bb_paxdata.application.domain.models.sbi_models import WordfishParams

logger = structlog.get_logger(__name__)


class WordfishScaler:
    """
    Implements Poisson Wordfish scaling (Slapin & Proksch 2008).

    Academic Source:
    Slapin, J. B., & Proksch, S. O. (2008). A scaling model for estimating
    political positions from texts. American Journal of Political Science, 52(3), 705-722.
    """

    def __init__(self, params: WordfishParams | None = None):
        self.params = params or WordfishParams()
        self._is_fitted = False
        self.alpha_: np.ndarray | None = None  # document effects (n_docs,)
        self.psi_: np.ndarray | None = None  # word effects (n_terms,)
        self.beta_: np.ndarray | None = None  # word discrimination (n_terms,)
        self.theta_: np.ndarray | None = None  # latent positions (n_docs,)

    async def fit_transform(
        self,
        doc_term_matrix: np.ndarray,
        document_ids: list[str],
        params: WordfishParams | None = None,
    ) -> dict[str, float]:
        """
        Estimate latent positions θᵢ using Poisson MLE.

        Identification strategy: θ is normalized to mean 0 and std 1.
        """
        if params:
            self.params = params

        n_docs, n_terms = doc_term_matrix.shape
        logger.info("wordfish.fitting_started", n_docs=n_docs, n_terms=n_terms)

        # Initial estimates
        # Simple log-frequency based initialization with independence baseline adjustment
        self.alpha_ = np.array(np.log(doc_term_matrix.sum(axis=1) + 1e-6))
        self.psi_ = np.array(
            np.log(doc_term_matrix.sum(axis=0) + 1e-6)
            - np.log(doc_term_matrix.sum() + 1e-6)
        )
        self.beta_ = np.array(np.random.normal(0, 0.1, n_terms))
        self.theta_ = np.array(np.random.normal(0, 1.0, n_docs))

        # Identification constraints: mean(theta) = 0, std(theta) = 1
        assert self.theta_ is not None
        self.theta_ = (self.theta_ - np.mean(self.theta_)) / (
            np.std(self.theta_) + 1e-9
        )

        # Iterate between document and word parameters
        for i in range(self.params.max_iter):
            assert self.theta_ is not None
            old_theta = self.theta_.copy()

            # 1. Fix theta, alpha. Optimize psi, beta (Word parameters) independently
            def word_objective(
                p_word: np.ndarray,
                y_col: np.ndarray,
                alpha: np.ndarray,
                theta: np.ndarray,
            ) -> float:
                psi_j, beta_j = p_word
                log_lambda = alpha + psi_j + beta_j * theta
                log_lambda = np.clip(log_lambda, -10, 10)
                # Poisson loss: exp(log_lambda) - y * log_lambda
                loss = np.exp(log_lambda) - y_col * log_lambda
                return float(np.sum(loss) + 0.5 * self.params.beta_prior * (beta_j**2))

            assert self.psi_ is not None and self.beta_ is not None
            for j in range(n_terms):
                y_col = doc_term_matrix[:, j]
                p0 = np.array([self.psi_[j], self.beta_[j]])
                res_word = minimize(
                    word_objective,
                    p0,
                    args=(y_col, self.alpha_, self.theta_),
                    method="BFGS",
                    options={"maxiter": 10},
                )
                self.psi_[j] = res_word.x[0]
                self.beta_[j] = res_word.x[1]

            # 2. Fix psi, beta. Optimize alpha, theta (Document parameters) independently
            def doc_objective(
                p_doc: np.ndarray, y_row: np.ndarray, psi: np.ndarray, beta: np.ndarray
            ) -> float:
                alpha_i, theta_i = p_doc
                log_lambda = alpha_i + psi + beta * theta_i
                log_lambda = np.clip(log_lambda, -10, 10)
                loss = np.exp(log_lambda) - y_row * log_lambda
                return float(
                    np.sum(loss) + 0.5 * self.params.alpha_prior * (alpha_i**2)
                )

            assert self.alpha_ is not None and self.theta_ is not None
            for i_doc in range(n_docs):
                y_row = doc_term_matrix[i_doc, :]
                p0 = np.array([self.alpha_[i_doc], self.theta_[i_doc]])
                res_doc = minimize(
                    doc_objective,
                    p0,
                    args=(y_row, self.psi_, self.beta_),
                    method="BFGS",
                    options={"maxiter": 10},
                )
                self.alpha_[i_doc] = res_doc.x[0]
                self.theta_[i_doc] = res_doc.x[1]

            # 3. Identification: Normalize theta
            assert self.theta_ is not None
            self.theta_ = (self.theta_ - np.mean(self.theta_)) / (
                np.std(self.theta_) + 1e-9
            )

            # Check convergence
            diff = np.sqrt(np.mean((self.theta_ - old_theta) ** 2))
            if diff < self.params.tolerance:
                break

        self._is_fitted = True
        assert self.theta_ is not None
        return {
            doc_id: float(theta) for doc_id, theta in zip(document_ids, self.theta_)
        }

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted
