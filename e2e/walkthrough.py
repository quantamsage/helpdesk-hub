"""End-to-end walkthrough in a real browser (Playwright + Chromium).

Needs: backend on :8000 and frontend on :3000, pointing at an EMPTY test
database with two staff accounts:
    sam@example.com / staffpass123  (name "Sam Okoth")
    ria@example.com / staffpass123  (name "Ria Mwangi")

Run (from the repo root, venv active):
    pip install -r e2e/requirements.txt
    playwright install chromium
    python e2e/walkthrough.py

Also saves the README screenshots to docs/screenshots/.
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:3000"
SHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
results, console_errors = [], []

def check(name, fn):
    try:
        fn(); results.append(("PASS", name))
    except Exception as e:
        results.append(("FAIL", f"{name}: {str(e)[:600]}"))

def new_page(browser, width=1200, height=820):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    return page

def register(page, name, email, password="password123"):
    page.goto(f"{BASE}/register")
    page.get_by_label("Your name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Create account").click()

def login(page, email, password):
    page.goto(f"{BASE}/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log in").click()

with sync_playwright() as p:
    browser = p.chromium.launch()

    # --- Errors a user can hit ---
    page = new_page(browser)
    def bad_register():
        register(page, "Short", "short@example.com", "short")
        expect(page.get_by_text("String should have at least 8 characters")).to_be_visible()
    check("register shows field error for short password", bad_register)
    def bad_login():
        login(page, "nobody@example.com", "wrongpass")
        expect(page.locator(".form-error")).to_have_text("Incorrect email or password.")
        page.screenshot(path=f"{SHOTS}/login-error.png")
    check("wrong login shows friendly error", bad_login)
    def guard():
        page.goto(f"{BASE}/tickets"); page.wait_for_url("**/login")
    check("logged-out user is sent to login", guard)

    # --- Customer Cara ---
    cara = new_page(browser)
    def cara_registers():
        register(cara, "Cara Wanjiru", "cara@example.com")
        cara.wait_for_url("**/tickets")
        expect(cara.get_by_text("You haven't opened any tickets.")).to_be_visible()
    check("customer registers and sees empty state", cara_registers)

    def cara_validation():
        cara.goto(f"{BASE}/tickets/new")
        cara.get_by_label("Summary").fill("Hi")
        cara.get_by_label("What's happening?").fill("short")
        cara.get_by_role("button", name="Open ticket").click()
        expect(cara.get_by_text("String should have at least 5 characters")).to_be_visible()
        expect(cara.get_by_text("String should have at least 10 characters")).to_be_visible()
    check("new ticket form shows server field errors", cara_validation)

    ticket_url = {}
    def cara_opens():
        cara.get_by_label("Summary").fill("Can't download my March invoice")
        cara.get_by_label("What's happening?").fill(
            "When I click Download on the March invoice, the page spins and then shows a blank screen.\n\nFebruary's invoice downloads fine.")
        cara.get_by_role("button", name="Open ticket").click()
        cara.wait_for_url(re.compile(r".*/tickets/[0-9a-f-]{36}$"))
        ticket_url["cara"] = cara.url
        expect(cara.locator(".stamp")).to_have_text("Open")
        expect(cara.get_by_text("Not assigned yet.")).to_be_visible()
    check("customer opens a ticket and lands on it", cara_opens)

    def cara_replies():
        cara.get_by_label("Your reply").fill("I've tried Chrome and Firefox, same result.")
        cara.get_by_role("button", name="Send reply").click()
        expect(cara.get_by_text("I've tried Chrome and Firefox, same result.")).to_be_visible()
    check("customer adds a reply", cara_replies)

    for title in ["Two-factor code never arrives", "Change the email on my account"]:
        cara.goto(f"{BASE}/tickets/new")
        cara.get_by_label("Summary").fill(title)
        cara.get_by_label("What's happening?").fill("Details about this problem for the support team.")
        cara.get_by_role("button", name="Open ticket").click()
        cara.wait_for_url(re.compile(r".*/tickets/[0-9a-f-]{36}$"))

    def no_staff_ui_for_customer():
        cara.goto(ticket_url["cara"])
        expect(cara.get_by_role("heading", name="Conversation")).to_be_visible()
        assert cara.locator(".staff-panel").count() == 0
        cara.goto(f"{BASE}/tickets")
        expect(cara.locator(".ticket-row")).to_have_count(3)
        assert cara.get_by_label("Assigned to").count() == 0
    check("customer sees no staff controls or assignee filter", no_staff_ui_for_customer)

    # --- Another customer can't see Cara's ticket ---
    dan = new_page(browser)
    def dan_blocked():
        register(dan, "Dan Kiprop", "dan@example.com")
        dan.wait_for_url("**/tickets")
        dan.goto(ticket_url["cara"])
        expect(dan.get_by_text("We couldn't find that ticket.")).to_be_visible()
        dan.goto(f"{BASE}/tickets")
        expect(dan.get_by_text("You haven't opened any tickets.")).to_be_visible()
    check("other customer gets 'couldn't find' on Cara's ticket", dan_blocked)
    dan.goto(f"{BASE}/tickets/new")
    dan.get_by_label("Summary").fill("App crashes when uploading a photo")
    dan.get_by_label("What's happening?").fill("Every time I attach a photo from my phone the app closes.")
    dan.get_by_role("button", name="Open ticket").click()
    dan.wait_for_url(re.compile(r".*/tickets/[0-9a-f-]{36}$"))

    # --- Staff Sam ---
    sam = new_page(browser)
    def sam_sees_all():
        login(sam, "sam@example.com", "staffpass123")
        sam.wait_for_url("**/tickets")
        expect(sam.get_by_role("heading", name="All tickets")).to_be_visible()
        expect(sam.locator(".ticket-row")).to_have_count(4)
        assert sam.get_by_role("link", name="Open a ticket").count() == 0
    check("staff sees all 4 tickets, no 'Open a ticket'", sam_sees_all)

    def sam_works_ticket():
        sam.goto(ticket_url["cara"])
        sam.get_by_label("Status").select_option("in_progress")
        sam.get_by_label("Assigned to").select_option(label="Sam Okoth")
        sam.get_by_role("button", name="Save changes").click()
        expect(sam.get_by_role("status")).to_have_text("Changes saved.")
        expect(sam.locator(".ticket-head .stamp")).to_have_text("In progress")
        expect(sam.get_by_text("Assigned to Sam Okoth.")).to_be_visible()
        sam.get_by_label("Your reply").fill("Thanks Cara. I can reproduce this, and I've passed it to billing. I'll update you here.")
        sam.get_by_role("button", name="Send reply").click()
        expect(sam.get_by_text("I've passed it to billing")).to_be_visible()
        sam.screenshot(path=f"{SHOTS}/ticket-staff-view.png", full_page=True)
    check("staff sets status, assigns, replies", sam_works_ticket)

    def sam_resolves_other():
        sam.goto(f"{BASE}/tickets")
        sam.get_by_role("link", name=re.compile("Change the email")).click()
        sam.wait_for_url(re.compile(r".*/tickets/[0-9a-f-]{36}$"))
        expect(sam.locator(".staff-panel")).to_be_visible()
        sam.get_by_label("Status").select_option("resolved")
        sam.get_by_role("button", name="Save changes").click()
        expect(sam.get_by_role("status")).to_have_text("Changes saved.")
    check("staff resolves another ticket", sam_resolves_other)

    def sam_filters():
        sam.goto(f"{BASE}/tickets")
        expect(sam.locator(".ticket-row")).to_have_count(4)
        sam.screenshot(path=f"{SHOTS}/staff-queue.png", full_page=True)
        sam.get_by_label("Assigned to").select_option("me")
        expect(sam.locator(".ticket-row")).to_have_count(1)
        sam.get_by_label("Assigned to").select_option("none")
        expect(sam.locator(".ticket-row")).to_have_count(3)
        sam.get_by_label("Status").select_option("resolved")
        expect(sam.locator(".ticket-row")).to_have_count(1)
        sam.get_by_label("Assigned to").select_option("me")
        expect(sam.get_by_text("No tickets match these filters.")).to_be_visible()
    check("staff filters by assignee and status", sam_filters)

    def staff_new_page_blocked():
        sam.goto(f"{BASE}/tickets/new")
        expect(sam.get_by_text("Staff can't open tickets.")).to_be_visible()
    check("staff visiting /tickets/new sees a clear message", staff_new_page_blocked)

    # --- Cara sees the update ---
    def cara_sees_update():
        cara.goto(ticket_url["cara"])
        expect(cara.locator(".ticket-head .stamp")).to_have_text("In progress")
        expect(cara.locator(".reply-staff")).to_contain_text("Sam Okoth")
        cara.screenshot(path=f"{SHOTS}/ticket-customer-view.png", full_page=True)
        cara.goto(f"{BASE}/tickets")
        expect(cara.locator(".ticket-row")).to_have_count(3)
        cara.screenshot(path=f"{SHOTS}/customer-tickets.png", full_page=True)
    check("customer sees new status and staff reply", cara_sees_update)

    def expired_session():
        cara.evaluate("sessionStorage.setItem('support_token', 'not-a-valid-token')")
        cara.goto(f"{BASE}/tickets")
        cara.wait_for_url("**/login**")
    check("invalid token sends user back to login", expired_session)

    def logout():
        sam.get_by_role("button", name="Log out").click()
        sam.wait_for_url("**/login")
        sam.goto(f"{BASE}/tickets"); sam.wait_for_url("**/login")
    check("log out clears the session", logout)

    # --- Mobile ---
    mobile = new_page(browser, 390, 844)
    def mobile_view():
        login(mobile, "ria@example.com", "staffpass123")
        mobile.wait_for_url("**/tickets")
        expect(mobile.locator(".ticket-row")).to_have_count(4)
        width = mobile.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"page scrolls sideways ({width}px)"
        mobile.screenshot(path=f"{SHOTS}/mobile-queue.png", full_page=True)
    check("mobile layout has no sideways scroll", mobile_view)

    browser.close()

for status, name in results:
    print(status, name)
csp = [e for e in console_errors if "Content Security Policy" in e or "Refused" in e]
print(f"\n{sum(s=='PASS' for s,_ in results)}/{len(results)} passed")
print("CSP violations:", csp or "none")
print("Other console errors:", [e for e in console_errors if e not in csp][:6] or "none")
