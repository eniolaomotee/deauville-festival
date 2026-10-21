# Deauville Festival du Rire - programme platform

The programme of the Deauville Festival du Rire (10-13 June 2027): venues,
artists and three kinds of performances, with the scheduling rules enforced in
one place. The data lives in `data/festival.json`. A command line and a web
API read and change it; the public website and the admin are static pages
that talk to the API.

## Install and run

```bash
uv sync                                        # install everything
uv run deauville                               # summary of the festival
uv run deauville venues                        # the venues
uv run deauville programme 2027-06-11          # the programme of one day
uv run deauville artist max-pellerin           # the shows of one artist
uv run deauville now 2027-06-11T21:00          # on stage now, and the next 3
uv run deauville add                           # schedule a solo show
uv run deauville cancel ID                     # cancel a performance
uv run deauville serve                         # website, admin and API
uv run deauville --data other.json programme 2027-06-11   # another data file
```

With the server running: website at http://127.0.0.1:8000/, admin at
http://127.0.0.1:8000/admin/, API under `/api` (contract in `API.md`).

Tests and build:

```bash
uv run pytest        # 49 tests
uv run ruff check .  # lint
uv build             # wheel in dist/
```

## Structure

Everything is in the package `src/deauville/`:

| Module        | Role                                                                    |
| ------------- | ----------------------------------------------------------------------- |
| `model.py`    | the objects: `Artist`, `Venue`, `Performance` and its three kinds        |
| `festival.py` | `Festival`: holds the objects, answers questions, enforces the rules    |
| `errors.py`   | the error family: one class per kind of broken rule                     |
| `storage.py`  | how a festival is loaded and saved: `JsonStorage`, `MemoryStorage`      |
| `api.py`      | the FastAPI routes of `API.md`, built by `create_app(storage, web)`     |
| `cli.py`      | the `deauville` command: parsers, printing, and `serve`                 |

`tests/` holds `test_rules.py` (the rules), `test_kinds.py` (the three kinds),
`test_admin.py` (the write operations) and `test_api.py` (every route of
`API.md` through `TestClient`).

### The objects

- `Artist` and `Venue` are dataclasses. Each knows its `slug`, built from its
  name, and two of them are equal when their slugs are equal. Each checks its
  own fields when created: an empty name or a venue with no seat is refused.
- `Performance` is an abstract class: what every performance shares (venue,
  start, duration, `end`, `festival_day`, `id`, `too_close`, `to_view`,
  `to_data`). It cannot be created itself.
- `SoloShow` (one artist and a title), `Lineup` (a host and at least two
  acts, duration computed from the acts) and `Workshop` (a teacher, a maximum
  of participants, a list of registered names) inherit from it. Each one
  fills the abstract parts: who its `artists` are, its `summary`, the
  `role_of` an artist, and its own fields for the API and the file.
- The dict `PERFORMANCE_KINDS` maps `"solo"`, `"lineup"`, `"workshop"` to the
  class. It is the only place where the kind name is read: no `if kind ==`
  anywhere else.

### Where the rules live

A rule about one object is checked in that object's constructor (a lineup
with one act, a workshop with zero places). A rule that needs the whole
festival is checked in `Festival.check`: the venue exists, the start is
inside the festival days, the venue is free with 30 minutes of gap, no artist
is on two stages at once. `schedule`, `replace` and `register` all go through
`check`, and the lists of venues, artists and performances are private
(`_performances`), returned as copies. The command line and the API only call
these methods, so neither can add a performance that breaks a rule.

### How a caller knows which rule broke

Every rule raises a subclass of `FestivalError`: `NotFoundError` (unknown
slug or id), `ConflictError` (busy venue, full workshop, outside the days,
duplicate), `InvalidError` (bad data, bad date format), `StorageError`
(unreadable file). The message is a sentence for the organiser. The command
line prints the message; the API maps the class to a status code with the
`STATUS` dict (404, 409, 422, 500) and returns the message as JSON. Bad
input from Python itself (`ValueError` from a date) is converted to
`InvalidError`, so callers never see a traceback.

### What would change with a database

Only `storage.py`. `Storage` is an abstract class with `load()` and
`save(festival)`. `JsonStorage` reads and writes the file through
`Festival.from_data` / `to_data`; `MemoryStorage` keeps a dict for the tests.
A `SqliteStorage` would be a third class, and `cli.main` would choose it.
The model, the API and the command line would not change.

## Done, not done, known bugs

Done: steps 00 to 12 of the track. All the rules of the brief, the three
kinds, the admin, the package with the `deauville` command, every route of
`API.md`, 49 tests.

Not done: the SQLite storage extension. Everything else in the brief is in.

Known bugs: none that I know of. The festival-day bug of step 02 (a show at
01:00 listed under the wrong day) was fixed in step 04: the festival day of a
show is the date of its start minus 6 hours.
