from datetime import datetime

import msgspec


class BaseMessage(msgspec.Struct, tag=True):
    pass


class InitResponse(BaseMessage):
    pass


class JoinRequest(BaseMessage):
    pass


class GameStartResponse(BaseMessage):
    game_id: str
    opponent_id: str
    start_time: datetime


class MoveRequest(BaseMessage):
    uci: str


class MoveResponse(BaseMessage):
    player_id: str
    uci: str


class GameOverResponse(BaseMessage):
    # winner_id: str
    pass
