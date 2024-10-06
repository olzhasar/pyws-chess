import asyncio

import pytest

from core.game import Game, GameManager
from core.player import AbstractPlayer

from .player import MockPlayer

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture
def player_1():
    return MockPlayer("player_1")


@pytest.fixture
def player_2():
    return MockPlayer("player_2")


@pytest.fixture
def game_id():
    return "game_id"


@pytest.fixture
def game(player_1: str, player_2: AbstractPlayer, game_id: AbstractPlayer):
    return Game.make(player_1, player_2, game_id=game_id)


async def test_checkmate():
    player_1 = MockPlayer("player_1", ["f2f3", "g2g4"])
    player_2 = MockPlayer("player_2", ["e7e5", "d8h4"])

    game = Game.make(player_1, player_2)

    await game.play()

    assert player_1.sent_opponent_moves == ["e7e5", "d8h4"]
    assert player_2.sent_opponent_moves == ["f2f3", "g2g4"]


async def test_illegal_move_skipped():
    player_1 = MockPlayer("player_1", ["f2f3", "invalid", "g2g4"])
    player_2 = MockPlayer("player_2", ["e7e5", "d8h4"])

    game = Game.make(player_1, player_2)

    await game.play()

    assert player_1.sent_opponent_moves == ["e7e5", "d8h4"]
    assert player_2.sent_opponent_moves == ["f2f3", "g2g4"]


async def test_joining():
    manager = GameManager()

    player_1 = MockPlayer("player_1")
    player_2 = MockPlayer("player_2")

    asyncio.create_task(manager.join(player_1))
    await asyncio.sleep(0.1)
    asyncio.create_task(manager.join(player_2))

    game = await manager.match()

    assert game.white == player_1
    assert game.black == player_2
