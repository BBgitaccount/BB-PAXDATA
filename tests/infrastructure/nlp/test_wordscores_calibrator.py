import numpy as np
import pytest
from bb_paxdata.infrastructure.nlp.wordscores_calibrator import WordscoresCalibrator


@pytest.mark.asyncio
async def test_wordscores_toy_example():
    """Verify Wordscores on a toy example."""
    # Toy DTM: 2 ref docs, 1 target doc, 3 words
    dtm = np.array(
        [
            [10, 0, 0],  # Ref Doc 1 (Score: -1)
            [0, 0, 10],  # Ref Doc 2 (Score: 1)
            [5, 0, 5],  # Target Doc (Expected Score: 0)
        ]
    )

    reference_scores = {"ref1": -1.0, "ref2": 1.0}

    all_doc_ids = ["ref1", "ref2", "target1"]
    target_ids = ["target1"]

    calibrator = WordscoresCalibrator()
    result = await calibrator.calibrate(dtm, reference_scores, target_ids, all_doc_ids)

    assert "target1" in result
    # For target1, it has equal parts of ref1 and ref2 words, so score should be close to 0
    assert abs(result["target1"]) < 0.1
