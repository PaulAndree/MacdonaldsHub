"""The comparison itself: it must notice what clients depend on and ignore wording."""

import copy

from tests.contract.compare import canon, differences

APPROVED = {
    "openapi": "3.1.0",
    "paths": {
        "/api/session": {
            "get": {
                "operationId": "getSession",
                "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/S"}}
                        },
                    },
                    "401": {"description": "no"},
                },
            }
        }
    },
    "components": {
        "schemas": {
            "S": {
                "type": "object",
                "required": ["a", "b"],
                "properties": {
                    "a": {"type": "string", "description": "words"},
                    "b": {"type": ["string", "null"]},
                },
            }
        }
    },
}


def generated() -> dict:  # type: ignore[type-arg]
    return copy.deepcopy(APPROVED)


def check(spec: dict) -> list[str]:  # type: ignore[type-arg]
    return differences(APPROVED, spec, {"getSession"})


def test_an_identical_document_matches() -> None:
    assert check(generated()) == []


def test_wording_and_examples_are_ignored() -> None:
    spec = generated()
    spec["components"]["schemas"]["S"]["properties"]["a"]["description"] = "other words"
    spec["components"]["schemas"]["S"]["properties"]["a"]["title"] = "A"
    assert check(spec) == []


def test_a_field_added_by_hand_is_noticed() -> None:
    spec = generated()
    spec["components"]["schemas"]["S"]["properties"]["extra"] = {"type": "string"}
    assert check(spec) == ["getSession: response 200 differs"]


def test_a_changed_type_is_noticed() -> None:
    spec = generated()
    spec["components"]["schemas"]["S"]["properties"]["a"]["type"] = "integer"
    assert check(spec) == ["getSession: response 200 differs"]


def test_a_field_that_stops_being_required_is_noticed() -> None:
    spec = generated()
    spec["components"]["schemas"]["S"]["required"] = ["a"]
    assert check(spec) == ["getSession: response 200 differs"]


def test_a_missing_status_code_is_noticed() -> None:
    spec = generated()
    del spec["paths"]["/api/session"]["get"]["responses"]["401"]
    assert "status codes" in check(spec)[0]


def test_a_changed_parameter_is_noticed() -> None:
    spec = generated()
    spec["paths"]["/api/session"]["get"]["parameters"][0]["required"] = True
    assert "parameters differ" in check(spec)[0]


def test_an_operation_that_is_not_served_is_noticed() -> None:
    spec = generated()
    del spec["paths"]["/api/session"]
    assert check(spec) == ["getSession: is not served by the API"]


def test_a_moved_operation_is_noticed() -> None:
    spec = generated()
    spec["paths"]["/api/me"] = spec["paths"].pop("/api/session")
    assert "instead of GET /api/session" in check(spec)[0]


def test_nullable_is_the_same_whichever_way_it_is_written() -> None:
    doc: dict = {}  # type: ignore[type-arg]
    a = canon({"type": ["string", "null"]}, doc)
    b = canon({"anyOf": [{"type": "string"}, {"type": "null"}]}, doc)
    assert a == b


def test_a_reference_equals_its_inline_schema() -> None:
    doc = {
        "components": {
            "schemas": {"X": {"type": "object", "properties": {"k": {"type": "string"}}}}
        }
    }
    inline = {"type": "object", "properties": {"k": {"type": "string"}}}
    assert canon({"$ref": "#/components/schemas/X"}, doc) == canon(inline, {})
