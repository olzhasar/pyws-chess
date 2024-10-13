# pyws-chess

A simple online chess game.

Built with FastAPI and websockets.

![Preview](./preview.png)

## Usage

### Docker

```bash
docker build -t pyws-chess .
docker run -p 8000:8000 pyws-chess
```

### Local installation

#### Pre-requisites

- [uv](https://github.com/astral-sh/uv)
- Python 3.11+

```bash
cd src
uv run uvicorn app.main:app
```

The server will be running on `http://localhost:8000`.

## License

MIT
