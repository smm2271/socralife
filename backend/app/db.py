from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

def database(url):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url: options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(conn, _): conn.execute("PRAGMA foreign_keys=ON")
    return engine, sessionmaker(engine, expire_on_commit=False)
