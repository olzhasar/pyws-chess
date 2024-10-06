from core.player import AbstractPlayer


class MockPlayer(AbstractPlayer):
    def __init__(self, name: str, moves: list[str] | None = None) -> None:
        self.name = name
        self.is_white: bool | None = None
        self.moves = list(moves) if moves else []
        self.sent_opponent_moves: list[str] = []
        self.game_aborted = False

    def __str__(self) -> str:
        return self.name

    async def send_game_info(self, white: bool) -> None:
        self.is_white = white

    async def receive_move(self) -> str:
        return self.moves.pop(0)

    async def send_opponent_move(self, move: str) -> None:
        self.sent_opponent_moves.append(move)

    async def send_game_aborted(self) -> None:
        self.game_aborted = True

    def is_connected(self) -> bool:
        return True
