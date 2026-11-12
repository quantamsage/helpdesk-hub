"""Role-based access and ownership: who can see and do what."""


# ---- Customers only see their own tickets ----------------------------------

def test_customer_sees_only_own_tickets_in_list(client, make_customer, open_ticket):
    cara, dan = make_customer("cara@example.com"), make_customer("dan@example.com")
    open_ticket(cara, title="Cara's ticket")
    open_ticket(dan, title="Dan's ticket")

    res = client.get("/tickets", headers=cara.headers).json()
    assert res["total"] == 1
    assert [t["title"] for t in res["items"]] == ["Cara's ticket"]


def test_other_customers_ticket_is_404_everywhere(client, make_customer, open_ticket):
    cara, dan = make_customer("cara@example.com"), make_customer("dan@example.com")
    ticket_id = open_ticket(cara)["id"]

    for res in (
        client.get(f"/tickets/{ticket_id}", headers=dan.headers),
        client.get(f"/tickets/{ticket_id}/comments", headers=dan.headers),
        client.post(f"/tickets/{ticket_id}/comments", json={"body": "hi"}, headers=dan.headers),
    ):
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "not_found"


def test_someone_elses_ticket_looks_identical_to_a_missing_one(client, make_customer, open_ticket):
    cara, dan = make_customer("cara@example.com"), make_customer("dan@example.com")
    ticket_id = open_ticket(cara)["id"]
    others = client.get(f"/tickets/{ticket_id}", headers=dan.headers)
    missing = client.get("/tickets/00000000-0000-0000-0000-000000000000", headers=dan.headers)
    assert others.json() == missing.json()


def test_dans_comment_attempt_is_not_saved(client, make_customer, open_ticket):
    cara, dan = make_customer("cara@example.com"), make_customer("dan@example.com")
    ticket_id = open_ticket(cara)["id"]
    client.post(f"/tickets/{ticket_id}/comments", json={"body": "sneaky"}, headers=dan.headers)
    assert client.get(f"/tickets/{ticket_id}/comments", headers=cara.headers).json()["items"] == []


# ---- Role restrictions ------------------------------------------------------

def test_customer_cannot_update_ticket(client, make_customer, open_ticket):
    cara = make_customer()
    ticket_id = open_ticket(cara)["id"]
    res = client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=cara.headers)
    assert res.status_code == 403
    assert client.get(f"/tickets/{ticket_id}", headers=cara.headers).json()["status"] == "open"


def test_customer_cannot_list_staff_or_filter_by_assignee(client, make_customer):
    cara = make_customer()
    assert client.get("/staff", headers=cara.headers).status_code == 403
    assert client.get("/tickets?assignee=me", headers=cara.headers).status_code == 403


def test_staff_cannot_open_tickets(client, make_staff):
    sam = make_staff()
    res = client.post("/tickets", json={"title": "Staff ticket", "description": "Should not be allowed"}, headers=sam.headers)
    assert res.status_code == 403


def test_every_protected_route_needs_a_token(client):
    some_id = "00000000-0000-0000-0000-000000000000"
    calls = [
        ("GET", "/auth/me"), ("GET", "/staff"), ("GET", "/tickets"), ("POST", "/tickets"),
        ("GET", f"/tickets/{some_id}"), ("PATCH", f"/tickets/{some_id}"),
        ("GET", f"/tickets/{some_id}/comments"), ("POST", f"/tickets/{some_id}/comments"),
    ]
    for method, path in calls:
        assert client.request(method, path, json={}).status_code == 401, f"{method} {path}"


# ---- Staff workflow ---------------------------------------------------------

def test_staff_sees_all_tickets(client, make_customer, make_staff, open_ticket):
    open_ticket(make_customer("cara@example.com"))
    open_ticket(make_customer("dan@example.com"))
    assert client.get("/tickets", headers=make_staff().headers).json()["total"] == 2


def test_staff_can_view_and_comment_on_any_ticket(client, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket_id = open_ticket(cara)["id"]

    assert client.get(f"/tickets/{ticket_id}", headers=sam.headers).status_code == 200
    reply = client.post(f"/tickets/{ticket_id}/comments", json={"body": "Looking into it"}, headers=sam.headers)
    assert reply.status_code == 201
    assert reply.json()["author"]["role"] == "staff"

    thread = client.get(f"/tickets/{ticket_id}/comments", headers=cara.headers).json()["items"]
    assert [c["body"] for c in thread] == ["Looking into it"]


def test_comment_thread_is_oldest_first_and_bumps_updated_at(client, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket = open_ticket(cara)
    client.post(f"/tickets/{ticket['id']}/comments", json={"body": "first"}, headers=cara.headers)
    client.post(f"/tickets/{ticket['id']}/comments", json={"body": "second"}, headers=sam.headers)

    thread = client.get(f"/tickets/{ticket['id']}/comments", headers=cara.headers).json()["items"]
    assert [c["body"] for c in thread] == ["first", "second"]
    after = client.get(f"/tickets/{ticket['id']}", headers=cara.headers).json()
    assert after["updated_at"] > ticket["updated_at"]


def test_staff_changes_status_and_assigns(client, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket_id = open_ticket(cara)["id"]

    res = client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress", "assignee_id": sam.id}, headers=sam.headers)
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"
    assert res.json()["assignee"] == {"id": sam.id, "name": "Sam"}

    # Sending only status leaves the assignee alone
    res = client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=sam.headers)
    assert res.json()["assignee"]["id"] == sam.id

    # Explicit null unassigns
    res = client.patch(f"/tickets/{ticket_id}", json={"assignee_id": None}, headers=sam.headers)
    assert res.json()["assignee"] is None
    assert res.json()["status"] == "resolved"


def test_cannot_assign_to_a_customer_or_unknown_user(client, make_customer, make_staff, open_ticket):
    cara, sam = make_customer(), make_staff()
    ticket_id = open_ticket(cara)["id"]
    for bad_id in (cara.id, "00000000-0000-0000-0000-000000000000"):
        res = client.patch(f"/tickets/{ticket_id}", json={"assignee_id": bad_id}, headers=sam.headers)
        assert res.status_code == 422
        assert res.json()["error"]["details"][0]["field"] == "assignee_id"


def test_patch_missing_ticket_is_404(client, make_staff):
    sam = make_staff()
    res = client.patch("/tickets/00000000-0000-0000-0000-000000000000", json={"status": "resolved"}, headers=sam.headers)
    assert res.status_code == 404


def test_staff_filters(client, make_customer, make_staff, open_ticket):
    cara, sam, ria = make_customer(), make_staff("sam@example.com", "Sam"), make_staff("ria@example.com", "Ria")
    mine = open_ticket(cara, title="Assigned to Sam")["id"]
    open_ticket(cara, title="Nobody's yet")
    client.patch(f"/tickets/{mine}", json={"assignee_id": sam.id, "status": "in_progress"}, headers=sam.headers)

    def titles(query):
        return [t["title"] for t in client.get(f"/tickets?{query}", headers=sam.headers).json()["items"]]

    assert titles("assignee=me") == ["Assigned to Sam"]
    assert titles("assignee=none") == ["Nobody's yet"]
    assert titles(f"assignee={ria.id}") == []
    assert titles("status=in_progress") == ["Assigned to Sam"]
    assert titles("status=open") == ["Nobody's yet"]


def test_staff_list_for_assign_dropdown(client, make_customer, make_staff):
    make_customer()
    make_staff("sam@example.com", "Sam")
    make_staff("ria@example.com", "Ria")
    res = client.get("/staff", headers=make_staff("al@example.com", "Al").headers).json()
    assert [s["name"] for s in res["items"]] == ["Al", "Ria", "Sam"]


def test_pagination(client, make_customer, open_ticket):
    cara = make_customer()
    for i in range(5):
        open_ticket(cara, title=f"Ticket number {i}")
    page = client.get("/tickets?limit=2&offset=2", headers=cara.headers).json()
    assert page["total"] == 5
    assert [t["title"] for t in page["items"]] == ["Ticket number 2", "Ticket number 1"]  # newest first
