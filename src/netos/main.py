"""Console entry point for the local API."""

from netos.api.app import create_app
from netos.config import Settings


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    main()
