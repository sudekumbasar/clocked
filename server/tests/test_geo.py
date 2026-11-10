from clocked.geo import distance_m


def test_zero_distance():
    assert distance_m(51.5, -0.1, 51.5, -0.1) == 0


def test_known_distance():
    # Hendrix (23 Brook Street) to Handel (25 Brook Street) from the CSV: next door, about 10 m.
    assert 3 < distance_m(51.51313, -0.14595, 51.5131035, -0.146055) < 15


def test_one_thousandth_degree_latitude_is_about_111_m():
    assert 110 < distance_m(51.5, -0.1, 51.501, -0.1) < 112
