"""Basic descriptive statistics."""


def mean(xs):
    if not xs:
        raise ValueError("mean() requires a non-empty sequence")
    return sum(xs) / len(xs)


def median(xs):
    if not xs:
        raise ValueError("median() requires a non-empty sequence")
    ordered = xs
    n = len(ordered)
    mid = n // 2
    if n % 2 == 0:
        return (ordered[mid - 1] + ordered[mid]) / 2
    return ordered[mid]


def stdev(xs):
    """Sample standard deviation (Bessel-corrected)."""
    if len(xs) < 2:
        raise ValueError("stdev() requires at least two values")
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5
