"""Books: public catalog + PDF/cover streaming, and admin CRUD (PDFs stored in GridFS)."""

import re
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from starlette.concurrency import run_in_threadpool

from lib.admin import require_admin
from lib.db import db
from lib.pdf import count_pages, render_cover
from models.books import AdminStats, Book

router = APIRouter()
fs = AsyncIOMotorGridFSBucket(db, bucket_name="files")

PALETTE = ["#585b70", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7", "#94e2d5"]
MAX_PDF_BYTES = 80 * 1024 * 1024


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_book(doc: dict) -> Book:
    return Book(
        **{
            k: doc.get(k)
            for k in Book.model_fields
            if k not in ("has_cover", "created_at", "updated_at")
        },
        has_cover=bool(doc.get("cover_file_id")),
        created_at=_aware(doc["created_at"]),
        updated_at=_aware(doc["updated_at"]),
    )


async def _get_doc(book_id: str) -> dict:
    doc = await db.books.find_one({"id": book_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    return doc


async def _delete_file(file_id: str | None) -> None:
    if file_id:
        try:
            await fs.delete(ObjectId(file_id))
        except Exception:
            pass


async def _store_pdf(book_id: str, data: bytes) -> dict:
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="O arquivo enviado não é um PDF válido"
        )
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF maior que 80 MB")
    try:
        page_count = await run_in_threadpool(count_pages, data)
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ler este PDF")
    file_id = await fs.upload_from_stream(
        f"{book_id}.pdf", data, metadata={"contentType": "application/pdf"}
    )
    return {
        "pdf_file_id": str(file_id),
        "page_count": page_count,
        "size_bytes": len(data),
    }


async def _store_cover(book_id: str, data: bytes, content_type: str) -> str:
    fid = await fs.upload_from_stream(
        f"{book_id}-cover", data, metadata={"contentType": content_type}
    )
    return str(fid)


async def _stream_file(file_id: str, media_type: str, filename: str | None = None):
    try:
        grid_out = await fs.open_download_stream(ObjectId(file_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    async def chunks():
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            yield chunk

    headers = {
        "Cache-Control": "public, max-age=3600",
        "Content-Length": str(grid_out.length),
    }
    if filename:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return StreamingResponse(chunks(), media_type=media_type, headers=headers)


# ---------- public ----------


@router.get("/books", response_model=list[Book])
async def list_books(q: str | None = None, category: str | None = None):
    query: dict = {}
    if category:
        query["category"] = category
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"author": rx}, {"description": rx}]
    docs = await db.books.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_to_book(d) for d in docs]


@router.get("/books/categories", response_model=list[str])
async def list_categories():
    cats = await db.books.distinct("category")
    return sorted(c for c in cats if c)


@router.get("/books/{book_id}", response_model=Book)
async def get_book(book_id: str):
    return _to_book(await _get_doc(book_id))


@router.get("/books/{book_id}/pdf")
async def get_pdf(book_id: str):
    doc = await _get_doc(book_id)
    return await _stream_file(doc["pdf_file_id"], "application/pdf", f"{book_id}.pdf")


@router.get("/books/{book_id}/cover")
async def get_cover(book_id: str):
    doc = await _get_doc(book_id)
    if not doc.get("cover_file_id"):
        raise HTTPException(status_code=404, detail="Sem capa")
    return await _stream_file(doc["cover_file_id"], doc.get("cover_type", "image/jpeg"))


# ---------- admin ----------


@router.get("/admin/stats", response_model=AdminStats)
async def admin_stats(_: dict = Depends(require_admin)):
    pages = await db.books.aggregate(
        [{"$group": {"_id": None, "n": {"$sum": "$page_count"}}}]
    ).to_list(1)
    return AdminStats(
        total_books=await db.books.count_documents({}),
        total_categories=len([c for c in await db.books.distinct("category") if c]),
        total_pages=pages[0]["n"] if pages else 0,
    )


def _clean(v: str | None, field: str, required: bool = True, max_len: int = 300) -> str:
    v = (v or "").strip()
    if required and not v:
        raise HTTPException(status_code=422, detail=f"Campo obrigatório: {field}")
    return v[:max_len]


async def _cover_from_upload(
    book_id: str, cover: UploadFile | None
) -> tuple[str, str] | None:
    if cover is None or not cover.filename:
        return None
    ctype = cover.content_type or ""
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="A capa deve ser uma imagem")
    data = await cover.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Imagem de capa maior que 8 MB")
    return await _store_cover(book_id, data, ctype), ctype


@router.post("/admin/books", response_model=Book, status_code=201)
async def create_book(
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    category: str = Form("Geral"),
    color: str = Form(""),
    pdf: UploadFile = File(...),
    cover: UploadFile | None = File(None),
    _: dict = Depends(require_admin),
):
    book_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    pdf_info = await _store_pdf(book_id, await pdf.read())
    cover_info = await _cover_from_upload(book_id, cover)
    if cover_info is None:
        rendered = await run_in_threadpool(
            render_cover, await _read_file(pdf_info["pdf_file_id"])
        )
        if rendered:
            cover_info = (
                await _store_cover(book_id, rendered, "image/jpeg"),
                "image/jpeg",
            )
    count = await db.books.count_documents({})
    doc = {
        "id": book_id,
        "title": _clean(title, "título"),
        "author": _clean(author, "autor"),
        "description": _clean(description, "descrição", required=False, max_len=3000),
        "category": _clean(category, "categoria", required=False, max_len=60)
        or "Geral",
        "color": color if color in PALETTE else PALETTE[count % len(PALETTE)],
        **pdf_info,
        "cover_file_id": cover_info[0] if cover_info else None,
        "cover_type": cover_info[1] if cover_info else None,
        "created_at": now,
        "updated_at": now,
    }
    await db.books.insert_one(doc)
    return _to_book(doc)


async def _read_file(file_id: str) -> bytes:
    stream = await fs.open_download_stream(ObjectId(file_id))
    return await stream.read()


@router.put("/admin/books/{book_id}", response_model=Book)
async def update_book(
    book_id: str,
    title: str = Form(...),
    author: str = Form(...),
    description: str = Form(""),
    category: str = Form("Geral"),
    color: str = Form(""),
    remove_cover: bool = Form(False),
    pdf: UploadFile | None = File(None),
    cover: UploadFile | None = File(None),
    _: dict = Depends(require_admin),
):
    doc = await _get_doc(book_id)
    update: dict = {
        "title": _clean(title, "título"),
        "author": _clean(author, "autor"),
        "description": _clean(description, "descrição", required=False, max_len=3000),
        "category": _clean(category, "categoria", required=False, max_len=60)
        or "Geral",
        "updated_at": datetime.now(timezone.utc),
    }
    if color in PALETTE:
        update["color"] = color
    if pdf is not None and pdf.filename:
        update.update(await _store_pdf(book_id, await pdf.read()))
        await _delete_file(doc.get("pdf_file_id"))
    cover_info = await _cover_from_upload(book_id, cover)
    if cover_info:
        await _delete_file(doc.get("cover_file_id"))
        update["cover_file_id"], update["cover_type"] = cover_info
    elif remove_cover:
        await _delete_file(doc.get("cover_file_id"))
        update["cover_file_id"], update["cover_type"] = None, None
    await db.books.update_one({"id": book_id}, {"$set": update})
    return _to_book(await _get_doc(book_id))


@router.delete("/admin/books/{book_id}", status_code=204)
async def delete_book(book_id: str, _: dict = Depends(require_admin)):
    doc = await _get_doc(book_id)
    await _delete_file(doc.get("pdf_file_id"))
    await _delete_file(doc.get("cover_file_id"))
    for coll in (
        db.notes,
        db.bookmarks,
        db.reading_progress,
    ):  # readers' data tied to this book only
        await coll.delete_many({"book_id": book_id})
    await db.books.delete_one({"id": book_id})
    return Response(status_code=204)
