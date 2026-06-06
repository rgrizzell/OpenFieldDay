from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("OFD_HOST", "0.0.0.0")
    port = int(os.environ.get("OFD_PORT", "8000"))
    config_path = os.environ.get("OFD_CONFIG", "config.yaml")

    from .app import create_app

    uvicorn.run(create_app(config_path=config_path), host=host, port=port)


if __name__ == "__main__":
    main()
