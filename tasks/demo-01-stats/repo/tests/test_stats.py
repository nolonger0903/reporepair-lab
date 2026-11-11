import pytest

from calc import mean, median, stdev


def test_mean_basic():
    assert mean([1, 2, 3]) == 2
    assert mean([2.5, 2.5]) == 2.5


def test_mean_empty():
    with pytest.raises(ValueError):
        mean([])


def test_median_odd():
    assert median([3, 1, 2]) == 2
    assert median([5]) == 5


def test_median_even_unsorted():
    assert median([4, 1, 3, 2]) == 2.5
    assert median([10, 2, 8, 4]) == 6


def test_median_empty():
    with pytest.raises(ValueError):
        median([])


def test_stdev_sample():
    # 样本标准差 (n-1) 约为 2.1381，总体标准差 (n) 为 2.0
    assert stdev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.1381, abs=1e-3)


def test_stdev_too_short():
    with pytest.raises(ValueError):
        stdev([1])
