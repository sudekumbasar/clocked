from clocked.ratelimit import DAY, RateLimiter, client_id


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_per_minute_then_waits():
    clock = Clock()
    limiter = RateLimiter(per_minute=3, per_day=100, clock=clock)
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]
    clock.now = 61
    assert limiter.allow("a")


def test_limits_per_day_too():
    clock = Clock()
    limiter = RateLimiter(per_minute=100, per_day=5, clock=clock)
    for minute in range(5):
        clock.now = minute * 60
        assert limiter.allow("a")
    clock.now = 10 * 60
    assert not limiter.allow("a")
    clock.now = DAY + 1
    assert limiter.allow("a")


def test_players_are_counted_separately():
    limiter = RateLimiter(per_minute=1, per_day=10, clock=Clock())
    assert limiter.allow("a") and limiter.allow("b")
    assert not limiter.allow("a")


def test_a_refused_request_does_not_count():
    clock = Clock()
    limiter = RateLimiter(per_minute=1, per_day=2, clock=clock)
    assert limiter.allow("a")
    assert not limiter.allow("a")  # refused within the minute
    clock.now = 61
    assert limiter.allow("a")  # the refusal did not use up the day's second request


def test_client_is_the_first_forwarded_address():
    assert client_id("203.0.113.5, 10.0.0.1", "10.0.0.1") == "203.0.113.5"
    assert client_id(None, "127.0.0.1") == "127.0.0.1"
    assert client_id(None, None) == "unknown"
