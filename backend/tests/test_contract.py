"""The backend must match docs/openapi.yaml: same routes, methods and success codes."""
from pathlib import Path

import yaml

CONTRACT = yaml.safe_load((Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml").read_text())
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def operations(spec: dict) -> dict:
    """{("GET", "/tickets"): 200, ...}: every operation and its success code."""
    ops = {}
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method in HTTP_METHODS:
                success = [int(code) for code in op["responses"] if str(code).startswith("2")]
                ops[(method.upper(), path)] = success[0]
    return ops


def contract_operations() -> dict:
    return operations(CONTRACT)


def app_operations(app) -> dict:
    # FastAPI generates a spec from the actual code; compare that to ours.
    return operations(app.openapi())


def test_routes_and_methods_match_contract(client):
    contract, app = contract_operations(), app_operations(client.app)
    assert set(app) - set(contract) == set(), "routes in the app but missing from the contract"
    assert set(contract) - set(app) == set(), "routes in the contract but missing from the app"


def test_success_status_codes_match_contract(client):
    contract, app = contract_operations(), app_operations(client.app)
    mismatched = {op: (app[op], contract[op]) for op in contract if app.get(op) != contract[op]}
    assert mismatched == {}


def test_error_codes_in_contract_match_backend():
    from app.errors import _HTTP_CODES
    allowed = set(CONTRACT["components"]["schemas"]["Error"]["properties"]["error"]["properties"]["code"]["enum"])
    used = {code for code, _ in _HTTP_CODES.values()} | {"validation_error", "conflict", "internal_error"}
    assert used <= allowed
