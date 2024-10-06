import asyncio
import json
import logging
import pathlib
from contextlib import asynccontextmanager
from typing import Any

import msgspec
from fastapi import (
    APIRouter,
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import messages
from game import GameManager, GameOver

APP_DIR = pathlib.Path(__file__).parent
TEMPLATES_DIR = APP_DIR.parent / "templates"
STATIC_DIR = APP_DIR.parent.parent / "static"

logger = logging.getLogger(__name__)


manager = GameManager()


templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter()

GAME_JOIN_TIMEOUT = 100


@router.websocket("/ws")
async def websocket_endpoint(
    *,
    websocket: WebSocket,
):
    await websocket.accept()

    # TODO: store sessions globally and recreate client on reconnect
    player_id = str(id(websocket))

    try:
        async with asyncio.timeout(GAME_JOIN_TIMEOUT):
            client = await manager.join(player_id=player_id)
    except asyncio.TimeoutError:
        logger.error("Timeout joining game")
        raise WebSocketException(status.WS_1013_TRY_AGAIN_LATER)

    logger.info("Player %s joined game %s", player_id, client.game.game_id)

    my_turn = client.am_i_white()

    start_msg = messages.GameStartResponse(
        start_time=client.game.start_time.result(),
        my_id=player_id,
        am_i_white=my_turn,
    )
    logger.info("Sending start message: %s", start_msg)
    await websocket.send_bytes(start_msg.serialize())

    while True:
        if my_turn:
            try:
                logger.debug("Player %s waiting for move", player_id)
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                logger.info("Player %s disconnected", player_id)
                # TODO: notify opponent
                break

            logger.info("Player %s received message: %s", player_id, msg)
            binary = json.dumps(msg).encode()
            try:
                move = msgspec.json.decode(binary, type=messages.MoveRequest)
            except Exception as exc:
                logger.error("Invalid message received: %s\n%s", msg, exc)
                break

            try:
                await client.make_move(move.uci)
            except GameOver:
                logger.error("Received move after game over")
                await websocket.send_bytes(messages.GameOverResponse().serialize())
                break
            except ValueError as exc:
                logger.error("Error making move: %s", exc)
                continue
            else:
                logger.info("Player %s made move: %s", player_id, move.uci)
        else:
            logger.info("Player %s is waiting for opponent move", player_id)

            try:
                logger.debug("Player %s waiting for opponent move", player_id)
                # TODO: graceful shutdown
                uci = await client.wait_for_move()
            except Exception as exc:
                logger.error("Unexpected error while waiting for move: %s", exc)
                continue
            else:
                logger.info("Player %s received opponent move: %s", player_id, uci)
                await websocket.send_bytes(
                    messages.MoveResponse(uci=uci, for_id=player_id).serialize()
                )

        my_turn = not my_turn


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
