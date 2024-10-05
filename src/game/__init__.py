import asyncio
import logging
import uuid
from datetime import datetime
from typing import Self

from chess import Board

logger = logging.getLogger(__name__)


class GameOver(Exception):
    pass


class Game:
    def __init__(
        self,
        game_id: str,
        player_1: str,
        player_2: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.game_id = game_id
        self.player_1 = player_1
        self.player_2 = player_2
        self._move_lock = asyncio.Lock()
        self._current_turn = player_1
        self._wait_condition = asyncio.Condition()
        self._current_move: asyncio.Future[str] = self.loop.create_future()
        self._board = Board()
        self.start_time: asyncio.Future[datetime] = self.loop.create_future()
        self._start_barrier = asyncio.Barrier(3)

    @classmethod
    def make(
        cls,
        player_1: str,
        player_2: str,
        *,
        game_id: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> Self:
        game_id = game_id or str(uuid.uuid4())
        return cls(game_id, player_1, player_2, loop=loop)

    async def wait_for_start(self) -> datetime:
        await self._start_barrier.wait()
        return await self.start_time

    async def start(self) -> None:
        await self._start_barrier.wait()
        self.start_time.set_result(datetime.now())
        logger.info("Game %s started", self.game_id)

    async def wait_for_move(self, player_id: str) -> str:
        async with self._wait_condition:
            await self._wait_condition.wait_for(lambda: self._current_turn != player_id)

            self._check_game_over()

            move = await self._current_move
            async with self._move_lock:
                self._current_move = self.loop.create_future()
                self._switch_turn()
                self._wait_condition.notify()
            return move

    def _switch_turn(self) -> None:
        if self._current_turn == self.player_1:
            self._current_turn = self.player_2
        else:
            self._current_turn = self.player_1

    async def make_move(self, player_id: str, move: str) -> None:
        if self._current_move.done():
            raise ValueError("Previous move not yet consumed")

        async with self._move_lock:
            if not self._is_current_turn(player_id):
                raise ValueError("Not your turn")

            self._push_move(move)

            self._current_move.set_result(move)

            self._check_game_over()

    def _is_current_turn(self, player_id: str) -> bool:
        return self._current_turn == player_id

    def _push_move(self, move_uci: str) -> None:
        try:
            self._board.push_uci(move_uci)
        except ValueError as exc:
            raise ValueError(f"Invalid move {move_uci}") from exc

    def _check_game_over(self) -> None:
        outcome = self._board.outcome()
        if outcome:
            raise GameOver()


class GameClient:
    def __init__(self, game: Game, my_id: str) -> None:
        self.game = game
        self.my_id = my_id

    def am_i_white(self) -> bool:
        return self.my_id == self.game.player_1

    async def wait_for_start(self) -> datetime:
        return await self.game.wait_for_start()

    async def make_move(self, move: str) -> None:
        await self.game.make_move(self.my_id, move)

    async def wait_for_move(self) -> str:
        return await self.game.wait_for_move(self.my_id)


class GameManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._games: dict[str, Game] = {}
        self._game_futures: dict[str, asyncio.Future[GameClient]] = {}
        self._run_task = None

    async def join(self, player_id: str) -> GameClient:
        logger.info("Player %s is joining", player_id)
        assert self._loop
        self._game_futures[player_id] = self._loop.create_future()
        await self._queue.put(player_id)
        client = await self._game_futures[player_id]
        del self._game_futures[player_id]
        await client.wait_for_start()
        return client

    async def pop(self) -> str:
        return await self._queue.get()

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, exc_type: str, exc: Exception, tb: str) -> None:
        await self.stop()

    async def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        logger.info("Starting game manager")
        logger.info("Loop id: %s", id(loop))
        self._run_task = self._loop.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._run_task:
            self._run_task.cancel()
            await self._run_task

    async def run_forever(self) -> None:
        while True:
            try:
                logger.info("Waiting for players")
                await self.match()
            except asyncio.CancelledError:
                break

    async def match(self) -> None:
        player_1 = await self.pop()
        player_2 = await self.pop()

        game = Game.make(player_1, player_2)
        client_1 = GameClient(game, player_1)
        client_2 = GameClient(game, player_2)

        asyncio.create_task(game.start())

        self._game_futures[player_1].set_result(client_1)
        self._game_futures[player_2].set_result(client_2)
