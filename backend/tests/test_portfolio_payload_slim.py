"""
Portfolio payload slimming: attachment bytes must never ship in list/summary
endpoints. Blobs live in the `portfolio_files` collection; list items carry a
light `file_id` pointer + `has_file`, and bytes are fetched on demand via
GET /teacher/portfolio/file/{file_id} (owner-scoped).

Covers:
- upload stores the blob and returns file_id (no data URL in the response)
- evidence created with file_id links it; portfolio / sections / evidence list
  responses contain NO inline `data:` blobs
- legacy inline data-URL evidence (pre-migration shape) is stripped on read,
  flagged has_file, and still fetchable via the item-id fallback
- inline data-URL on create is relocated to portfolio_files transparently
- CV items relocate inline blobs; sections cv payload stays light
- file endpoint is owner-scoped (another teacher gets 404)
- deleting evidence / cv items cleans up the linked file document
- update replacing a file deletes the previous file document
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from server import app
from dependencies import db, create_access_token
from engines.sql_utils import gd_insert, gd_find_one

PNG_DATA_URL = "data:image/png;base64," + ("iVBORw0KGgoAAAANSUhEUg" * 40)
PDF_DATA_URL = "data:application/pdf;base64," + ("JVBERi0xLjUK" * 40)


def _auth(user_id: str, role: str, tenant_id: str) -> dict:
    tok = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {tok}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_teacher(tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": "teacher",
        "tenant_id": tenant_id,
        "email": f"{uid}@test.invalid",
        "full_name": "معلم اختبار",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as c:
        yield c


@pytest_asyncio.fixture
async def ctx():
    tid = str(uuid.uuid4())
    await _mk_school(tid)
    user = await _mk_teacher(tid)
    return {
        "user": user,
        "tenant": tid,
        "headers": _auth(user["id"], "teacher", tid),
    }


async def _create_evidence(http, ctx, **overrides):
    payload = {
        "evidence_type": "lesson_plan",
        "title_ar": "خطة درس تجريبية",
        **overrides,
    }
    res = await http.post("/teacher/portfolio/evidence", json=payload, headers=ctx["headers"])
    assert res.status_code == 200, res.text
    return res.json()


class TestUploadStoresBlobSeparately:

    @pytest.mark.asyncio
    async def test_upload_returns_file_id_not_data_url(self, http, ctx):
        res = await http.post(
            "/teacher/portfolio/upload",
            files={"file": ("plan.pdf", b"%PDF-1.5 test-bytes", "application/pdf")},
            headers=ctx["headers"],
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body.get("success") is True
        assert body.get("file_id"), body
        assert "data:" not in (body.get("file_url") or ""), "upload must not echo the blob"
        stored = await gd_find_one(db.session, "portfolio_files", {"id": body["file_id"]})
        assert stored is not None
        assert stored["teacher_id"] == ctx["user"]["id"]
        assert stored["data_url"].startswith("data:application/pdf;base64,")


class TestListPayloadsStayLight:

    @pytest.mark.asyncio
    async def test_inline_create_is_relocated_and_lists_ship_no_blobs(self, http, ctx):
        created = await _create_evidence(http, ctx, file_url=PNG_DATA_URL, file_name="صورة.png")
        ev = created["evidence"]
        assert ev.get("file_id"), "inline blob should be relocated to portfolio_files"
        assert not (ev.get("file_url") or "").startswith("data:")

        for path in ("/teacher/portfolio", "/teacher/portfolio/sections",
                     "/teacher/portfolio/evidence", "/teacher/portfolio/progress"):
            res = await http.get(path, headers=ctx["headers"])
            assert res.status_code == 200, f"{path}: {res.text[:200]}"
            assert "data:image/png;base64" not in res.text, f"{path} leaked inline blob"

        # The relocated blob is fetchable on demand.
        res = await http.get(f"/teacher/portfolio/file/{ev['file_id']}", headers=ctx["headers"])
        assert res.status_code == 200, res.text
        assert res.json()["file_url"] == PNG_DATA_URL

    @pytest.mark.asyncio
    async def test_legacy_inline_row_is_stripped_and_fetchable_by_item_id(self, http, ctx):
        # Pre-migration shape: blob still inline on the evidence document.
        legacy_id = str(uuid.uuid4())
        await gd_insert(db.session, "portfolio_evidence", {
            "id": legacy_id,
            "teacher_id": ctx["user"]["id"],
            "school_id": ctx["tenant"],
            "evidence_type": "lesson_plan",
            "section": "teaching_plans",
            "title_ar": "شاهد قديم",
            "source": "manual",
            "file_url": PDF_DATA_URL,
            "file_name": "قديم.pdf",
            "created_at": "2026-01-01T00:00:00+00:00",
        })

        res = await http.get("/teacher/portfolio", headers=ctx["headers"])
        assert res.status_code == 200
        assert "data:application/pdf;base64" not in res.text
        items = [i for sec in res.json()["sections"].values() for i in sec["items"]]
        legacy = next(i for i in items if i["id"] == legacy_id)
        assert legacy["has_file"] is True
        assert legacy["file_id"] == legacy_id  # item id doubles as fetch handle

        res = await http.get(f"/teacher/portfolio/file/{legacy_id}", headers=ctx["headers"])
        assert res.status_code == 200
        assert res.json()["file_url"] == PDF_DATA_URL

    @pytest.mark.asyncio
    async def test_external_links_pass_through_untouched(self, http, ctx):
        created = await _create_evidence(
            http, ctx, file_url="https://example.com/doc.pdf", file_name="رابط")
        ev = created["evidence"]
        assert ev.get("file_url") == "https://example.com/doc.pdf"
        assert not ev.get("file_id")


class TestFileEndpointAuthz:

    @pytest.mark.asyncio
    async def test_other_teacher_gets_404(self, http, ctx):
        created = await _create_evidence(http, ctx, file_url=PNG_DATA_URL)
        file_id = created["evidence"]["file_id"]

        other_tid = str(uuid.uuid4())
        await _mk_school(other_tid)
        other = await _mk_teacher(other_tid)
        res = await http.get(
            f"/teacher/portfolio/file/{file_id}",
            headers=_auth(other["id"], "teacher", other_tid),
        )
        assert res.status_code == 404, res.text

    @pytest.mark.asyncio
    async def test_foreign_file_id_rejected_on_create(self, http, ctx):
        other_tid = str(uuid.uuid4())
        await _mk_school(other_tid)
        other = await _mk_teacher(other_tid)
        up = await http.post(
            "/teacher/portfolio/upload",
            files={"file": ("x.pdf", b"%PDF-1.5", "application/pdf")},
            headers=_auth(other["id"], "teacher", other_tid),
        )
        foreign_file_id = up.json()["file_id"]

        res = await http.post(
            "/teacher/portfolio/evidence",
            json={"evidence_type": "lesson_plan", "title_ar": "سرقة ملف",
                  "file_id": foreign_file_id},
            headers=ctx["headers"],
        )
        assert res.status_code == 400, res.text


class TestFileLifecycle:

    @pytest.mark.asyncio
    async def test_delete_evidence_removes_file_doc(self, http, ctx):
        created = await _create_evidence(http, ctx, file_url=PNG_DATA_URL)
        ev = created["evidence"]
        res = await http.delete(f"/teacher/portfolio/evidence/{ev['id']}", headers=ctx["headers"])
        assert res.status_code == 200
        assert await gd_find_one(db.session, "portfolio_files", {"id": ev["file_id"]}) is None

    @pytest.mark.asyncio
    async def test_replacing_file_deletes_previous_blob(self, http, ctx):
        created = await _create_evidence(http, ctx, file_url=PNG_DATA_URL)
        ev = created["evidence"]
        old_file_id = ev["file_id"]

        up = await http.post(
            "/teacher/portfolio/upload",
            files={"file": ("new.pdf", b"%PDF-1.5 new", "application/pdf")},
            headers=ctx["headers"],
        )
        new_file_id = up.json()["file_id"]

        res = await http.put(
            f"/teacher/portfolio/evidence/{ev['id']}",
            json={"file_id": new_file_id, "file_name": "new.pdf"},
            headers=ctx["headers"],
        )
        assert res.status_code == 200, res.text
        assert res.json()["evidence"]["file_id"] == new_file_id
        assert await gd_find_one(db.session, "portfolio_files", {"id": old_file_id}) is None
        assert await gd_find_one(db.session, "portfolio_files", {"id": new_file_id}) is not None

    @pytest.mark.asyncio
    async def test_clearing_file_drops_pointer_and_blob(self, http, ctx):
        created = await _create_evidence(http, ctx, file_url=PNG_DATA_URL)
        ev = created["evidence"]
        res = await http.put(
            f"/teacher/portfolio/evidence/{ev['id']}",
            json={"file_url": None, "file_id": None, "file_name": None},
            headers=ctx["headers"],
        )
        assert res.status_code == 200, res.text
        updated = res.json()["evidence"]
        assert not updated.get("file_id")
        assert not updated.get("file_url")
        assert await gd_find_one(db.session, "portfolio_files", {"id": ev["file_id"]}) is None


class TestSharedFilePointerSafety:

    @pytest.mark.asyncio
    async def test_deleting_one_of_two_items_sharing_a_file_keeps_the_blob(self, http, ctx):
        """A file_id may be attached to several items (retry / double attach).
        Deleting one item must NOT delete the shared blob out from under the other."""
        up = await http.post(
            "/teacher/portfolio/upload",
            files={"file": ("shared.pdf", b"%PDF-1.5 shared-bytes", "application/pdf")},
            headers=ctx["headers"],
        )
        file_id = up.json()["file_id"]

        ev1 = (await _create_evidence(http, ctx, file_id=file_id))["evidence"]
        ev2 = (await _create_evidence(http, ctx, file_id=file_id, title_ar="شاهد ثانٍ"))["evidence"]

        res = await http.delete(f"/teacher/portfolio/evidence/{ev1['id']}", headers=ctx["headers"])
        assert res.status_code == 200, res.text

        # Blob must survive: the second item still points at it.
        res = await http.get(f"/teacher/portfolio/file/{file_id}", headers=ctx["headers"])
        assert res.status_code == 200, "shared blob was deleted while still referenced"

        # Deleting the last reference finally removes the blob.
        res = await http.delete(f"/teacher/portfolio/evidence/{ev2['id']}", headers=ctx["headers"])
        assert res.status_code == 200, res.text
        stored = await gd_find_one(db.session, "portfolio_files", {"id": file_id})
        assert stored is None, "unreferenced blob should be cleaned up"

    @pytest.mark.asyncio
    async def test_cv_item_sharing_a_file_with_evidence_keeps_the_blob(self, http, ctx):
        up = await http.post(
            "/teacher/portfolio/upload",
            files={"file": ("cert.pdf", b"%PDF-1.5 cert-bytes", "application/pdf")},
            headers=ctx["headers"],
        )
        file_id = up.json()["file_id"]

        ev = (await _create_evidence(http, ctx, file_id=file_id))["evidence"]
        res = await http.post("/teacher/portfolio/cv-item", json={
            "kind": "training_attended", "title": "دورة تدريبية", "file_id": file_id,
        }, headers=ctx["headers"])
        assert res.status_code == 200, res.text
        item_id = res.json()["item"]["id"]

        # Deleting the evidence row keeps the blob (cv_item still references it).
        res = await http.delete(f"/teacher/portfolio/evidence/{ev['id']}", headers=ctx["headers"])
        assert res.status_code == 200, res.text
        res = await http.get(f"/teacher/portfolio/file/{file_id}", headers=ctx["headers"])
        assert res.status_code == 200, "blob deleted while a cv_item still references it"

        # Deleting the cv_item (last reference) removes the blob.
        res = await http.delete(f"/teacher/portfolio/cv-item/{item_id}", headers=ctx["headers"])
        assert res.status_code == 200, res.text
        stored = await gd_find_one(db.session, "portfolio_files", {"id": file_id})
        assert stored is None


class TestMetaNoRecursiveData:

    @pytest.mark.asyncio
    async def test_repeated_meta_saves_never_nest_the_data_duplicate(self, http, ctx):
        """model_to_dict returns the raw JSONB under "data"; _save_meta must never
        write it back (historically snowballed one meta doc to 62 MB, depth 6)."""
        for text_val in ("مقدمة أولى", "مقدمة ثانية", "مقدمة ثالثة"):
            res = await http.put("/teacher/portfolio/intro", json={"text": text_val},
                                 headers=ctx["headers"])
            assert res.status_code == 200, res.text

        from sqlalchemy import text as sqltext
        row = (await db.session.execute(sqltext(
            "SELECT data ? 'data', pg_column_size(data) FROM generic_documents "
            "WHERE collection = 'teacher_portfolio_meta' AND data->>'teacher_id' = :t"),
            {"t": ctx["user"]["id"]})).one()
        assert row[0] is False, "meta doc must not contain the nested 'data' duplicate"
        assert row[1] < 10_000, f"meta doc unexpectedly large: {row[1]} bytes"


class TestCvItems:

    @pytest.mark.asyncio
    async def test_cv_item_inline_blob_relocated_and_sections_stay_light(self, http, ctx):
        res = await http.post(
            "/teacher/portfolio/cv-item",
            json={"kind": "training_attended", "title": "دورة تدريبية",
                  "file_url": PNG_DATA_URL, "file_name": "شهادة.png"},
            headers=ctx["headers"],
        )
        assert res.status_code == 200, res.text
        item = res.json()["item"]
        assert item.get("file_id"), "cv blob should be relocated"
        assert not (item.get("file_url") or "").startswith("data:")

        secs = await http.get("/teacher/portfolio/sections", headers=ctx["headers"])
        assert secs.status_code == 200
        assert "data:image/png;base64" not in secs.text
        cv_items = secs.json()["cv"]["training_attended"]
        mine = next(i for i in cv_items if i["id"] == item["id"])
        assert mine["has_file"] is True

        # On-demand fetch + delete cleans the blob up.
        f = await http.get(f"/teacher/portfolio/file/{item['file_id']}", headers=ctx["headers"])
        assert f.status_code == 200
        assert f.json()["file_url"] == PNG_DATA_URL

        d = await http.delete(f"/teacher/portfolio/cv-item/{item['id']}", headers=ctx["headers"])
        assert d.status_code == 200
        assert await gd_find_one(db.session, "portfolio_files", {"id": item["file_id"]}) is None
