"""Signed-in reader features: per-page notes, bookmarks and reading progress (all scoped to the caller)."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from lib.admin import current_member
from lib.db import db
from models.books import Me
from models.library import (
    Bookmark,
    BookmarkCreate,
    Note,
    NoteCreate,
    NoteUpdate,
    Progress,
    ProgressUpdate,
    RecentBook,
)
from routers.books import _get_doc, _to_book

router = APIRouter(prefix="/me")


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("", response_model=Me)
async def me(member: dict = Depends(current_member)):
    return Me(
        user_id=member["user_id"],
        email=member.get("email"),
        is_admin=member["role"] == "admin",
    )


# ---------- notes ----------


@router.get("/books/{book_id}/notes", response_model=list[Note])
async def list_notes(book_id: str, member: dict = Depends(current_member)):
    docs = (
        await db.notes.find(
            {"user_id": member["user_id"], "book_id": book_id}, {"_id": 0}
        )
        .sort([("page", 1), ("created_at", 1)])
        .to_list(2000)
    )
    return [
        Note(
            **{
                **d,
                "created_at": _utc(d["created_at"]),
                "updated_at": _utc(d["updated_at"]),
            }
        )
        for d in docs
    ]


@router.post("/books/{book_id}/notes", response_model=Note, status_code=201)
async def create_note(
    book_id: str, body: NoteCreate, member: dict = Depends(current_member)
):
    await _get_doc(book_id)
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": member["user_id"],
        "book_id": book_id,
        "page": body.page,
        "text": body.text.strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.notes.insert_one(doc)
    return Note(**doc)


@router.put("/notes/{note_id}", response_model=Note)
async def update_note(
    note_id: str, body: NoteUpdate, member: dict = Depends(current_member)
):
    doc = await db.notes.find_one_and_update(
        {"id": note_id, "user_id": member["user_id"]},
        {"$set": {"text": body.text.strip(), "updated_at": datetime.now(timezone.utc)}},
        projection={"_id": 0},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Anotação não encontrada")
    return Note(
        **{
            **doc,
            "created_at": _utc(doc["created_at"]),
            "updated_at": _utc(doc["updated_at"]),
        }
    )


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: str, member: dict = Depends(current_member)):
    if (
        await db.notes.delete_one({"id": note_id, "user_id": member["user_id"]})
    ).deleted_count == 0:
        raise HTTPException(status_code=404, detail="Anotação não encontrada")
    return Response(status_code=204)


# ---------- bookmarks ----------


@router.get("/books/{book_id}/bookmarks", response_model=list[Bookmark])
async def list_bookmarks(book_id: str, member: dict = Depends(current_member)):
    docs = (
        await db.bookmarks.find(
            {"user_id": member["user_id"], "book_id": book_id}, {"_id": 0}
        )
        .sort("page", 1)
        .to_list(1000)
    )
    return [Bookmark(**{**d, "created_at": _utc(d["created_at"])}) for d in docs]


@router.post("/books/{book_id}/bookmarks", response_model=Bookmark, status_code=201)
async def create_bookmark(
    book_id: str, body: BookmarkCreate, member: dict = Depends(current_member)
):
    await _get_doc(book_id)
    existing = await db.bookmarks.find_one(
        {"user_id": member["user_id"], "book_id": book_id, "page": body.page},
        {"_id": 0},
    )
    if existing:
        return Bookmark(**{**existing, "created_at": _utc(existing["created_at"])})
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": member["user_id"],
        "book_id": book_id,
        "page": body.page,
        "label": body.label.strip(),
        "created_at": datetime.now(timezone.utc),
    }
    await db.bookmarks.insert_one(doc)
    return Bookmark(**doc)


@router.delete("/bookmarks/{bookmark_id}", status_code=204)
async def delete_bookmark(bookmark_id: str, member: dict = Depends(current_member)):
    if (
        await db.bookmarks.delete_one({"id": bookmark_id, "user_id": member["user_id"]})
    ).deleted_count == 0:
        raise HTTPException(status_code=404, detail="Marcador não encontrado")
    return Response(status_code=204)


# ---------- reading progress ----------


@router.get("/progress/{book_id}", response_model=Progress | None)
async def get_progress(book_id: str, member: dict = Depends(current_member)):
    doc = await db.reading_progress.find_one(
        {"user_id": member["user_id"], "book_id": book_id}, {"_id": 0}
    )
    return Progress(**{**doc, "updated_at": _utc(doc["updated_at"])}) if doc else None


@router.put("/progress/{book_id}", response_model=Progress)
async def save_progress(
    book_id: str, body: ProgressUpdate, member: dict = Depends(current_member)
):
    await _get_doc(book_id)
    now = datetime.now(timezone.utc)
    page = min(body.page, body.total_pages)
    await db.reading_progress.update_one(
        {"user_id": member["user_id"], "book_id": book_id},
        {"$set": {"page": page, "total_pages": body.total_pages, "updated_at": now}},
        upsert=True,
    )
    return Progress(
        book_id=book_id, page=page, total_pages=body.total_pages, updated_at=now
    )


@router.get("/recent", response_model=list[RecentBook])
async def recent(member: dict = Depends(current_member)):
    rows = (
        await db.reading_progress.find({"user_id": member["user_id"]}, {"_id": 0})
        .sort("updated_at", -1)
        .to_list(12)
    )
    if not rows:
        return []
    books = {
        b["id"]: b
        async for b in db.books.find(
            {"id": {"$in": [r["book_id"] for r in rows]}}, {"_id": 0}
        )
    }
    return [
        RecentBook(
            book=_to_book(books[r["book_id"]]),
            page=r["page"],
            total_pages=r["total_pages"],
            updated_at=_utc(r["updated_at"]),
        )
        for r in rows
        if r["book_id"] in books
    ]
