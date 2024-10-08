from datetime import datetime

import msgspec


class BaseMessage(msgspec.Struct, tag=True):
    def serialize(self) -> bytes:
        return msgspec.json.encode(self)


class GameStarted(BaseMessage):
    start_time: datetime
    my_id: str
    am_i_white: bool


class Move(BaseMessage):
    uci: str


class GameAborted(BaseMessage):
    pass
