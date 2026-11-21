import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.security import AuthMiddleware, require_role
from app.domain.roles import Role
from app.services.authorization import AuthorizedUser, Authorizer
from app.services.ports import AllowlistRecord, Identity


class FakeRepo:
    def __init__(self, records: dict[str, Role]) -> None:
        self.records = records
        self.calls: list[str] = []

    def find_active(self, identifier: str) -> AllowlistRecord | None:
        self.calls.append(identifier)
        role = self.records.get(identifier)
        return AllowlistRecord(identifier, role) if role else None


class FakeIdentity:
    def __init__(self, identity: Identity | None) -> None:
        self.identity = identity

    def resolve(self, headers: dict[str, str]) -> Identity | None:
        return self.identity


def build(identity: Identity | None, repo: FakeRepo, key: str = "email") -> TestClient:
    app = FastAPI()
    app.add_middleware(
        AuthMiddleware,
        identity=FakeIdentity(identity),
        authorizer=Authorizer(repo, key),  # type: ignore[arg-type]
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me")
    def me(user: AuthorizedUser = Depends(require_role("administrator", "global_manager"))):  # type: ignore[no-untyped-def]  # noqa: B008
        return {"role": user.role}

    @app.get("/admin")
    def admin(user: AuthorizedUser = Depends(require_role("administrator"))):  # type: ignore[no-untyped-def]  # noqa: B008
        return {"role": user.role}

    return TestClient(app)


def test_missing_identity_is_401_without_any_allowlist_query() -> None:  # BASE-12
    repo = FakeRepo({"ana@example.test": "administrator"})
    client = build(None, repo)
    assert client.get("/me").status_code == 401
    assert repo.calls == []


def test_authenticated_but_not_allowlisted_is_denied() -> None:  # BASE-02
    repo = FakeRepo({"ana@example.test": "administrator"})
    client = build(Identity(email="intruder@example.test"), repo)
    assert client.get("/me").status_code == 403
    assert repo.calls == ["intruder@example.test"]


def test_allowlisted_user_is_allowed() -> None:
    client = build(
        Identity(email="ana@example.test"), FakeRepo({"ana@example.test": "administrator"})
    )
    r = client.get("/me")
    assert r.status_code == 200 and r.json() == {"role": "administrator"}


def test_role_without_permission_is_denied() -> None:
    client = build(Identity(email="g@example.test"), FakeRepo({"g@example.test": "global_manager"}))
    assert client.get("/me").status_code == 200
    assert client.get("/admin").status_code == 403


def test_health_endpoints_are_public() -> None:
    repo = FakeRepo({})
    assert build(None, repo).get("/healthz").status_code == 200
    assert repo.calls == []


def test_unknown_routes_are_not_reachable_anonymously() -> None:
    assert build(None, FakeRepo({})).get("/anything-else").status_code == 401


def test_dev_preauthorized_role_skips_the_allowlist() -> None:
    repo = FakeRepo({})
    client = build(Identity(email="d@x.test", preauthorized_role="global_manager"), repo)
    assert client.get("/me").json() == {"role": "global_manager"}
    assert client.get("/admin").status_code == 403
    assert repo.calls == []


@pytest.mark.parametrize(
    ("key", "identity", "stored"),
    [
        ("sub", Identity(subject="g-1", email="other@x.test"), "g-1"),
        ("email", Identity(subject="g-1", email="ana@x.test"), "ana@x.test"),
    ],
)
def test_allowlist_works_with_either_identifier_kind(
    key: str, identity: Identity, stored: str
) -> None:
    repo = FakeRepo({stored: "administrator"})
    assert Authorizer(repo, key).authorize(identity) is not None  # type: ignore[arg-type]


def test_identifier_kind_must_match_the_configured_one() -> None:
    repo = FakeRepo({"ana@x.test": "administrator"})
    by_sub = Authorizer(repo, "sub")  # type: ignore[arg-type]
    assert by_sub.authorize(Identity(subject="g-1", email="ana@x.test")) is None


def test_unset_identifier_kind_denies() -> None:
    repo = FakeRepo({"ana@x.test": "administrator"})
    assert Authorizer(repo, None).authorize(Identity(email="ana@x.test")) is None
    assert repo.calls == []


def test_forged_identity_that_is_not_allowlisted_is_denied() -> None:  # BASE-04
    repo = FakeRepo({"admin@x.test": "administrator"})
    client = build(Identity(email="admin@x.test.evil.example"), repo)
    assert client.get("/admin").status_code == 403
