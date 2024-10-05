import asyncio

import pytest
import pytest_asyncio

from game import Game, GameClient, GameManager, GameOver

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture
def player_1():
    return "player_1"


@pytest.fixture
def player_2():
    return "player_2"


@pytest.fixture
def game_id():
    return "game_id"


@pytest.fixture
def game(player_1: str, player_2: str, game_id: str):
    return Game.make(player_1, player_2, game_id=game_id)


@pytest.fixture
def client_1(game: Game, player_1: str):
    return GameClient(game, player_1)


@pytest.fixture
def client_2(game: Game, player_2: str):
    return GameClient(game, player_2)


async def test_moves(game: Game, client_1: GameClient, client_2: GameClient):
    await client_1.make_move("e2e4")
    assert await client_2.wait_for_move() == "e2e4"

    await client_2.make_move("e7e5")
    assert await client_1.wait_for_move() == "e7e5"

    await client_1.make_move("g1f3")
    assert await client_2.wait_for_move() == "g1f3"


@pytest.mark.parametrize("move", ["e2e8", "e5", "illegal"])
async def test_illegal_moves(
    game: Game, client_1: GameClient, client_2: GameClient, move: str
):
    with pytest.raises(ValueError):
        await client_1.make_move(move)


async def test_waiting(game: Game, client_1: GameClient, client_2: GameClient):
    await client_1.make_move("e2e4")

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client_1.wait_for_move(), timeout=0.2)

    assert await client_2.wait_for_move() == "e2e4"

    await client_2.make_move("e7e5")

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client_2.wait_for_move(), timeout=0.2)

    assert await client_1.wait_for_move() == "e7e5"


async def test_checkmate(game: Game, client_1: GameClient, client_2: GameClient):
    await client_1.make_move("f2f3")
    await client_2.wait_for_move()

    await client_2.make_move("e7e5")
    await client_1.wait_for_move()

    await client_1.make_move("g2g4")
    await client_2.wait_for_move()

    with pytest.raises(GameOver):
        await client_2.make_move("d8h4")

    with pytest.raises(GameOver):
        await client_1.wait_for_move()


@pytest_asyncio.fixture(loop_scope="module")
async def game_manager():
    instance = GameManager()
    async with instance:
        yield instance


async def test_joining(game_manager: GameManager):
    player_1 = "player_1"
    player_2 = "player_2"

    task_1 = asyncio.create_task(game_manager.join(player_1))
    task_2 = asyncio.create_task(game_manager.join(player_2))

    client_1, client_2 = await asyncio.wait_for(
        asyncio.gather(task_1, task_2), timeout=1
    )

    assert client_1.game is client_2.game
    assert client_1.game.start_time.done()
