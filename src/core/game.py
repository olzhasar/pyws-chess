import asyncio
import itertools
import logging
import uuid
from datetime import datetime
from typing import Self

from chess import Board

from .player import AbstractPlayer, PlayerDisconnected

logger = logging.getLogger(__name__)


class GameOver(Exception):
    pass


class Game:
    def __init__(
        self,
        game_id: str,
        player_1: AbstractPlayer,
        player_2: AbstractPlayer,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self.game_id = game_id
        self.white = player_1
        self.black = player_2
        self._players_iter = itertools.cycle([self.white, self.black])
        self._current_turn = next(self._players_iter)
        self._board = Board()
        self.start_time: asyncio.Future[datetime] = self._loop.create_future()

    @classmethod
    def make(
        cls,
        player_1: AbstractPlayer,
        player_2: AbstractPlayer,
        *,
        game_id: str | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> Self:
        game_id = game_id or str(uuid.uuid4())
        return cls(game_id, player_1, player_2, loop=loop)

    async def play(self) -> None:
        self.start_time.set_result(datetime.now())
        logger.info("Game %s started", self.game_id)

        await asyncio.gather(
            self.white.send_game_info(True), self.black.send_game_info(False)
        )

        await self.run()

    @property
    def _waiting_player(self) -> AbstractPlayer:
        if self._current_turn == self.white:
            return self.black
        else:
            return self.white

    async def run(self) -> None:
        while not self._board.outcome():
            if not self._waiting_player.is_connected():
                logger.debug("Player %s disconnected", self._waiting_player)
                try:
                    await self._current_turn.send_game_aborted()
                finally:
                    break

            logger.debug("Waiting for move from %s", self._current_turn)
            try:
                async with asyncio.timeout(5):
                    move = await self._current_turn.receive_move()
            except TimeoutError:
                continue
            except PlayerDisconnected:
                logger.debug("Player %s disconnected", self._current_turn)
                try:
                    await self._waiting_player.send_game_aborted()
                finally:
                    break
            try:
                logger.debug("Pushing move %s of player %s", move, self._current_turn)
                self._push_move(move)
            except ValueError:
                logger.error("Invalid move %s from player %s", move, self._current_turn)
                continue

            logger.debug("Sending move %s to player %s", move, self._waiting_player)
            try:
                await self._waiting_player.send_opponent_move(move)
            except PlayerDisconnected:
                logger.debug("Player %s disconnected", self._waiting_player)
                try:
                    await self._current_turn.send_game_aborted()
                finally:
                    break

            self._current_turn = next(self._players_iter)

        logger.info("Game %s ended", self.game_id)

    def _switch_turn(self) -> None:
        if self._current_turn == self.white:
            self._current_turn = self.black
        else:
            self._current_turn = self.white

    def _push_move(self, move_uci: str) -> None:
        try:
            self._board.push_uci(move_uci)
        except ValueError as exc:
            raise ValueError(f"Invalid move {move_uci}") from exc


class GameManager:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[AbstractPlayer] = asyncio.Queue()
        self._games: dict[str, Game] = {}
        self._run_task = None

    @property
    def running_loop(self) -> asyncio.AbstractEventLoop:
        assert self._loop, "Not started"
        return self._loop

    async def join(self, player: AbstractPlayer) -> None:
        logger.info("Player %s is joining", player)
        await self._queue.put(player)

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, exc_type: str, exc: Exception, tb: str) -> None:
        await self.stop()

    async def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        logger.info("Starting game manager")
        logger.info("Loop id: %s", id(loop))
        self._run_task = self.running_loop.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._run_task:
            self._run_task.cancel()
            await self._run_task

    async def run_forever(self) -> None:
        while True:
            try:
                logger.info("Waiting for players")
                game = await self.match()
                self.running_loop.create_task(game.play())
            except PlayerDisconnected:
                logger.debug("Player disconnected")
            except asyncio.CancelledError:
                break

    async def match(self) -> Game:
        player_1 = await self._queue.get()
        player_2 = await self._queue.get()

        if not player_1.is_connected():
            await self._queue.put(player_2)
            raise PlayerDisconnected

        return Game.make(player_1, player_2)
