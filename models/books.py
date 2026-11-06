from datetime import datetime

from pydantic import BaseModel


class Book(BaseModel):
    id: str
    title: str
    author: str
    description: str = ""
    category: str = "Geral"
    color: str = "#89b4fa"
    has_cover: bool = False
    page_count: int = 0
    size_bytes: int = 0
    created_at: datetime
    updated_at: datetime


class AdminStats(BaseModel):
    total_books: int
    total_categories: int
    total_pages: int


class Me(BaseModel):
    user_id: str
    email: str | None = None
    is_admin: bool
