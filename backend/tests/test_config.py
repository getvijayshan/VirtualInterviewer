from app.config import Settings


def test_bare_postgresql_url_is_pinned_to_psycopg2():
    s = Settings(database_url="postgresql://u:p@localhost:5432/db")
    assert s.database_url == "postgresql+psycopg2://u:p@localhost:5432/db"


def test_explicit_driver_is_left_alone():
    s = Settings(database_url="postgresql+psycopg2://u:p@localhost:5432/db")
    assert s.database_url == "postgresql+psycopg2://u:p@localhost:5432/db"
