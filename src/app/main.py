import asyncio
import logging
import pathlib
from typing import Any

from fastapi import (
    APIRouter,
    FastAPI,
    Request,
    WebSocket,
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

logging.basicConfig(level=logging.INFO)
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

    player_id = str(id(websocket))

    try:
        async with asyncio.timeout(GAME_JOIN_TIMEOUT):
            client = await manager.join(player_id=player_id)
    except asyncio.TimeoutError:
        logger.error("Timeout joining game")
        raise WebSocketException(status.WS_1013_TRY_AGAIN_LATER)

    logger.info("Player %s joined game %s", player_id, client.game.game_id)

    my_turn = client.am_i_white()

    while True:
        if my_turn:
            msg = await websocket.receive_json()
            try:
                move = messages.MoveRequest(**msg)
            except Exception:
                logger.error(f"Invalid message: {msg}")
                continue

            try:
                await client.make_move(move.uci)
            except GameOver:
                await websocket.send_json(messages.GameOverResponse())
                break
        else:
            try:
                uci = await client.wait_for_move()
            except GameOver:
                await websocket.send_json(messages.GameOverResponse())
                break
            finally:
                await websocket.send_json(messages.MoveRequest(uci=uci))

    await websocket.close(status.WS_1000_NORMAL_CLOSURE)


@router.get("/")
async def index(request: Request) -> Any:
    return templates.TemplateResponse("index.html", {"request": request})


def create_app() -> FastAPI:
    app = FastAPI(
        on_startup=[manager.start],
        on_shutdown=[manager.stop],
    )

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/img", StaticFiles(directory=STATIC_DIR / "img"))

    return app
