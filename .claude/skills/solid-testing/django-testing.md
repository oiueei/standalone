# Django/DRF testing reference (OIUEEI)

Stack: pytest-django · factory_boy · time-machine · DRF APIClient (Bearer JWT).
Fixtures live in `core/tests/conftest.py`. Every POST needs `format="json"`
(JSON-only parser). Rate limits are off in tests.

## Models — what actually needs a test

Not the ORM (Django tested it). Test **your** rules:

- **Custom methods and properties** — every branch, with the boundary inputs.
- **Constraints** — prove the DB refuses the duplicate, not just that the happy
  insert works:

```python
def test_a_booking_creates_at_most_one_transfer_per_thing(thing, user, user2):
    booking = BookingFactory(thing_code=thing)
    ThingTransfer.objects.create(thing=thing, from_user=user, to_user=user2,
                                 booking=booking, lent_date=date(2026, 7, 1))
    with pytest.raises(IntegrityError):
        ThingTransfer.objects.create(thing=thing, from_user=user, to_user=user2,
                                     booking=booking, lent_date=date(2026, 7, 2))
```

- **`on_delete` semantics when they carry product meaning** — this repo's
  erasure rules are behaviour, not plumbing:

```python
def test_deleting_the_questioner_keeps_the_question_anonymised(faq):
    faq.questioner.delete()
    faq.refresh_from_db()
    assert faq.questioner is None          # attribution gone (right to erasure)
    assert faq.question == "Is this available?"  # knowledge stays with the thing
```

- **Signals** — assert the *effect* (e.g. the Cloudinary destroy was queued
  with the right public_id via `assert_called_once_with`), not "no crash".

## Views & serializers — the permission matrix is the test

For every endpoint, the minimum honest set is:

| Case | Expectation |
|---|---|
| Anonymous | 401 (or the *designed* anonymous behaviour — assert its exact shape) |
| Authenticated, wrong user | 403/404 — and prove **nothing changed** (`refresh_from_db`) |
| Right user, invalid payload | 400 with the field named in the error |
| Right user, valid payload | Status **and** body **and** side effects (DB row, `mail.outbox`, notification) |
| Not found | 404 (and for IDOR-sensitive lookups: someone else's code → 404, not 403 leak) |

```python
def test_only_the_owner_can_update_a_collection(authenticated_client2, collection):
    res = authenticated_client2.put(
        f"/api/v1/collections/{collection.code}/",
        {"headline": "hijacked"}, format="json",
    )
    assert res.status_code in (403, 404)
    collection.refresh_from_db()
    assert collection.headline == "Test Collection"   # ← the half everyone forgets
```

**Response bodies over status codes.** `assert res.status_code == 200` alone is
smell #1. Assert the fields that carry the behaviour — and for list endpoints,
assert *what is excluded* (the INACTIVE thing, the other user's row) — exclusion
is usually the security property.

**Serializer-level rules** (per-viewer fields, localized limits) get unit tests
at the serializer, plus ONE integration test proving the view wires the context.

## Emails and notifications

An action that "notifies" is untested until the test opens the envelope:

```python
assert len(mail.outbox) == 1
sent = mail.outbox[0]
assert sent.to == [owner.email]
assert rsvp.token in sent.body          # the action link actually works
assert "<script>" not in sent.alternatives[0][0]   # escaping held
```

For the preference pipeline: one test per category proving opt-out is honoured
and Cat. 1 ignores it.

## Transactions and races

- Partial-failure rollback: force the second write in an atomic block to fail
  (e.g. `mocker.patch.object(..., side_effect=IntegrityError)`) and assert the
  FIRST write was rolled back too.
- Concurrency on SQLite can't be executed — but the *re-validation under lock*
  can: call the service twice with state mutated between calls and assert the
  second attempt refuses (see `test_booking_service_race_guards.py` for the
  house pattern). When a real race can't be simulated, say so in a comment and
  pin the lock-ordering reasoning there instead of writing a fake test.

## Time

`time_machine.travel("2026-07-01")` — never sleep, never `datetime.now()` maths
in the test body. Boundary tests go exactly ON the boundary (72h ± 1 second).

## Migrations

- CI must keep `python manage.py makemigrations --check` clean.
- A migration altering data gets a test exercising its `RunPython` both ways
  when feasible; at minimum prove idempotence (running twice is safe) — this
  repo's release phase runs `migrate` on every deploy.
- Schema changes with product meaning (SET_NULL vs CASCADE) are tested at the
  model level as behaviour (see erasure example above).

## Regression tests

Every fixed bug gets a test that FAILS on the pre-fix code. Name it after the
symptom, comment the root cause, and *run it against the broken version once*
(git stash the fix, watch it fail, restore). "Verificado por mutación" — the
house habit.
