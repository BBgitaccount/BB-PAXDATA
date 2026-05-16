import numpy as np
import pytest
from bb_paxdata.domain.models.sbi_models import WordfishParams
from bb_paxdata.infrastructure.nlp.wordfish_scaler import WordfishScaler


@pytest.mark.asyncio
async def test_wordfish_recovery():
    """Verify that Wordfish can recover known latent positions from synthetic data."""
    np.random.seed(42)
    n_docs = 10
    n_terms = 100

    # 1. Create synthetic data
    true_theta = np.linspace(-2, 2, n_docs)
    true_beta = np.random.normal(0, 1, n_terms)
    true_psi = np.random.normal(2, 0.5, n_terms)
    true_alpha = np.random.normal(5, 0.5, n_docs)

    # log(lambda) = alpha + psi + beta * theta
    log_lambda = (
        true_alpha[:, np.newaxis]
        + true_psi[np.newaxis, :]
        + np.outer(true_theta, true_beta)
    )
    dtm = np.random.poisson(np.exp(log_lambda))

    doc_ids = [f"doc_{i}" for i in range(n_docs)]

    # 2. Fit Wordfish
    scaler = WordfishScaler(params=WordfishParams(max_iter=50))
    result = await scaler.fit_transform(dtm, doc_ids)

    # 3. Check correlation with true theta
    estimated_theta = np.array([result[did] for did in doc_ids])
    correlation = np.corrcoef(true_theta, estimated_theta)[0, 1]

    # Note: Wordfish may recover positions with inverted polarity (it's a latent model)
    # So we check the absolute correlation.
    assert abs(correlation) > 0.9, f"Recovery correlation too low: {correlation}"
    assert len(result) == n_docs
