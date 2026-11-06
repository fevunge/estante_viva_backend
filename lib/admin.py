"""Admin gate: only verified emails listed in ADMIN_EMAIL become admin (decided at first sign-in)."""

import os

import requests
from fastapi import Depends, HTTPException
from pymongo import ReturnDocument
from starlette.concurrency import run_in_threadpool

from clerk_auth import require_user
from lib.db import db

ENV = (
    "live"
    if os.environ.get("CLERK_PUBLISHABLE_KEY", "").startswith("pk_live_")
    else "preview"
)


def _verified_admin_email(user_id: str) -> str | None:
    admins = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAIL", "").split(",")
        if e.strip()
    }
    r = requests.get(
        f"https://api.clerk.com/v1/users/{user_id}",
        timeout=10,
        headers={
            "Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}",
            "User-Agent": "emergent-app",
        },
    )
    r.raise_for_status()
    for e in r.json()["email_addresses"]:
        if (
            e["email_address"].lower() in admins
            and (e.get("verification") or {}).get("status") == "verified"
        ):
            return e["email_address"].lower()
    return None


async def current_member(user: dict = Depends(require_user)) -> dict:
    uid = user["user_id"]
    member = await db.users.find_one({"user_id": uid}, {"_id": 0})
    if member is None or not member.get("role"):
        email = await run_in_threadpool(_verified_admin_email, uid)
        role = "admin" if email else "member"
        await db.users.update_one(
            {"user_id": uid, "role": {"$in": [None, ""]}}, {"$set": {"role": role}}
        )
        member = await db.users.find_one_and_update(
            {"user_id": uid},
            {"$setOnInsert": {"user_id": uid, "role": role, "email": email}},
            upsert=True,
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
    if member.get("env") != ENV:
        await db.users.update_one({"user_id": uid}, {"$set": {"env": ENV}})
    return {
        **member,
        "env": ENV,
        "role": member["role"] if member["role"] in ("admin", "member") else "member",
    }


async def require_admin(member: dict = Depends(current_member)) -> dict:
    if member["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return member
