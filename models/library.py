from datetime import datetime

from pydantic import BaseModel, Field

from models.books import Book


class Note(BaseModel):
    id: str
    book_id: str
    page: int
    text: str
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    page: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=5000)


class NoteUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class Bookmark(BaseModel):
    id: str
    book_id: str
    page: int
    label: str = ""
    created_at: datetime


class BookmarkCreate(BaseModel):
    page: int = Field(ge=1)
    label: str = Field(default="", max_length=120)


class ProgressUpdate(BaseModel):
    page: int = Field(ge=1)
    total_pages: int = Field(ge=1)


class Progress(BaseModel):
    book_id: str
    page: int
    total_pages: int
    updated_at: datetime


class RecentBook(BaseModel):
    book: Book
    page: int
    total_pages: int
    updated_at: datetime
