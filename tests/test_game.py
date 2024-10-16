import asyncio

import pytest

from app.core.game import Game, GameManager
from app.core.player import AbstractPlayer

from .player import MockPlayer

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture
def player_1():
    return MockPlayer("player_1")


@pytest.fixture
def player_2():
    return MockPlayer("player_2")


@pytest.fixture
def game(player_1: AbstractPlayer, player_2: AbstractPlayer):
    return Game.make(player_1, player_2)


async def test_game_info():
    player_1 = MockPlayer("player_1", ["f2f3", "g2g4"])
    player_2 = MockPlayer("player_2", ["e7e5", "d8h4"])

    game = Game.make(player_1, player_2)

    await game.play()

    assert player_1.is_white
    assert player_2.is_white is False
    assert player_1.opponent_name == "player_2"
    assert player_2.opponent_name == "player_1"


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
