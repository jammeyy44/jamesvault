"""CACHE_REDIS_URL is read forgivingly: a bad value must never stop the API from booting."""
import pytest

from config import parse_redis_url


@pytest.mark.parametrize("raw,expected", [
    ("rediss://default:pw@host.upstash.io:6379", "rediss://default:pw@host.upstash.io:6379"),
    ("redis://localhost:6379/0", "redis://localhost:6379/0"),
    ("  rediss://default:pw@host:6379  ", "rediss://default:pw@host:6379"),
    ("redis-cli --tls -u redis://default:pw@host.upstash.io:6379", "rediss://default:pw@host.upstash.io:6379"),   # pasted command, --tls
    ("redis-cli -u redis://default:pw@host:6379", "redis://default:pw@host:6379"),
    ('"rediss://default:pw@host:6379"', "rediss://default:pw@host:6379"),
    ("unix:///var/run/redis.sock", "unix:///var/run/redis.sock"),
])
def test_valid_or_pasted_values_become_a_clean_url(raw, expected):
    assert parse_redis_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "default:pw@host:6379", "--tls -u host", "http://example.com", "example.upstash.io"])
def test_unusable_values_give_none_instead_of_crashing(raw):
    assert parse_redis_url(raw) is None
