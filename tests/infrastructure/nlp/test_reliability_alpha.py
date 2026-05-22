from bb_paxdata.infrastructure.nlp.reliability import krippendorff_alpha


def test_krippendorff_alpha_nominal_perfect_agreement():
    # 2 coders, 4 items. Perfect agreement.
    data = [[1, 2, 1, 0], [1, 2, 1, 0]]
    alpha = krippendorff_alpha(data, metric="nominal")
    assert alpha == 1.0


def test_krippendorff_alpha_nominal_disagreement():
    # 2 coders, 5 items. Some disagreement.
    data = [[1, 2, 1, 0, 1], [1, 0, 1, 0, 2]]
    alpha = krippendorff_alpha(data, metric="nominal")
    assert alpha < 1.0
    assert alpha > -1.0


def test_krippendorff_alpha_missing_values():
    # 3 coders, 4 items. Some missing values.
    data = [[1, None, 1, 0], [1, 2, None, 0], [None, 2, 1, 0]]
    alpha = krippendorff_alpha(data, metric="nominal")
    # Item 0 has annotations [1, 1]
    # Item 1 has annotations [2, 2]
    # Item 2 has annotations [1, 1]
    # Item 3 has annotations [0, 0, 0]
    # All non-missing items are fully agreed upon
    assert alpha == 1.0


def test_krippendorff_alpha_interval():
    data = [[1.0, 2.0, 3.0], [1.2, 1.9, 3.1]]
    alpha = krippendorff_alpha(data, metric="interval")
    assert alpha > 0.8
