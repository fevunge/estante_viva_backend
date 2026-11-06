"""Supabase Storage (REST) para PDFs e capas.

O bucket é privado: o backend faz upload/download com a service key e continua
servindo `/api/books/{id}/pdf` e `/cover` publicamente (contrato do SPEC).
"""

import logging
import os
from urllib.parse import quote

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=300.0, pool=10.0)


def _settings() -> tuple[str, str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    bucket = os.environ.get("SUPABASE_BUCKET", "books")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase Storage não configurado")
    return url, key, bucket


def _object_url(url: str, bucket: str, path: str) -> str:
    return f"{url}/storage/v1/object/{bucket}/{quote(path, safe='/')}"


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


async def upload(path: str, data: bytes, content_type: str) -> None:
    """Cria/sobrescreve um objeto no bucket."""
    url, key, bucket = _settings()
    headers = {**_auth(key), "Content-Type": content_type, "x-upsert": "true"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                _object_url(url, bucket, path), content=data, headers=headers
            )
    except httpx.HTTPError as exc:
        logger.error("supabase upload %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="Falha ao enviar arquivo ao storage")
    if r.status_code not in (200, 201):
        logger.error(
            "supabase upload %s: %s %s", path, r.status_code, r.text[:300]
        )
        raise HTTPException(status_code=502, detail="Falha ao enviar arquivo ao storage")


async def delete(path: str | None) -> None:
    """Remove um objeto; ausência não é erro (idempotente)."""
    if not path:
        return
    url, key, bucket = _settings()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.delete(
                _object_url(url, bucket, path), headers=_auth(key)
            )
        if r.status_code not in (200, 204, 404):
            logger.warning(
                "supabase delete %s: %s %s", path, r.status_code, r.text[:300]
            )
    except httpx.HTTPError as exc:
        logger.warning("supabase delete %s: %s", path, exc)


class StorageObject:
    """Download em streaming; quem chama itera e sempre fecha (`aclose`)."""

    def __init__(self, response: httpx.Response, client: httpx.AsyncClient):
        self._response = response
        self._client = client

    async def aiter_bytes(self):
        async for chunk in self._response.aiter_bytes():
            yield chunk

    async def aclose(self) -> None:
        await self._response.aclose()
        await self._client.aclose()


async def open_object(path: str) -> StorageObject:
    """Abre o objeto para streaming, validando o status antes dos headers."""
    url, key, bucket = _settings()
    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        request = client.build_request(
            "GET", _object_url(url, bucket, path), headers=_auth(key)
        )
        response = await client.send(request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.error("supabase download %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="Falha ao acessar o storage")

    if response.status_code == 404:
        await response.aclose()
        await client.aclose()
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if response.status_code != 200:
        body = (await response.aread())[:300]
        await response.aclose()
        await client.aclose()
        logger.error("supabase download %s: %s %s", path, response.status_code, body)
        raise HTTPException(status_code=502, detail="Falha ao acessar o storage")
    return StorageObject(response, client)
