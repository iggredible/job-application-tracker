from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_session
from app.main import app


def test_health_returns_ok_and_confirms_database(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_unreachable() -> None:
    # Nothing listens on port 1, so the connection check must fail.
    engine = create_engine(
        "postgresql+psycopg://localhost:1/none", connect_args={"connect_timeout": 1}
    )
    factory = sessionmaker(bind=engine)

    def broken_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/health")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

    assert response.status_code == 503
    assert response.json() != {"status": "ok"}
