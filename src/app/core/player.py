import abc


class PlayerDisconnected(Exception):
    pass


class AbstractPlayer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def send_game_info(self, white: bool) -> None: ...

    @abc.abstractmethod
    async def receive_move(self) -> str: ...

    @abc.abstractmethod
    async def send_opponent_move(self, move: str) -> None: ...

    @abc.abstractmethod
    async def send_game_aborted(self) -> None: ...

    @abc.abstractmethod
    def is_connected(self) -> bool: ...
