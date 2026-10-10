# Python Codebase Change Guidelines

Language-specific patterns and examples for Python projects. Read this after the shared principles in `SKILL.md`. Start with **Self-Documenting Code & Comments** — it governs every example below. Apply every section to the **whole function you edit**, not just the line you changed — if you touched the function, bring all of it up to standard.

---

## Table of Contents

- [Self-Documenting Code & Comments](#self-documenting-code--comments) — the governing rule
1. [Data Handling with Pydantic](#1-data-handling-with-pydantic)
2. [Error Management](#2-error-management)
3. [Function Scope](#3-function-scope)
4. [Code Structure](#4-code-structure)
5. [Reliability & Resilience](#5-reliability--resilience)
6. [Database Interactions](#6-database-interactions)
7. [Named Boolean Validation](#7-named-boolean-validation)
8. [Avoid Magic Numbers](#8-avoid-magic-numbers)
9. [Type Safety: Pydantic + Type Hints](#9-type-safety-pydantic--type-hints)
10. [Event-Driven Architecture](#10-event-driven-architecture)
11. [Error Handling Pattern](#11-error-handling-pattern)
12. [Logging with structlog](#12-logging-with-structlog)
13. [Configuration: Never Read OS Envs Directly](#13-configuration-never-read-os-envs-directly)
14. [Vendor-Neutral Client Names](#14-vendor-neutral-client-names)
15. [Layer Contracts: DTOs Between Layers](#15-layer-contracts-dtos-between-layers)

---

## Self-Documenting Code & Comments

This restates the Core Principle from `SKILL.md` with Python examples. Apply it to every line you write.

**The default is no comment.** Write code as if comments did not exist in the language. When a line feels like it needs explaining, exhaust the closed set of code-level tools first — (1) rename it, (2) extract a function or variable, (3) name the constant, (4) strengthen the type. A comment is not step five; it is not in the set. If you are about to write one, you stopped too early.

Restating comments rephrase the code next to them. They add nothing and rot into lies. Delete them on contact, anywhere in a file you open — whether you wrote them or inherited them. When you open a file to change it, sweep the whole file for noise, not just the lines you touched: per-line narration (`# loop over items`), section banners (`# --- validation ---`), commented-out code, docstrings that restate the signature, and comments a name, constant, or type already covers. (A genuine *why*-comment stays — see the escape hatch below.)

```python
active_subscriptions = [s for s in subscriptions if s.is_active]  # filter to active ones
monthly_total = sum(s.price for s in active_subscriptions)  # sum the prices
return monthly_total  # return the total
```

The code already said all three of those things:

```python
active_subscriptions = [subscription for subscription in subscriptions if subscription.is_active]
monthly_total = sum(subscription.price for subscription in active_subscriptions)
return monthly_total
```

When a comment exists because a type is too weak to express the value, strengthen the type and delete the comment:

```python
status: str  # "SUCCESS" | "FAILED"            # weak type forced a comment
status: Literal["SUCCESS", "FAILED"]  # the type now says it — comment gone
```

A docstring earns its place only when it states a contract or invariant the signature cannot. A function whose name, parameter types, and return type already say everything needs no docstring:

```python
def transfer_funds(source_id: str, target_id: str, amount: Decimal) -> Result: ...
```

**The one escape hatch.** A comment is allowed only when the code would be *misleading or dangerous* without it — a unit footgun, a workaround, a constraint the code cannot encode. This is rare; if you reached for it easily, it does not qualify:

```python
def parse_amount(raw: str) -> Decimal:
    # Stored as dollars; the ledger requires cents, so we never round here.
    return Decimal(raw)
```

Without that note, a future reader might "clean up" `Decimal(raw)` and introduce rounding. The note encodes a constraint. Read it as the shape of an acceptable comment — and as proof of how rare the bar is. Almost nothing you write clears it.

---

## 1. Data Handling with Pydantic

Use Pydantic models as strict data contracts at every system boundary.

```python
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class OrderItemSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    quantity: int
    unit_price: Decimal
    discount_percentage: Decimal = Decimal("0.0000")


def process_order_item(raw_data: dict) -> OrderItemSchema:
    try:
        return OrderItemSchema(**raw_data)
    except ValidationError as error:
        raise OrderValidationError("Invalid order item data", error) from error
```

**Key points:**
- Use `ConfigDict(frozen=True)` for immutable DTOs where possible.
- Use `Decimal` for monetary values — never `float`.
- All fields must have explicit types. No `Any`.
- Validation happens once, at the entry point. Downstream code trusts the validated object.

**Checklist:**
- [ ] Consolidate scattered type checks into a single Pydantic model at the entry point.
- [ ] Replace manual `int(variable)` / `str(variable)` conversions with Pydantic's type coercion.
- [ ] Remove `if data.get("key") is not None:` guards on fields that the schema requires.

---

## 2. Error Management

Return structured state objects. Never log and forget.

```python
from dataclasses import dataclass
from typing import Literal, TypeVar

T = TypeVar("T")


@dataclass
class Result:
    """Structured return type for operations that can fail."""

    status: Literal["SUCCESS", "FAILED"]
    data: T | None = None
    errors: list[str] | None = None


def transfer_funds(source_id: str, target_id: str, amount: Decimal) -> Result:
    try:
        source = account_repository.find_by_id(source_id)
        if not source:
            return Result(status="FAILED", errors=[f"Source account not found: {source_id}"])

        target = account_repository.find_by_id(target_id)
        if not target:
            return Result(status="FAILED", errors=[f"Target account not found: {target_id}"])

        has_insufficient_funds = source.balance < amount
        if has_insufficient_funds:
            return Result(status="FAILED", errors=["Insufficient funds"])

        source.balance -= amount
        target.balance += amount
        account_repository.save_all([source, target])

        return Result(status="SUCCESS", data={"source_balance": source.balance})
    except DatabaseError as error:
        logger.exception("transfer_failed", source_id=source_id, target_id=target_id)
        return Result(status="FAILED", errors=[str(error)])
```

**Checklist:**
- [ ] Find `except` blocks that only log. Make them update a return state.
- [ ] Replace functions that return data on success and `None` on failure with `Result`.

---

## 3. Function Scope

No nested functions. Extract to module scope.

```python
# ❌ Avoid — nested function captures outer scope
def process_orders(orders: list[dict]) -> list[dict]:
    def extract_total(order: dict) -> Decimal:
        return Decimal(order.get("total", "0"))

    return sorted(orders, key=extract_total, reverse=True)


# ✅ Prefer — module-level helper with explicit params
def _extract_order_total(order: dict) -> Decimal:
    return Decimal(order.get("total", "0"))


def process_orders(orders: list[dict]) -> list[dict]:
    return sorted(orders, key=_extract_order_total, reverse=True)
```

**Checklist:**
- [ ] Move nested `def` to module-level helpers or `@staticmethod`.
- [ ] Replace closures with explicit parameters.
- [ ] Add tests for extracted helpers.

---

## 4. Code Structure

Guard clauses, descriptive names, small functions.

```python
# ❌ Avoid — nested, unclear names
def process(d):
    if d:
        if d.get("type") == "email":
            if d.get("priority") == "high":
                send_urgent_email(d)
            else:
                send_normal_email(d)


# ✅ Prefer — guard clauses, descriptive names
def process_notification(notification: dict) -> None:
    if not notification:
        return

    is_email_type = notification.get("type") == "email"
    if not is_email_type:
        return

    is_high_priority = notification.get("priority") == "high"
    if is_high_priority:
        send_urgent_email(notification)
        return

    send_normal_email(notification)
```

**Checklist:**
- [ ] Functions longer than 20-25 lines? Break them down.
- [ ] Nested `if/else`? Flatten with guard clauses.
- [ ] Variables named `data`, `item`, `x`, `temp`? Rename them.
- [ ] Make code self-documenting — delete comments that restate the code.

---

## 5. Reliability & Resilience

Retries, idempotency, circuit breakers, deadlines.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TransientError),
)
def call_payment_gateway(payload: PaymentPayload) -> GatewayResponse:
    response = httpx.post(
        PAYMENT_GATEWAY_URL,
        json=payload.model_dump(),
        headers={"Idempotency-Key": payload.idempotency_key},
        timeout=30.0,
    )
    response.raise_for_status()
    return GatewayResponse(**response.json())
```

**Checklist:**
- [ ] Add idempotency keys to POST/PUT operations.
- [ ] Wrap flaky external calls with retries + backoff.
- [ ] Propagate timeouts via `timeout` params or deadline context.

---

## 6. Database Interactions

Bulk operations, eager loading, push computation to DB.

```python
from sqlalchemy import select
from sqlalchemy.orm import joinedload, load_only


def get_active_users_with_orders(session: Session) -> list[User]:
    statement = (
        select(User)
        .options(
            load_only(User.id, User.email, User.is_active),
            joinedload(User.orders),
        )
        .where(User.is_active == True)
    )
    return list(session.execute(statement).scalars().unique())


def bulk_create_order_items(session: Session, items: list[dict]) -> None:
    session.bulk_insert_mappings(OrderItem, items)
```

**Checklist:**
- [ ] Loops with queries inside? Replace with a single query.
- [ ] Fetching all columns? Use `load_only`.
- [ ] Manual aggregation in Python? Use SQL `func.count()`, `func.sum()`, etc.

---

## 7. Named Boolean Validation

```python
# ❌ Avoid
if user.age > 65 and user.years_active > 10 and not user.has_pending_violations:
    apply_senior_discount(user)

# ✅ Prefer
is_eligible_for_senior_discount = (
    user.age > SENIOR_AGE_THRESHOLD
    and user.years_active > MIN_YEARS_FOR_DISCOUNT
    and not user.has_pending_violations
)
if is_eligible_for_senior_discount:
    apply_senior_discount(user)
```

---

## 8. Avoid Magic Numbers

```python
# ❌ Avoid
if attempt_count > 3:
    lock_account(user)

# ✅ Prefer
MAX_LOGIN_ATTEMPTS = 3
exceeded_max_login_attempts = attempt_count > MAX_LOGIN_ATTEMPTS
if exceeded_max_login_attempts:
    lock_account(user)
```

---

## 9. Type Safety: Pydantic + Type Hints

- **Pydantic:** Runtime validation at boundaries (API payloads, config, queue messages).
- **Type hints + mypy:** Static safety for internal logic (function signatures, protocols).
- **Flow:** External Source → Pydantic Model (runtime) → Typed Logic (static).

```python
from typing import Protocol


class NotificationSender(Protocol):
    """Static type for internal dependency injection — no Pydantic needed."""

    def send(self, recipient: str, message: str) -> None: ...


class EmailNotificationSender:
    """Concrete implementation — validated at creation, trusted internally."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def send(self, recipient: str, message: str) -> None:
        smtp_send(
            host=self._config.smtp_host,
            port=self._config.smtp_port,
            recipient=recipient,
            message=message,
        )
```

**Checklist:**
- [ ] Pydantic models at every trust boundary.
- [ ] Type hints on all function signatures.
- [ ] No `Any` — use proper types or `object`.

---

## 10. Event-Driven Architecture

```python
from pydantic import BaseModel


class OrderPlacedEvent(BaseModel):
    order_id: str
    customer_id: str
    total: Decimal


def on_order_placed(event: OrderPlacedEvent) -> None:
    """Handler registered in event_handlers.py — decoupled from order domain."""
    send_order_confirmation_email(event.customer_id, event.order_id)
    update_inventory(event.order_id)
```

Emit from the order service:

```python
event_bus.emit(
    "order_placed",
    OrderPlacedEvent(
        order_id=order.id,
        customer_id=order.customer_id,
        total=order.total,
    ),
)
```

**Checklist:**
- [ ] Domains calling each other directly? Refactor to event bus.
- [ ] Event payloads as Pydantic models.
- [ ] Handlers in a dedicated registration module.

---

## 11. Error Handling Pattern

Custom error hierarchy with consistent structure.

**Placement rule: a module's domain errors live in its own `errors.py`** — never declared inside a routes file, a service, a pipeline, or any module that also holds behavior. Each package that raises its own errors gets `errors.py`:

```
app/ingestion/errors.py           # IngestionError, UnknownChunkerError
app/rag_strategies/errors.py      # UnknownStrategyError
app/llm/errors.py                 # EmbeddingCountMismatchError
```

A domain failure raised as a bare builtin (`raise ValueError(f"unknown chunker: {name}")`) is a defect — name it and put it in the module's `errors.py`. Subclass the builtin it replaces (`class UnknownChunkerError(ValueError)`) when callers may legitimately catch the builtin, so the fix stays backward-compatible.

```python
class AppError(Exception):
    """Base error for all domain-specific exceptions."""

    def __init__(
        self,
        message: str,
        code: str,
        context: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}


class ValidationError(AppError):
    def __init__(self, message: str, details: object) -> None:
        super().__init__(message, code="VALIDATION_ERROR", context={"details": details})


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            context={"resource": resource, "id": resource_id},
        )
```

**Checklist:**
- [ ] Exception classes declared in routes/services/pipelines? Move to the module's `errors.py`.
- [ ] Domain failures raised as bare `ValueError`/`RuntimeError`? Name them (`UnknownChunkerError(ValueError)`) in `errors.py`.

---

## 12. Logging with structlog

Shared rule: **SKILL.md § 14**. Every log call is an event name plus key-value pairs — an f-string inside a log call is a defect, and `print` never appears in application code.

One `logging_config` module configures structlog once at bootstrap (JSON renderer in production, `ConsoleRenderer` in development) and routes stdlib logging — uvicorn included — through the same `ProcessorFormatter`; call it from the FastAPI lifespan. Every other module only does `logger = get_logger(__name__)`:

```python
from app.logging_config import get_logger, set_task_context, clear_task_context

logger = get_logger(__name__)

logger.info("order_processed", order_id=order_id, total=float(total))
```

Use `logger.exception()` for errors — it auto-attaches the traceback:

```python
try:
    process_payment(order)
except PaymentError:
    logger.exception("payment_failed", order_id=order_id)
```

**Auto-fields (never add manually):** `event`, `filename`, `lineno`, `func_name`, `module`, `level`, `timestamp`, `task_name`

**Checklist:**
- [ ] Any f-string or `+` concatenation inside a `logger.*(` call? Rewrite as event name + keyword arguments.
- [ ] Any `print(` in application code? Replace with a structured log event.
- [ ] Logging configured in exactly one module, called once at bootstrap — nowhere else.

**Celery tasks:**
```python
@celery_app.task
def my_task(item_id: str) -> None:
    set_task_context("my_task")
    try:
        logger.info("processing_item", item_id=item_id)
    finally:
        clear_task_context()
```

---

## 13. Configuration: Never Read OS Envs Directly

All env access flows through one validated config object, built once at bootstrap and injected. No `os.getenv` or `os.environ` in business code.

**If the repo has pydantic** — use `pydantic-settings` `BaseSettings`. It reads, coerces, and validates env into a typed object at construction:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", frozen=True)

    environment: Literal["development", "production"]
    database_url: str
    port: int = 8000
    db_pool_size: int = 10
    enable_feature_flag: bool = False
```

**If the repo has no pydantic** — use a frozen `dataclass` loaded once at startup, with explicit validation and coercion at the boundary:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: Literal["development", "production"]
    database_url: str
    port: int
    enable_feature_flag: bool


def load_settings() -> Settings:
    environment = os.environ.get("APP_ENVIRONMENT")
    if environment not in ("development", "production"):
        raise ConfigError("APP_ENVIRONMENT must be 'development' or 'production'")

    database_url = os.environ.get("APP_DATABASE_URL")
    if not database_url:
        raise ConfigError("APP_DATABASE_URL is required")

    return Settings(
        environment=environment,
        database_url=database_url,
        port=int(os.environ.get("APP_PORT", "8000")),
        enable_feature_flag=_as_bool(os.environ.get("APP_ENABLE_FEATURE_FLAG", "false")),
    )


def _as_bool(raw: str) -> bool:
    return raw.lower() == "true"
```

Build once at startup, then inject — never read the environment inside a function:

```python
# ❌ Avoid — reads env ad-hoc; "false" stays a truthy string, a typo is silently ignored
def get_pool_size() -> int:
    return int(os.getenv("DB_POOL_SIZE", "10"))


# ✅ Prefer — typed, validated once at startup, passed in
settings = Settings()


def get_pool_size(settings: Settings) -> int:
    return settings.db_pool_size
```

**Key points:**
- The config object lives in a single module (e.g. `app/config.py`). It is the only place `os.environ` appears.
- Build it once at startup (FastAPI lifespan, Celery bootstrap, `if __name__ == "__main__"`), then inject it — not re-read per request or per function.
- Booleans and numbers come out of the schema already coerced. No `== "true"` checks or `int(...)` calls in domain code.

**Checklist:**
- [ ] Any `os.getenv` / `os.environ` outside the single config module? Move it into `Settings`.
- [ ] Config built once at startup and injected — not re-read inside functions.
- [ ] Booleans read through the schema/coercion, never a raw string comparison in domain code.

---

## 14. Vendor-Neutral Client Names

Shared rule: **SKILL.md § 12**. One module names the vendor; every other module imports a role name.

```python
# ❌ Avoid — the product is in the alias, the provider, the app state, and every caller's signature
from supabase import AsyncClient, acreate_client


def supabase_client(request: Request) -> AsyncClient:
    return cast("AsyncClient", request.app.state.supabase)


SupabaseClient = Annotated[AsyncClient, Depends(supabase_client)]


async def get_certifications(supabase: SupabaseClient): ...  # router
async def get_active_certifications(supabase: AsyncClient): ...  # repository
```

```python
# ✅ Prefer — app/core/db.py is the only module that names the vendor
from supabase import AsyncClient, acreate_client

DatabaseClient = AsyncClient
"""Role name for the connected client. The SDK is named here and nowhere else, so replacing the
database is a change to this module rather than to every repository."""


async def create_database_client() -> DatabaseClient:
    return await acreate_client(settings.supabase_url, settings.supabase_service_role_key)


def database_client(request: Request) -> DatabaseClient:
    return cast("DatabaseClient", request.app.state.database)


Database = Annotated[DatabaseClient, Depends(database_client)]
```

```python
# routers — take the injected dependency
from app.core.db import Database


async def get_certifications(db: Database): ...


# repositories — annotate the plain type, no vendor import anywhere in the file
if TYPE_CHECKING:
    from app.core.db import DatabaseClient


async def get_active_certifications(db: DatabaseClient) -> list[dict]: ...
```

**Key points:**
- Two aliases, one vendor import: `DatabaseClient` is the type, `Database` is the dependency FastAPI resolves. Handlers take the dependency; repositories and services take the plain type.
- `settings.supabase_url` and `SUPABASE_SERVICE_ROLE_KEY` keep their names — credentials are the vendor's coordinates, and they are read only by the adapter.
- Test doubles follow the rule: `_FakeDatabase` overriding `database_client`, not `_FakeSupabase` overriding `supabase_client`.
- Do **not** wrap `AsyncClient` in a class whose methods just hand back `.table(...)` builders. The seam that actually makes the database replaceable is the repository layer, where calls are named `get_active_certifications` rather than `select`.

**Checklist:**
- [ ] `grep -rn "supabase" app/ | grep -v core/db.py` returns nothing but config keys.
- [ ] No handler, repository, or service parameter named after the product.
- [ ] `app.state` keys and factory functions named by role (`app.state.database`, `create_database_client`).
- [ ] No passthrough facade added around the SDK.

---

## 15. Layer Contracts: DTOs Between Layers

Shared rule: **SKILL.md § 13**. Repositories, services, and routers exchange declared DTOs — pydantic models (`ConfigDict(frozen=True)`) when pydantic is already a dependency, frozen `@dataclass`es when it is not. Raw dicts appear in exactly two places: where data enters the process (DTO construction) and where a payload leaves it at an SDK boundary (serialization).

Schemas live in a dedicated `schemas.py` — never defined alongside routes, services, pipelines, or app bootstrap. One `schemas.py` per package; when a package holds schemas for several domains, promote it to a `schemas/` package, one module per domain, models in a fixed order — row/internal DTOs first, request models next, response models last:

```
# single-domain package: everything in one schemas.py
app/knowledge_bases/schemas.py     # SourceRef → ConceptDoc → KnowledgeBundle

# multi-domain package: promoted to a schemas/ package
app/schemas/
    questions.py    # QuestionRow → QuestionOut
    sessions.py     # SessionRow → SessionStartRequest → SessionStartOut
    tags.py
```

A `BaseModel` declared inside `routes.py`, `pipeline.py`, or `main.py` is a defect on contact — move it to the package's `schemas.py` and import it from there, even mid-unrelated-change.

The repository validates rows into DTOs at the data boundary — stored-data quirks get normalized here too:

```python
class QuestionRow(RowModel):
    id: str
    title: str
    options: list[OptionRow] = []

    @field_validator("options", mode="before")
    @classmethod
    def decode_options(cls, raw: object) -> object:
        return json.loads(raw) if isinstance(raw, str) else raw


async def get_questions_page(db: DatabaseClient, offset: int, limit: int) -> list[QuestionRow]:
    response = (
        await db.table("questions")
        .select(QUESTION_COLUMNS)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [QuestionRow.model_validate(row) for row in rows(response)]
```

Services and mappers read attributes — the scattered `row.get("key")` defensive reads disappear, because the schema guarantees the field:

```python
def to_question_preview(row: QuestionRow) -> QuestionOut:
    return QuestionOut(
        id=row.id,
        title=row.title,
        options=[OptionPreviewOut.model_validate(option) for option in row.options],
    )
```

The router maps the final DTO onto the fixed wire model; `response_model` remains the API contract:

```python
@router.get("", response_model=QuestionsPageOut)
async def get_questions(db: Database, page: int = FIRST_PAGE):
    question_rows = await questions_repo.get_questions_page(db, offset, limit)
    return QuestionsPageOut(
        items=[to_question_preview(row) for row in question_rows], pagination=pagination
    )
```

**Key points:**
- One frozen base for all internal DTOs; wire models keep their own base and stay untouched — mappers convert between them (`QuestionOut.model_validate(row_dto)` via `from_attributes`).
- A write DTO serializes back to a plain dict exactly once, at the SDK boundary: `row.model_dump(mode="json")`. Never `by_alias=True` on SDK payloads — wire aliases must not reach the database.
- Internal DTOs keep the database's field names and representations; do not "improve" a pass-through `str` timestamp into `datetime` — re-serialization silently changes what the client receives.
- A new DB column flows DTO-first: add the field, then follow the type errors to every layer that must adapt.

**Checklist:**
- [ ] Repository return annotations are DTO types (`list[QuestionRow]`), not `dict` / `list[dict]`.
- [ ] No `row["key"]` or `row.get("key")` on data crossing a layer boundary — attribute access only.
- [ ] No hand-built response dicts in services or routers; mappers build the wire models.
- [ ] SDK-boundary payloads are plain dicts, serialized from DTOs inside the repository.
- [ ] No `class X(BaseModel)` defined outside a `schemas.py` module — grep the files you touched; move strays into the package's `schemas.py`.
