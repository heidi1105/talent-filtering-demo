from enrichment.brands.calibrate import build_calibration_set, compute_distribution, percentile


def _pool(n):
    # Ordered by followers descending, as fetch_calibration_pool returns.
    return [(f"id-{i}", f"Talent {i}", None, f"handle{i}", 1000 * (n - i)) for i in range(n)]


# ---------------------------------------------------------------------------
# build_calibration_set
# ---------------------------------------------------------------------------

def test_top10_is_exactly_the_ten_highest_follower_rows():
    calibration_set = build_calibration_set(_pool(40), seed=1)
    top10 = [c for c in calibration_set if c.cohort == "top10"]
    assert [c.talent_id for c in top10] == [f"id-{i}" for i in range(10)]


def test_bottom_sample_is_drawn_only_from_the_back_half():
    pool = _pool(40)
    calibration_set = build_calibration_set(pool, seed=1)
    bottom = [c for c in calibration_set if c.cohort == "bottom_random10"]
    assert len(bottom) == 10
    back_half_ids = {f"id-{i}" for i in range(20, 40)}
    assert {c.talent_id for c in bottom} <= back_half_ids


def test_same_seed_is_reproducible():
    pool = _pool(40)
    a = build_calibration_set(pool, seed=5)
    b = build_calibration_set(pool, seed=5)
    assert [c.talent_id for c in a] == [c.talent_id for c in b]


def test_different_seed_can_change_the_bottom_sample():
    pool = _pool(40)
    a = build_calibration_set(pool, seed=1)
    b = build_calibration_set(pool, seed=2)
    bottom_a = {c.talent_id for c in a if c.cohort == "bottom_random10"}
    bottom_b = {c.talent_id for c in b if c.cohort == "bottom_random10"}
    assert bottom_a != bottom_b


def test_total_set_size_is_twenty():
    calibration_set = build_calibration_set(_pool(40), seed=1)
    assert len(calibration_set) == 20


def test_handles_a_pool_smaller_than_the_target_sample():
    # Tiny pools are a degenerate edge case (real pools run in the hundreds)
    # where the two cohorts can overlap — this just asserts it doesn't
    # crash and doesn't try to sample more rows than exist.
    calibration_set = build_calibration_set(_pool(8), seed=1)
    bottom = [c for c in calibration_set if c.cohort == "bottom_random10"]
    assert len(bottom) <= 4  # bottom half of an 8-row pool has only 4 rows


# ---------------------------------------------------------------------------
# compute_distribution / percentile
# ---------------------------------------------------------------------------

def test_compute_distribution_basic_stats():
    dist = compute_distribution([0, 0, 1, 2, 5])
    assert dist["n"] == 5
    assert dist["median"] == 1
    assert dist["max"] == 5
    assert dist["pct_zero"] == 40.0


def test_compute_distribution_empty_input():
    assert compute_distribution([]) == {"n": 0, "median": None, "p90": None, "max": None, "pct_zero": None}


def test_compute_distribution_no_zeros():
    dist = compute_distribution([1, 2, 3])
    assert dist["pct_zero"] == 0.0


def test_percentile_nearest_rank_p90_of_ten_items():
    values = list(range(1, 11))  # 1..10
    assert percentile(values, 0.9) == 9


def test_percentile_empty_returns_none():
    assert percentile([], 0.9) is None
