---
name: codebase-change
description: >
  The guidelines to follow in any codebase modification — Python or JavaScript/TypeScript.
  Use this skill whenever you are asked to modify, refactor, add features, fix bugs, or
  write new code in any codebase. Also use it when reviewing code for quality, suggesting
  improvements, or answering "how should I write X?" questions. Load the language-specific
  reference file that matches the project you're working in — Python or JavaScript/TypeScript.
  Even if the user doesn't explicitly ask for "codebase change guidelines", apply these
  principles whenever you touch code.
---

# Codebase Change — Universal Guidelines

This skill provides a consistent set of software engineering principles that apply regardless of language. Language-specific examples, patterns, and tooling are in separate reference files — load only the one you need.

## How to Use This Skill

1. Read the **Core Principle** and the shared rules below (this file). The Core Principle governs every other rule.
2. Detect the project's primary language from the files you're editing:
   - **Python** (.py, pyproject.toml, requirements.txt, setup.py) → read `references/python-guidelines.md`
   - **JavaScript / TypeScript** (.ts, .js, .tsx, .jsx, package.json, tsconfig.json) → read `references/javascript-guidelines.md`
   - **Mixed project** (e.g., Python backend + JS frontend) → load both references.
3. Apply the shared rules below, combined with the language-specific patterns from the reference.
4. Run the **Self-Review Checkpoint** before you finish — it is where most comment noise gets caught.

**Reference file paths** (relative to this skill directory):
- `references/python-guidelines.md` — Python with Pydantic, SQLAlchemy, Celery, structlog
- `references/javascript-guidelines.md` — JavaScript/TypeScript with Zod, Prisma/Drizzle, Express/Fastify, Node.js

---

## Core Principle: The Code Is the Documentation

Every other rule in this skill serves one outcome: a reader who knows the language but not your project follows your code cold, top to bottom, **without reading a single comment**. The structure, the names, and the shape of the code carry all the meaning.

**The default is no comment.** Not "few comments" — none. A comment is not a normal option you pick from a menu; it is absent unless something extraordinary pushes it in. Write your code as if comments did not exist in the language. Then, only if a line would be *actively misleading or dangerous* without a note, allow exactly one — see the escape hatch below.

When a line feels like it needs explaining, the code is asking to be rewritten, not annotated. Exhaust these first — this is the complete, closed set of tools you reach for:

1. **Rename it.** Make the name state the intent. `total += fee` becomes `invoice_total += late_payment_fee` and needs no comment.
2. **Extract it.** Pull a dense block into a function or variable whose name replaces the explanation you would have written.
3. **Name the constant.** Replace the magic number or magic string; the name carries the meaning (`SALES_TAX_RATE`, not `0.08`).
4. **Strengthen the type.** When a comment exists because the type is too weak to express the value, make the type say it: `status: Literal["SUCCESS", "FAILED"]` instead of `status: str  # "SUCCESS"|"FAILED"`.

That set is closed. **A comment is not step five.** If you are about to write one, you stopped at 1–4 too early — go back. The reason this matters: every comment is a second source of truth that rots into a lie the moment the code changes and the comment does not. The fewer you write, the fewer lies your codebase accumulates.

**Restating comments are wrong — delete them on contact, across the whole file you open.** A comment that paraphrases the code next to it (`# validate the input` above a `validate()` call, `// fetch the user`, `# loop over orders`) is pure noise. Treat one the way you treat a lint error: remove it the instant you see it, whether you wrote it or merely inherited it. This is the active side of the rule — you do not merely avoid *adding* restating comments; when you open a file to make a change, you *remove* the restating comments already sitting anywhere in that file. A one-line fix is a perfectly good reason to clear the noise from the rest of the file too. Comments are not logic; stripping them is low-risk and keeps the file honest. (Stay surgical about *logic*: do not rewrite or refactor functions you were not asked to change — only their comment noise. And a genuine *why*-comment survives — see the escape hatch below.)

The rule in action:

```text
What tends to get produced (every comment here must be deleted):

def get_user(user_id):               # fetch the user from the DB
    user = db.find(user_id)          # look up by id
    if not user:                     # check if it exists
        return None                  # not found
    return user                      # return the user

What this skill expects (zero comments — the code already says all of it):

def get_user(user_id):
    user = db.find(user_id)
    return user
```

The function name, the calls, and the return already said everything the five comments did. The five comments were five future lies.

**The escape hatch — the one situation a comment is allowed.** A comment is permitted only when the code, read by a competent programmer, would be *misleading or dangerous* without the note: a workaround for an external bug, a surprising constraint the code cannot encode, a unit or ordering footgun that would silently corrupt data. This is rare — genuinely once per long file, often never. If you reached for the comment easily, it does not qualify; the note must explain *why*, never *what*.

```python
amount_cents = int(order_total_dollars * 100)  # provider requires cents, not dollars
```

Without the note, `int(x * 100)` reads as a careless float truncation. The note encodes a unit constraint the code cannot express. Read this as the *shape* of an acceptable comment — and as a measure of how high the bar is: a conversion that would silently corrupt money. Almost nothing you write clears it. When in doubt, leave the comment out.

---

## Apply the guidelines to the whole function you edit, not just the changed line

When you touch a function — even for a one-line bug fix — bring the **entire function** up to the standard in this skill, not just the line you changed. Fixing a bug and following the guidelines are not two separate modes: if you leave a magic number, an unnamed complex condition, or a bare `return None` in the very function you just edited, the next reader sees inconsistent code and the guidelines might as well not exist. Because you are already responsible for that function, also extract its magic numbers into named constants, name its complex conditions as booleans, model its errors as state (a `Result`, not a silent `None`), flatten deep nesting with guard clauses, and strengthen its types. Do this even when the user asked only for the bug fix — leave the function better than you found it.

Scope: the **function** you are editing. Leave the other functions in the file alone — that is surgical discipline, and rewriting functions you were not asked to touch creates large, risky diffs. (Comment noise is the one exception you sweep *file-wide*, because deleting a restating comment is zero-risk; every other guideline stays bounded to the function you touched.)

---

## 1. Data Handling: Validate at the Boundary

**Why it matters:** Invalid data is the root cause of most runtime bugs. If you validate once, at the entry point, the rest of your code can trust the data it receives and stay clean.

**Shared rules:**
- Define strict schemas for all data entering the system (API payloads, queue messages, DB rows, env vars).
- Validate once, at the entry point. Never scatter type checks throughout domain logic.
- Reject invalid data immediately with a clear, structured error.
- Trust validated objects downstream — no redundant null/type checks on fields your schema guarantees exist.
- Avoid generic catch-all types (`Any` in Python, `any` in TypeScript). Use `unknown` + schema parse in TS, and strict Pydantic types in Python.

**Language-specific patterns:** See reference files for Pydantic (Python) and Zod (JavaScript) examples.

---

## 2. Error Management: Errors Are State, Not Just Logs

**Why it matters:** Logging an error and continuing silently hides failures. Errors should change the control flow — the caller must know something went wrong and act on it.

**Shared rules:**
- Model errors explicitly as structured objects, not just log messages.
- Return a state object that includes a status field (`ok: true/false`) and error details.
- The caller must check the error state and react (return HTTP error, retry, abort, etc.).
- Eliminate "log and forget" — a catch block that only logs without changing return state is a bug.
- Use a custom error hierarchy with domain-specific error classes.
- **Domain errors live in the module's dedicated errors file, never mixed with behavior code.** Each module that raises its own errors has an `errors.py` (Python) / `errors.ts` (JS/TS) inside it — an exception class declared in a routes file, a service, a pipeline, or next to business logic is a defect: move it there. The hierarchy must be clear at a glance: named for the domain failure (`UnknownStrategyError`, `IngestionError`), subclassing the builtin it replaces (`ValueError`, `KeyError`) when callers may catch the builtin.
- **No bare builtins for domain failures.** `raise ValueError(...)` / `throw new Error(...)` for a failure the domain owns is a defect — declare a named error in the module's `errors` file so callers can catch precisely. Builtins stay acceptable for true programmer errors (assertion-style guards).

**Language-specific patterns:** See reference files for Python's `Result` dict pattern and JavaScript's `Result<T>` type.

---

## 3. Function Scope: Do Not Nest Functions

**Why it matters:** Nested functions capture outer scope via closures, making code hard to test, hard to reason about, and prone to subtle bugs from hidden state.

**Shared rules:**
- Define functions at module scope or as class/static methods — never inside other functions.
- Extract inner logic to top-level helpers (prefix with `_` if internal).
- Pass all dependencies via explicit parameters — no closure-captured variables.
- The only exception is framework-mandated nesting (React hooks, decorator callbacks) — keep these minimal.

---

## 4. Code Structure: Obvious, Predictable, Readable

**Why it matters:** Code is read 10x more than it's written, and a human must find things by prediction, not exploration. A layout where every location is guessed correctly before opening the tree is part of code quality — as much as the code inside the files.

**Shared rules:**

*Files and folders — location must be predictable:*
- **Same kind of thing, same-named file, every module.** Data contracts in `schemas.py`, domain errors in `errors.py` (§ 2, § 13), abstractions in `base.py`, lookups in `registry.py`. Synonyms (`models.py`, `exceptions.py`, `types.py`) and definitions mixed into behavior files both break the prediction.
- **Every architectural layer has a predictable home in every domain.** Ports in `base.py`; the domain's orchestrator in `service.py` (`pipeline.py` when it is a pipeline); vendor adapters named by role with the vendor inside (§ 12); and one composition root (`composition.py` or the framework's equivalent) wiring implementations to ports for the whole app. A reader who wants "the service" or "the wiring" opens that file without searching.
- **Orchestration lives in services, never in routes or wiring files.** Routes validate, delegate to a service, and map domain errors to transport responses (HTTP status, queue nack); services compose the domain's operations and raise domain errors (§ 2); the composition root only wires. Business logic in a routes file or a DI/wiring file is a defect — including readiness checks that raise HTTP errors there.
- **Folders are named after domains, not mechanics.** `ingestion/`, `retrieval/`, `billing/` — never `utils/`, `helpers/`, `common/`, `misc/`, which become unfindable dumping grounds. A module whose name needs "and" is two modules.
- **Declarations are separated from behavior.** Schemas and errors modules hold declarations only; behavior modules (`service.py`, `pipeline.py`, `routes.py`, stores) import them. The separation is what makes location predictable.
- **Consistency beats local cleverness.** Follow the layout the project already uses — one module arranged differently from its siblings makes every other module harder to trust.
- **Split only when it pays.** One `schemas.py` per package until multiple domains accumulate, then promote to `schemas/` (§ 13). Pre-splitting is structure for its own sake.

*Inside a file:*
- **Small, single-purpose functions.** If you can't name it in a few words without an "and", it does too much — split it.
- **Guard clauses over nesting.** Check invalid conditions first and exit early. Flat reads better than nested.
- **Names answer "what is this?", not "what type is this?".** Prefer `active_users` over `user_list`, `order_total` over `num`. Ban the generics: `data`, `item`, `x`, `temp`, `resp`, `obj`, `value`, `info`, and `result` (unless it genuinely is a `Result` type). If a name needs a comment to be understood, the name is wrong — rename it, don't annotate it.
- **No project-local abbreviations — names are read by someone without your context.** `kb` → `knowledge_base`, `rrf` → `reciprocal_rank_fusion`. Spell the phrase out however long it gets: `rank_fusion_smoothing_constant`, never `rrf_k`. An abbreviation earns its place only as standard industry/domain vocabulary (`http`, `url`, `bm25`) or the domain's own formal proper name — never as a typing convenience. This covers identifiers, filenames, trace/log keys, and stored-prefix values alike.
- **Extract complex logic.** When a block gets dense, pull it into a named function. The function name replaces the comment you would have written.
- **Self-documenting by default; comments are off the table.** Apply the Core Principle. The default is zero comments — let names, structure, and types carry the meaning. A restating comment is a defect to delete, not a habit to feed.
- **Remove comment noise from the whole file you open, not just the lines you touched.** When you open a file to change it, sweep it for comment noise and delete it — a one-line fix is reason enough to clean the rest. Treat each of these as noise to delete on sight: per-line narration (`# loop over items`, `// return the result`), section-banner comments (`// ===== Setup =====`, `# --- validation ---`), commented-out code, docstrings that only restate the signature, and any comment that merely repeats what a name, constant, or type already says. Deletion is the cleanest change — a line removed is a line that can never lie. Stay surgical about *logic*: do not rewrite functions you were not asked to change, and do not go hunting for unrelated dead code — only the comment noise is in scope. A genuine *why*-comment (unit footgun, workaround, ordering constraint) stays; apply the Core Principle's escape hatch before removing anything that reads like a warning.
- **Prefer immutability.** Use `const` in JS, avoid reassignment in Python. Only mutate when you have a good reason.

---

## 5. Reliability & Resilience: Fail Fast, Recover Gracefully

**Why it matters:** Systems that tolerate partial failure stay usable. Systems that don't, cascade into outages.

**Shared rules:**
- **Retry transient errors only** — network timeouts, 5xx, rate limits. Use exponential backoff.
- **Make writes idempotent** — idempotency keys, dedup tables, version checks on POST/PUT.
- **Circuit breakers** around fragile dependencies — third-party APIs, external services.
- **Propagate deadlines end-to-end** — timeout headers, AbortSignal (JS), or deadline context (Python).
- **Handle async errors** — no floating promises, no swallowed rejections.

---

## 6. Optimize Database Interactions

**Why it matters:** Database queries are usually the bottleneck. One bad query can take down a service.

**Shared rules:**
- **Bulk operations** for multi-record creates/updates — never loop-and-insert.
- **Select only what you need** — field selection, column projection. Don't fetch entire rows.
- **Eager loading** to prevent N+1 — use joins/includes/populate, not sequential queries.
- **Push computation to the DB** — aggregations, full-text search, window functions belong in SQL, not in application code.
- **Transactions** for multi-step writes that must succeed or fail together.

**Language-specific patterns:** See reference files for SQLAlchemy (Python) and Prisma/Drizzle (JavaScript) examples.

---

## 7. Use Named Boolean Validation

**Why it matters:** A complex inline condition forces the reader to mentally evaluate it. A named variable documents intent.

**Shared rules:**
- Extract complex `if` conditions into a named boolean variable.
- The variable name should describe the business rule, not the technical check.
- Prefer `const isEligibleForDiscount = ...` over `if (user.age > 65 && user.yearsActive > 5 && ...)`.

---

## 8. Avoid Magic Numbers

**Why it matters:** A raw number in code has no context. A named constant explains *why* that value exists.

**Shared rules:**
- Extract hardcoded numbers into named constants.
- Constants should live in a config file or at the top of the module.
- The constant name should describe the business meaning, not the value itself.

---

## 9. Type Safety Strategy

**Why it matters:** Runtime validation catches bad data at the boundary. Static types catch logic bugs during development. You need both.

**Shared rules:**
- **Runtime validation** at system boundaries (API, queue, env, third-party responses) — this is where untrusted data enters.
- **Static types** for internal logic — function signatures, domain objects, protocols/interfaces.
- **Flow:** External Source → Runtime Schema Validation → Typed Internal Logic.
- Never bypass the type system with escape hatches (`Any`, `any`, type assertions) unless you have a documented reason.

**Language-specific patterns:** See reference files for Pydantic + mypy (Python) and Zod + TypeScript (JavaScript).

---

## 10. Event-Driven / Decoupled Architecture

**Why it matters:** Direct calls between domains create coupling. Events keep components independent and evolvable.

**Shared rules:**
- Use an internal event bus or emitter for side effects between domains — not direct function calls.
- Define typed event payloads with schemas.
- Register handlers separately from the business logic that emits events.
- Ensure handlers have proper error handling — errors in handlers should not crash the emitter.

---

## 11. Configuration: Never Read OS Envs Directly

**Why it matters:** OS env vars are strings — a raw `"false"` is truthy, a missing var is `None`/`undefined`, and a misspelled name is silently ignored. Reading them ad-hoc inside business logic scatters these footguns across the codebase and turns a misconfigured variable from a loud startup crash into a quiet, request-time bug.

**Shared rules:**
- **Never read OS envs directly in business/domain code.** No `os.getenv(...)` / `os.environ[...]` (Python) or `process.env.X` (JS/TS) outside the single config module.
- **Centralize every env read in one config object**, built from a validated schema. One source of truth, typed and immutable.
- **Build it once, at service bootstrap** — a missing or malformed variable crashes the process immediately, not on the first request that needs it.
- **Inject the config object** into the code that needs it. Downstream code reads typed fields (`config.port`, `config.enable_feature_flag`), never the environment.
- **Coerce and validate at construction** — strings become booleans, numbers, and enums through the schema, which is what kills the `"false"`-is-truthy class of bug.

**Language-specific patterns:** Python → pydantic `BaseSettings` if the repo has it, otherwise a `dataclass` config loaded once at bootstrap (`references/python-guidelines.md`). JS/TS → a Zod schema parsed once at startup (`references/javascript-guidelines.md`).

---

## 12. Name Clients by Role, Never by Vendor

**Why it matters:** A client named `SupabaseClient` or `RedisClient` stamps a vendor's identity onto every file that imports it. Replacing that vendor then means editing every caller — and the name being everywhere is exactly what lets vendor-shaped assumptions spread everywhere too. A role name keeps the vendor's identity inside one module, so a replacement is a change to that module instead of a sweep across the codebase.

**Shared rules:**
- **Name the capability, not the product.** `DatabaseClient`, `CacheClient`, `StorageClient`, `AuthClient`, `QueueClient`, `EmailClient`, `PaymentsClient`, `VoiceClient` — never `SupabaseClient`, `RedisClient`, `S3Client`, `ClerkClient`, `SendgridClient`, `StripeClient`.
- **The rule covers every symbol, not just classes.** Modules and filenames, type aliases, factory functions, DI providers, app-state keys, test doubles, and wire-shape types all follow it: `supabase_client()` → `database_client()`, `capacitorStorage` → `persistentStorage`, `SupabaseQuestion` → `QuestionRow`, `_FakeSupabase` → `_FakeDatabase`, `app.state.supabase` → `app.state.database`.
- **The vendor's name is allowed in exactly one place: inside the adapter module.** Its SDK import, its construction call, and its reading of the vendor's credentials live there. Every other module imports the role name and never learns which product is behind it.
- **Callers must not name the vendor either.** If seven handlers still declare `supabase: DatabaseClient`, the rename bought nothing — the parameter is `db`. Grep for the vendor's name when you are done: every hit outside the adapter is a leak.
- **A rename alone does not buy swappability — the adapter's surface does.** The seam is real only where the operations are named in your domain's terms (a repository, a port, a service method). Renaming the type is what makes that seam visible and confines the vendor import; it is a first step, not the finish line, and it should be paired with a domain-shaped layer over the vendor's calls.
- **Never add a wrapper that only forwards.** A `DatabaseClient` whose methods hand back the vendor SDK's own query builders or response types is a layer with no boundary — pure ceremony, and callers stay just as coupled. Prefer the role-named alias plus a domain-shaped layer over a passthrough facade.
- **Carve-outs.** The vendor's own credentials and config keys keep their real names (`SUPABASE_URL` is a real environment variable; renaming it breaks the deploy) — they belong to the adapter's config and are read only by the adapter. A tool whose subject genuinely *is* that product (a seed script driving the Supabase CLI, a migration runner) names it. And a vendor type passed between two files of the same adapter is fine, as long as the adapter's public surface stays role-shaped.

**Language-specific patterns:** See reference files for the Python adapter/alias pattern and the TypeScript module-boundary pattern.

---

## 13. Layer Contracts: DTOs Between Layers

**Why it matters:** When layers exchange raw dicts/objects/rows, the contract between them lives only in the reader's head — a typo'd key surfaces as a runtime `None` three layers away, every consumer re-derives the shape by hand, and nothing says which fields exist until the code runs. A declared DTO makes the contract explicit, named, and checkable. That is what keeps services easy to understand and maintain as they grow: the DTO is the documentation, and the type checker enforces it.

**Shared rules:**
- **Layers communicate through declared DTOs, not raw dicts, tuples, or untyped objects.** A repository returns DTOs; a service consumes DTOs and returns DTOs; the API response is a fixed DTO. Raw dicts are allowed in exactly two places: data entering your process (where the DTO is constructed from them) and payloads leaving your process at an SDK/protocol boundary (where the DTO is serialized back).
- **Schemas live in a dedicated schemas module, never mixed with behavior code.** A schema class defined inside a routes file, a service, a pipeline, an app bootstrap (`main.py`/`app.ts`), or any module that also holds logic is a defect — move it to the package's schemas module. In Python that file is named `schemas.py` (one per package; rename `models.py` to `schemas.py` when you touch it). In JS/TS it is `schemas.ts` (or a `schemas/` folder). When a single package accumulates schemas for several domains, promote `schemas.py` to a `schemas/` package — one file per domain, with a fixed internal order: row/internal DTOs first, request models next, response models last.
- **Internal DTOs and wire DTOs are distinct.** Internal DTOs speak the code's vocabulary (snake_case, the database's field names); wire DTOs carry the API contract (camelCase aliases, only what the client sees). Map between them at the edge — never let wire aliases or response-only fields leak into domain logic.
- **A DTO declares shape, not behavior.** No business logic on it; a derived property is the ceiling.
- **A new field flows DTO-first.** Add it to the DTO; the type checker then finds every layer that must adapt. That is the payoff — change ripples through names, not through string keys.
- **Validate where untrusted data enters.** DB rows and third-party payloads are parsed into DTOs at construction (the boundary); DTOs your own code builds are typed at birth and trusted downstream.

**Language-specific patterns:** Python → pydantic `BaseModel` with `ConfigDict(frozen=True)`, or a frozen `dataclass` when pydantic is not already a dependency. JS/TS → Zod object schemas with `z.infer<>` types. See `references/python-guidelines.md` and `references/javascript-guidelines.md`.

---

## 14. Logging: Structured Events, Never Free-Text

**Why it matters:** A log line built by string interpolation (`logger.info(f"user {id} did {thing}")`) cannot be searched, filtered, alerted on, or charted — the facts are welded into prose. Structured logs make each fact a queryable field, which is the entire point of logging in a service.

**Shared rules:**
- **Every log call is an event name plus key-value pairs — never an interpolated or concatenated message.** `logger.info("order_completed", order_id=order_id, total_cents=total_cents)` — the event name is a snake_case verb phrase; the facts ride as keyword arguments. An f-string inside a log call is a defect on contact.
- **No free-text logs, no `print`.** `print(...)` in application code is a defect (log it through the logger instead). Same for bare `logging.info("...")` string-only calls.
- **One logger per module**, obtained from the project's logging setup (`get_logger(__name__)`), never ad-hoc `logging.getLogger` scattered with different configuration.
- **Configure logging once, at service bootstrap** — one `logging_config` module decides the format (JSON in production, human-readable console in development) and routes stdlib/framework logs through the same pipeline. No module configures logging itself.
- **Errors log as `logger.exception(event_name, ...)`** inside the `except` block — the traceback attaches automatically; never `logger.error(str(error))`.
- **Log meaningful events, not narration.** One event per business occurrence (request handled, job completed, ingestion finished) with the identifiers and counts that describe it. A function that logs every loop iteration is noise.
- **Logging never replaces error state.** A log records what happened; the return value / raised error still carries the failure (see § 2).

**Language-specific patterns:** Python → structlog (`references/python-guidelines.md` § 12). JS/TS → pino or the framework's structured logger with the same shape.

---

## Self-Review Checkpoint

Before you finish editing, scan what you wrote and answer these questions. Each one names a change to make in the code — never a comment to leave behind.

1. **Count your comments. Is the count zero?** If not, walk each comment through the closed set: could a better name, an extracted function, a named constant, or a stronger type say it instead? Make that change and delete the comment. A comment survives only if the line would be *misleading or dangerous* without it — the escape hatch, not the rule.
2. **Did you sweep the whole file you opened, not just the lines you changed?** Scan for leftover per-line narration, section banners, commented-out code, restating docstrings, or comments a name/constant/type already covers — and delete them. A genuine *why*-comment stays (escape hatch); the rest goes.
3. **Is any name generic or an unexplained abbreviation?** (`data`, `item`, `temp`, `result`, `value`, `obj`, `resp`, `info`, and project-local shorthand like `kb`, `rrf`, `cfg`) — rename it to reveal intent. If a name needs a comment to be understood, the name is wrong.
4. **Did you bring the whole function you edited up to standard — not just the changed line?** Scan the rest of that function for magic numbers still inline, complex conditions still unnamed, errors still returned as a silent `None`/`null`, and nesting you could flatten — and apply the guideline for each before you finish.
5. **Did any code you add read an OS env directly?** Any `os.getenv` / `os.environ` (Python) or `process.env.X` (JS/TS) outside the single config module is a defect. Move the value into the validated config object that is built once at bootstrap, and read the typed field off that object instead.
6. **Does any name you touched carry a vendor's name?** Grep the files you changed for the product (`supabase`, `redis`, `clerk`, `stripe`, `s3`, …). Outside the one adapter module — and outside the credential and vendor-CLI carve-outs — every hit is a defect: rename it to the capability (`DatabaseClient`, `CacheClient`), including the parameter names at the call sites.
7. **Did any layer hand another layer a raw dict or untyped object where a declared DTO belongs?** Trace the values your code passes between repository, service, and router layers. A dict crossing a layer boundary (rather than entering or leaving the process) is a defect — replace it with the domain's DTO, and if no such DTO exists, that gap is the finding.
8. **Is any schema defined outside a schemas module?** Grep the files you changed for schema definitions (`class X(BaseModel)` in Python, `z.object` / interface declarations in JS/TS) living in routes, services, pipelines, or `main`/app-bootstrap files — every hit is a defect. Move it to the package's `schemas.py` (Python) or `schemas.ts` (JS/TS), and import it from there.
9. **Is any domain error defined outside the module's errors file — or raised as a bare builtin?** Grep the files you changed for exception classes (`class X(Exception)` / `class X(Error)`) and bare raises (`raise ValueError(`, `throw new Error(`). A domain failure declared outside the module's `errors.py` / `errors.ts`, or thrown as an unnamed builtin, is a defect: name it and move it to the errors file.
10. **Is any log call unstructured?** Scan the files you changed for f-strings or concatenation inside `logger.*(`, string-only log messages, and `print(`. Every hit is a defect — rewrite as `event_name` plus key-value pairs through the project's logger.
11. **Is every file where a reader would predict?** A schema outside `schemas.py`, a domain error outside `errors.py`, orchestration inside a route or wiring file instead of `service.py`, a file whose name needs "and" or says mechanics instead of domain (`utils`, `helpers`, `common`), or a module laid out differently from its siblings — each is a defect. Move or rename it to match the pattern the project already established.

The bar: a reader who knows the language but not your project follows the code without reading a single comment, and every function you touched reads like it was written to these guidelines on purpose — not patched mid-flight.

---

## Quick Reference: When to Load Which File

| You're working in... | Load this reference |
|---|---|
| Python backend | `references/python-guidelines.md` |
| JavaScript / TypeScript project | `references/javascript-guidelines.md` |
| Full-stack (Python + JS) | Both references |
| Unsure? Check for `pyproject.toml` or `package.json` | Load the matching one |
