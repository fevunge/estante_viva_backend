"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "books": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel(
            [("category", ASCENDING), ("created_at", DESCENDING)],
            name="category_created",
        ),
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
    ],
    "notes": [
        IndexModel(
            [("user_id", ASCENDING), ("book_id", ASCENDING), ("page", ASCENDING)],
            name="user_book_page",
        ),
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("book_id", ASCENDING)], name="book"),
    ],
    "bookmarks": [
        IndexModel(
            [("user_id", ASCENDING), ("book_id", ASCENDING), ("page", ASCENDING)],
            name="user_book_page",
            unique=True,
        ),
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("book_id", ASCENDING)], name="book"),
    ],
    "reading_progress": [
        IndexModel(
            [("user_id", ASCENDING), ("book_id", ASCENDING)],
            name="user_book",
            unique=True,
        ),
        IndexModel(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated"
        ),
        IndexModel([("book_id", ASCENDING)], name="book"),
    ],
    "users": [IndexModel([("user_id", ASCENDING)], name="user_id", unique=True)],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except (
                Exception
            ) as exc:  # never block boot on an index; the log line names what to fix
                logger.error(
                    "ensure_indexes(%s.%s): %s", collection, model.document["name"], exc
                )
