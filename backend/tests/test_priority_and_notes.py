"""Priority, first-response deadlines (SLA) and staff-only internal notes."""
from datetime import datetime, timedelta


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_ticket(admin_conn, ticket_id: str, hours: int) -> None:
    """Pretend the ticket was opened `hours` ago."""
    admin_conn.execute(
        "UPDATE support_tickets SET created_at = now() - make_interval(hours => %s), updated_at = now() "
        "WHERE id = %s",
        (hours, ticket_id),
    )


# ---- Priority and deadlines -------------------------------------------------

def test_new_ticket_is_normal_priority_with_24h_deadline(make_customer, open_ticket):
    ticket = open_ticket(make_customer())
    assert ticket["priority"] == "normal"
    assert ticket["first_response_at"] is None and ticket["overdue"] is False
    assert _ts(ticket["due_at"]) - _ts(ticket["created_at"]) == timedelta(hours=24)


def test_customers_cannot_set_priority_when_opening(client, make_customer):
    cara = make_customer()
    res = client.post("/tickets", json={"title": "Help please", "description": "Everything is broken.",
                                        "priority": "urgent"}, headers=cara.headers)
    assert res.status_code == 422


def test_staff_change_priority_and_deadline_moves(client, make_customer, make_staff, open_ticket):
    ticket, sam = open_ticket(make_customer()), make_staff()
    res = client.patch(f"/tickets/{ticket['id']}", json={"priority": "urgent"}, headers=sam.headers)
    assert res.status_code == 200
    body = res.json()
    assert body["priority"] == "urgent"
    assert _ts(body["due_at"]) - _ts(body["created_at"]) == timedelta(hours=2)
    assert body["status"] == "open"  # other fields untouched


def test_priority_cannot_be_null_or_unknown(client, make_customer, make_staff, open_ticket):
    ticket, sam = open_ticket(make_customer()), make_staff()
    for bad in (None, "critical"):
        res = client.patch(f"/tickets/{ticket['id']}", json={"priority": bad}, headers=sam.headers)
        assert res.status_code == 422


def test_ticket_becomes_overdue_and_can_be_filtered(client, admin_conn, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    late, fresh = open_ticket(cara, title="Late ticket"), open_ticket(cara, title="Fresh ticket")
    client.patch(f"/tickets/{late['id']}", json={"priority": "high"}, headers=sam.headers)
    _age_ticket(admin_conn, late["id"], 9)  # high = 8h target

    assert client.get(f"/tickets/{late['id']}", headers=sam.headers).json()["overdue"] is True
    overdue = client.get("/tickets", params={"overdue": "true"}, headers=sam.headers).json()
    assert [t["title"] for t in overdue["items"]] == ["Late ticket"]
    on_time = client.get("/tickets", params={"overdue": "false"}, headers=sam.headers).json()
    assert [t["title"] for t in on_time["items"]] == ["Fresh ticket"]
    high = client.get("/tickets", params={"priority": "high"}, headers=sam.headers).json()
    assert high["total"] == 1


def test_first_public_staff_reply_stops_the_clock(client, admin_conn, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket = open_ticket(cara)
    _age_ticket(admin_conn, ticket["id"], 30)  # normal = 24h target, so overdue now
    url = f"/tickets/{ticket['id']}"
    assert client.get(url, headers=sam.headers).json()["overdue"] is True

    client.post(f"{url}/comments", json={"body": "Customer bump"}, headers=cara.headers)
    client.post(f"{url}/comments", json={"body": "Checking logs", "internal": True}, headers=sam.headers)
    still = client.get(url, headers=sam.headers).json()
    assert still["first_response_at"] is None and still["overdue"] is True  # neither counts

    client.post(f"{url}/comments", json={"body": "On it!"}, headers=sam.headers)
    replied = client.get(url, headers=sam.headers).json()
    assert replied["first_response_at"] is not None and replied["overdue"] is False

    first = replied["first_response_at"]
    client.post(f"{url}/comments", json={"body": "Fixed now."}, headers=sam.headers)
    assert client.get(url, headers=sam.headers).json()["first_response_at"] == first  # set once


def test_resolved_tickets_are_never_overdue(client, admin_conn, make_customer, make_staff, open_ticket):
    ticket, sam = open_ticket(make_customer()), make_staff()
    _age_ticket(admin_conn, ticket["id"], 100)
    client.patch(f"/tickets/{ticket['id']}", json={"status": "resolved"}, headers=sam.headers)
    assert client.get(f"/tickets/{ticket['id']}", headers=sam.headers).json()["overdue"] is False


# ---- Internal notes ---------------------------------------------------------

def test_internal_notes_are_hidden_from_customers(client, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket = open_ticket(cara)
    url = f"/tickets/{ticket['id']}/comments"
    client.post(url, json={"body": "Hi Cara, looking into it."}, headers=sam.headers)
    res = client.post(url, json={"body": "Probably the SSO bug again", "internal": True}, headers=sam.headers)
    assert res.status_code == 201 and res.json()["internal"] is True

    customer_view = client.get(url, headers=cara.headers).json()["items"]
    assert [c["body"] for c in customer_view] == ["Hi Cara, looking into it."]
    assert all(c["internal"] is False for c in customer_view)

    staff_view = client.get(url, headers=sam.headers).json()["items"]
    assert [c["internal"] for c in staff_view] == [False, True]


def test_customers_cannot_post_internal_notes(client, make_customer, open_ticket):
    cara = make_customer()
    ticket = open_ticket(cara)
    url = f"/tickets/{ticket['id']}/comments"
    res = client.post(url, json={"body": "secret", "internal": True}, headers=cara.headers)
    assert res.status_code == 403
    assert client.get(url, headers=cara.headers).json()["items"] == []  # nothing saved


def test_internal_note_does_not_bump_updated_at(client, make_customer, make_staff, open_ticket):
    ticket, sam = open_ticket(make_customer()), make_staff()
    before = client.get(f"/tickets/{ticket['id']}", headers=sam.headers).json()["updated_at"]
    client.post(f"/tickets/{ticket['id']}/comments", json={"body": "note", "internal": True}, headers=sam.headers)
    assert client.get(f"/tickets/{ticket['id']}", headers=sam.headers).json()["updated_at"] == before


def test_app_role_cannot_change_created_at(admin_conn, settings):
    """The SLA depends on created_at, so the app's database role must not be able to edit it."""
    import psycopg
    import pytest

    with psycopg.connect(settings.database_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE support_tickets SET created_at = now()")
