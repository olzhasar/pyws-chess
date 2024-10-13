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
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocketState

from app import messages
from app.core.game import GameManager
from app.core.player import AbstractPlayer, PlayerDisconnected

SRC_DIR = pathlib.Path(__file__).parent.parent
TEMPLATES_DIR = SRC_DIR / "templates"
STATIC_DIR = SRC_DIR / "static"

logger = logging.getLogger(__name__)


manager = GameManager()


templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

PING_FRAME_BYTES = b"\x89\x00"
PING_INTERVAL = 1


class WSPlayer(AbstractPlayer):
    def __init__(self, name: str, websocket: WebSocket) -> None:
        self.name = name
        self.websocket = websocket

    def __str__(self) -> str:
        return self.name

    async def send_game_info(self, white: bool, opponent_name: str) -> None:
        if not self.is_connected():
            return

        start_time = datetime.now()
        msg = messages.GameStarted(
            start_time=start_time,
            am_i_white=white,
            opponent_name=opponent_name,
        )
        logger.debug("Sending game info: %s", msg)
        try:
            await self.websocket.send_bytes(msg.serialize())
        except WebSocketDisconnect as exc:
            raise PlayerDisconnected from exc

    async def receive_move(self) -> str:
        if not self.is_connected():
            raise PlayerDisconnected

        try:
            msg = await self.websocket.receive_json()
        except WebSocketDisconnect as exc:
            raise PlayerDisconnected from exc
        binary = json.dumps(msg).encode()
        move = msgspec.json.decode(binary, type=messages.Move)
        return move.uci

    async def send_opponent_move(self, move: str) -> None:
        if not self.is_connected():
            raise PlayerDisconnected

        msg = messages.Move(uci=move)
        try:
            await self.websocket.send_bytes(msg.serialize())
        except WebSocketDisconnect as exc:
            raise PlayerDisconnected from exc

    async def send_game_aborted(self) -> None:
        if not self.is_connected():
            raise PlayerDisconnected

        msg = messages.GameAborted()
        logger.debug("Sending game aborted: %s", msg.serialize())
        await self.websocket.send_bytes(msg.serialize())

    def is_connected(self) -> bool:
        return (
            self.websocket.client_state == WebSocketState.CONNECTED
            and self.websocket.application_state == WebSocketState.CONNECTED
        )


@router.websocket("/ws")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
    name: str = Query(),
):
    await websocket.accept()

    # TODO: store sessions globally and recreate client on reconnect
    player = WSPlayer(name, websocket)
    logger.info("Player %s connected", player)

    await manager.join(player)

    while websocket.client_state != WebSocketState.DISCONNECTED:
        # Websocket disconnects are not propagated when not sending / receiving
        try:
            await websocket.send_bytes(PING_FRAME_BYTES)
        except Exception as exc:
            logger.debug("Player %s disconnected", player, exc_info=exc)
            break
        await asyncio.sleep(PING_INTERVAL)


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


app = create_app()
