from datetime import datetime

import msgspec


class BaseMessage(msgspec.Struct, tag=True):
    def serialize(self) -> bytes:
        return msgspec.json.encode(self)


class InitResponse(BaseMessage):
    pass


class JoinRequest(BaseMessage):
    pass


class GameStartResponse(BaseMessage):
    start_time: datetime
    my_id: str
    am_i_white: bool


class MoveRequest(BaseMessage):
    uci: str


class MoveResponse(BaseMessage):
    for_id: str
    uci: str


class GameOverResponse(BaseMessage):
    # winner_id: str
    pass
