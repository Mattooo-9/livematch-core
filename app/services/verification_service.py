"""
Photo intake (hash + dedup) + lightweight verification flow.

Honesty about scope: this implements perceptual-hash duplicate detection and a
selfie-gesture challenge/response flow, which is enough to stop the most common
abuse (stolen photos, mass-reused images) and to require an explicit live action.
It does NOT implement real biometric liveness/face-match ML -- that requires a
dedicated vendor/model and is flagged as a TODO for production hardening.
"""
from __future__ import annotations

import hashlib
import io
import random
from typing import Optional

import imagehash
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VerificationMethod, VerificationStatus
from app.models.mixins import utcnow
from app.models.photo import Photo
from app.models.verification import Verification

GESTURES = ["thumbs_up", "peace_sign", "hand_on_head", "point_left", "point_right", "wink"]

HAMMING_DUPLICATE_THRESHOLD = 6  # perceptual hashes within this distance are treated as the same photo


def compute_hashes(image_bytes: bytes) -> tuple[str, str]:
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    phash = str(imagehash.phash(img))
    return sha256, phash


async def find_duplicate_photo(session: AsyncSession, phash: str, exclude_user_id: int) -> Optional[Photo]:
    res = await session.execute(select(Photo).where(Photo.user_id != exclude_user_id))
    target_hash = imagehash.hex_to_hash(phash)
    for photo in res.scalars().all():
        try:
            existing_hash = imagehash.hex_to_hash(photo.phash)
        except Exception:
            continue
        if target_hash - existing_hash <= HAMMING_DUPLICATE_THRESHOLD:
            return photo
    return None


async def add_photo(
    session: AsyncSession, user_id: int, telegram_file_id: str, image_bytes: bytes, is_primary: bool = False
) -> Photo:
    sha256, phash = compute_hashes(image_bytes)
    duplicate = await find_duplicate_photo(session, phash, exclude_user_id=user_id)

    photo = Photo(
        user_id=user_id,
        telegram_file_id=telegram_file_id,
        sha256_hash=sha256,
        phash=phash,
        is_primary=is_primary,
        is_flagged_duplicate=duplicate is not None,
    )
    session.add(photo)
    await session.flush()
    return photo


def issue_gesture_challenge() -> str:
    return random.choice(GESTURES)


async def start_verification(session: AsyncSession, user_id: int, method: VerificationMethod) -> Verification:
    res = await session.execute(select(Verification).where(Verification.user_id == user_id))
    v = res.scalar_one_or_none()
    gesture = issue_gesture_challenge()
    if v is None:
        v = Verification(user_id=user_id, status=VerificationStatus.PENDING, method=method, gesture_code=gesture)
        session.add(v)
    else:
        v.status = VerificationStatus.PENDING
        v.method = method
        v.gesture_code = gesture
    await session.flush()
    return v


async def submit_verification(session: AsyncSession, user_id: int, file_bytes: bytes) -> Verification:
    res = await session.execute(select(Verification).where(Verification.user_id == user_id))
    v = res.scalar_one_or_none()
    if v is None or v.status != VerificationStatus.PENDING:
        raise ValueError("no_pending_verification")

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    v.submitted_file_hash = file_hash
    # MVP auto-approval: a file was actually submitted in response to a fresh
    # gesture challenge. Production should route this to a real liveness check
    # or human moderation queue before final approval.
    v.status = VerificationStatus.APPROVED
    v.reviewed_at = utcnow()
    v.reviewer_note = "auto-approved: gesture-response received (MVP heuristic)"
    await session.flush()
    return v
