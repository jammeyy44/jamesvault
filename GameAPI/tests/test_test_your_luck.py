"""Test your luck: consecutive deposits without a cashout earn diamonds (3 -> 5, 4 -> 8, 5+ -> 15)."""
import pytest

from app import db
from app.models_site import PaymentOrder, Player
from app.routes.site.bonus import luck_reward


def _deposits(player_id, n, start=0):
    for i in range(n):
        db.session.add(PaymentOrder(player_id=player_id, method_id="m", method_value="cashapp", method_name="CashApp",
                                    amount_cents=1000, status="paid", idempotency_key=f"luck-{player_id}-{start + i}"))
    db.session.commit()


@pytest.mark.parametrize("count,diamonds", [(0, 0), (1, 0), (2, 0), (3, 5), (4, 8), (5, 15), (6, 15), (12, 15)])
def test_reward_table(count, diamonds):
    assert luck_reward(count) == diamonds


def test_state_lists_the_tiers_and_what_is_claimable(api, make_player):
    me = make_player(api)
    state = api.get('/api/v1/bonus/loss-streak').get_json()
    assert state["tiers"] == [{"deposits": 3, "diamonds": 5}, {"deposits": 4, "diamonds": 8}, {"deposits": 5, "diamonds": 15}]
    assert state["claimable"] == 0
    _deposits(me["id"], 4)
    state = api.get('/api/v1/bonus/loss-streak').get_json()
    assert state["losses"] == 4 and state["claimable"] == 8


def test_below_three_deposits_cannot_be_claimed(api, make_player):
    me = make_player(api)
    _deposits(me["id"], 2)
    assert api.post('/api/v1/bonus/loss-streak/claim').status_code == 400


def test_claiming_awards_the_tier_once_and_restarts_the_streak(api, make_player):
    me = make_player(api)
    _deposits(me["id"], 5)
    before = db.session.get(Player, me["id"]).diamonds
    r = api.post('/api/v1/bonus/loss-streak/claim')
    assert r.status_code == 201 and r.get_json()["diamonds_awarded"] == 15
    assert db.session.get(Player, me["id"]).diamonds == before + 15
    assert api.get('/api/v1/bonus/loss-streak').get_json()["losses"] == 0   # streak restarted
    assert api.post('/api/v1/bonus/loss-streak/claim').status_code == 400   # nothing left to claim
