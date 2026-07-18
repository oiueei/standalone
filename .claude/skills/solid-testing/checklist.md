# Weak-test checklist — the smell catalogue

Grade every test you read or write against this list. Each entry: the smell,
why it lies, and the bad→good pair.

## 1. The no-op assertion

Asserts "it didn't crash" — `status_code == 200`, `expect(render).not.toThrow()`.

```python
# BAD — passes even if the endpoint returns an empty page forever
res = client.get("/api/v1/my-bookings/")
assert res.status_code == 200

# GOOD — pins the behaviour: my booking is there, with the fields the UI needs
res = client.get("/api/v1/my-bookings/")
assert res.status_code == 200
rows = res.json()["results"]
assert [r["code"] for r in rows] == [booking.code]
assert rows[0]["thing_headline"] == "Test Thing"
```

## 2. The lonely happy path

One valid input, zero hostile ones. For every function ask: `None`? empty?
boundary (0, max, max+1, exactly-at-limit)? wrong type? duplicate? concurrent
repeat? For every endpoint: invalid payload → 400 naming the field.

```python
# The 64-char headline limit is per LANGUAGE — the boundary test goes AT 64 and 65:
assert serializer_accepts(headline="x" * 64)
assert serializer_rejects(headline="x" * 65)
assert serializer_accepts(headline=json.dumps({"es": "x" * 64, "ca": "y" * 64}))
```

## 3. The unverified mock

A mock that was configured but never interrogated proves nothing.

```python
# BAD
mocker.patch("core.services.email_service.send_contact_email")
client.post("/api/v1/contact/", payload, format="json")   # green even if never called

# GOOD
mock_send = mocker.patch("core.views.contact.send_contact_email")
client.post("/api/v1/contact/", payload, format="json")
mock_send.assert_called_once_with("Napoleón", "nappy@example.com", "Help!", kind="support")
```

(Better still, in this repo: don't mock the email service at all — assert on
`mail.outbox`, the real seam.)

## 4. The fake integration test

Everything mocked = a unit test wearing a costume. An integration test earns
its name by exercising the real view + serializer + DB (+ `mail.outbox`).
Mock only true externals (Cloudinary, SMTP transport, clock).

## 5. The unguarded bugfix

A bug without a regression test WILL return. The test must have been seen to
fail on the broken code (stash the fix once and watch it go red). Name it
after the symptom: `test_logout_actually_ends_the_session`.

## 6. Implementation-coupled assertions

Asserting private attrs, internal call order, or exact markup means any honest
refactor breaks the suite — so people stop refactoring, or stop trusting red.
Assert through the public seam: response bodies, rendered roles/labels, DB
state, outbox.

```jsx
// BAD: expect(container.querySelector('.thing-card-meta')).toBeTruthy()
// GOOD:
expect(screen.getByRole('link', { name: 'Lele' })).toHaveAttribute('href', '/L3L3oo');
```

## 7. The vacuous test

Delete the assertions — does it still pass? Then it tested the fixture, not
the code. Common form: heavy arrange, one `assert response is not None`.
Mutation testing (`scripts/mutation_test.sh`) catches these mechanically.

## 8. The golden number

`assert result == 42` where 42 was copied from running the code. It pins
"unchanged", not "correct". Derive expectations independently in the test
(compute the count from the fixtures you created), or comment the derivation.

## 9. Order/time dependence

A test that fails at midnight, on the 31st, in another timezone, or when run
alone. Freeze time (`time_machine`), never rely on today's date arithmetic,
never depend on another test's leftovers (pytest-django rolls back per test —
module-level state and caches are the leak paths; the repo's rate-limit quota
cache is the canonical example).

## 10. The silenced failure

`try/except` in tests, broad `pytest.raises(Exception)`, or asserting inside a
conditional (`if response.ok: assert …` — green when not ok!). Assert the
EXACT exception/error and make every path assert something.

---

**The meta-check:** for each test file ask — *if a junior deleted the feature's
core `if` tomorrow, which test here goes red?* If the answer is "none", the
file is decoration.
