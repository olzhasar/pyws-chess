import asyncio
import json
import logging
import pathlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import msgspec
from fastapi import (
    APIRouter,
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocketState

from app import messages
from core.game import GameManager
from core.player import AbstractPlayer, PlayerDisconnected

APP_DIR = pathlib.Path(__file__).parent
TEMPLATES_DIR = APP_DIR.parent / "templates"
STATIC_DIR = APP_DIR.parent.parent / "static"

logger = logging.getLogger(__name__)


manager = GameManager()


templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

PING_FRAME_BYTES = b"\x89\x00"


class WSPlayer(AbstractPlayer):
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self._connected = True

    def __str__(self) -> str:
        return f"Player {id(self.websocket)}"

    async def send_game_info(self, white: bool) -> None:
        if not self.is_connected():
            return

        start_time = datetime.now()
        msg = messages.GameStartResponse(
            start_time=start_time, my_id=str(id(self.websocket)), am_i_white=white
        )
        logger.debug("Sending game info: %s", msg)
        await self.websocket.send_bytes(msg.serialize())

    async def receive_move(self) -> str:
        if not self.is_connected():
            raise PlayerDisconnected

        try:
            msg = await self.websocket.receive_json()
        except WebSocketDisconnect as exc:
            self._connected = False
            raise PlayerDisconnected from exc
        binary = json.dumps(msg).encode()
        move = msgspec.json.decode(binary, type=messages.MoveRequest)
        return move.uci

    async def send_opponent_move(self, move: str) -> None:
        if not self.is_connected():
            raise PlayerDisconnected

        msg = messages.MoveResponse(uci=move, for_id="opponent")
        try:
            await self.websocket.send_bytes(msg.serialize())
        except WebSocketDisconnect as exc:
            self._connected = False
            raise PlayerDisconnected from exc

    async def send_game_aborted(self) -> None:
        if not self.is_connected():
            raise PlayerDisconnected

        msg = messages.GameOverResponse()
        logger.debug("Sending game aborted: %s", msg.serialize())
        await self.websocket.send_bytes(msg.serialize())

    def is_connected(self) -> bool:
        return self._connected


@router.websocket("/ws")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
):
    await websocket.accept()

    # TODO: store sessions globally and recreate client on reconnect
    player = WSPlayer(websocket)

    await manager.join(player)

    while websocket.client_state != WebSocketState.DISCONNECTED:
        # Websocket disconnects are not propagated when not sending / receiving
        logger.debug("Sending ping frame to %s", player)
        try:
            await websocket.send_bytes(PING_FRAME_BYTES)
        except Exception as exc:
            logger.debug("Player %s disconnected", player, exc_info=exc)
            break
        await asyncio.sleep(1)


@router.get("/")
async def index(request: Request) -> Any:
    return templates.TemplateResponse(request, "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.start()
    try:
        yield
    finally:
        await manager.stop()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/img", StaticFiles(directory=STATIC_DIR / "img"))

    return app
