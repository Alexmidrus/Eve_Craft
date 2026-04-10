# AGENTS.md

## Purpose

This repository uses architecture option 2: a domain-oriented modular monolith for a desktop application built with `PySide6`, `SQLite`, and `SQLAlchemy`.

These instructions should guide every future implementation task in this project unless the user explicitly asks to change the architecture.

## Core Architectural Decision

Build one desktop application with clear module boundaries instead of a set of loose scripts.

The project is divided into four main areas:

- `app`: application bootstrap, wiring, navigation, configuration, module registry
- `modules.industry`: industry-related business modules
- `modules.market`: market-related business modules
- `platform`: shared technical services and integrations
- `shared`: small, truly reusable cross-module primitives

## Mandatory Structure

All new code should be added under the target structure below:

```text
src/iph2/
  app/
  shared/
  platform/
  modules/
    industry/
    market/
  resources/
```

If the repository does not yet contain this structure, create new code directly in this target layout instead of adding more root-level scripts.

## Module Design Rules

Each business feature must be implemented as a self-contained module package.

Examples:

- `modules/industry/blueprint_calc/`
- `modules/industry/profit_finder/`
- `modules/industry/projects/`
- `modules/industry/mining/`
- `modules/industry/planetary/`
- `modules/market/orders/`
- `modules/market/day_trading/`
- `modules/market/interregional_trade/`

Each feature module should normally contain:

```text
<feature_module>/
  domain/
  application/
  infrastructure/
  presentation/
  module.py
```

Do not create global feature logic in `app`, `shared`, or `platform` if that logic clearly belongs to one business module.

## Layer Responsibilities

### `domain`

- Pure business rules, calculations, entities, value objects, domain services
- No `PySide6`
- No `SQLAlchemy` ORM code
- No direct HTTP, ESI, SDE, filesystem, or database calls

### `application`

- Use cases and orchestration
- Coordinates repositories, services, and transactions
- Converts data between UI-facing models and domain models
- Contains ports or protocols when external dependencies are needed

### `infrastructure`

- Adapters for database, HTTP, ESI, SDE, file IO, cache, token storage
- Implements interfaces declared by upper layers
- May use `SQLAlchemy`, `requests`, filesystem, etc.

### `presentation`

- `PySide6` windows, widgets, dialogs, presenters, view models
- UI state and UI wiring only
- No heavy business calculations in widgets
- No direct SQL queries inside UI classes

## Dependency Rules

Dependencies must flow inward:

- `presentation -> application`
- `application -> domain`
- `infrastructure -> application/domain contracts`

Forbidden directions:

- `domain -> presentation`
- `domain -> infrastructure`
- `application -> PySide widgets`
- one feature directly importing another feature's infrastructure internals

Cross-feature access should happen through explicit application services, ports, or public module APIs.

## Platform Layer Rules

`platform` is for technical capabilities shared across multiple business modules.

Examples of valid `platform` packages:

- `platform/db`
- `platform/esi`
- `platform/sde`
- `platform/auth`
- `platform/characters`
- `platform/assets`
- `platform/scheduler`
- `platform/logging`

`platform` must not become a dump for business logic.

If code is specific to blueprint profitability, regional trading, mining yield, or project accounting, it belongs in the owning business module, not in `platform`.

## Shared Layer Rules

`shared` should stay very small.

Valid contents:

- common exceptions
- small generic DTOs
- generic utilities with broad reuse
- foundational abstractions reused by multiple bounded contexts

Invalid contents:

- industry logic
- market logic
- generic catch-all `helpers.py`
- generic catch-all `services.py`
- generic catch-all `models.py`

Rule of thumb: if code is reused by fewer than 3 modules, keep it local to the owning module.

## UI Rules

The UI should follow a presentation-oriented pattern:

- keep widgets focused on rendering and user interaction
- place orchestration in presenters or view models
- call application use cases from the presentation layer
- keep navigation centralized in `app/navigation.py` or equivalent

Do not place domain calculations, repository logic, or token refresh logic inside `QWidget`, `QMainWindow`, or dialog classes.

## Database Rules

Use `SQLite` with `SQLAlchemy`.

Guidelines:

- shared DB wiring belongs in `platform/db`
- module-specific repositories belong close to the owning module
- ORM models should live either in the owning module or in `platform/db/models` only when truly shared
- transaction management should be explicit
- avoid leaking raw sessions into the UI layer

## Module Registration

Each feature module should expose a `module.py` file that acts as its entry point.

`module.py` may define:

- module name
- navigation registration
- menu entries
- screen factories
- startup hooks
- dependencies on platform services

This enables the modular monolith to grow without centralizing all feature wiring in one giant file.

## File and Class Hygiene

The goal is to avoid both extremes:

- hundreds of tiny meaningless files
- giant scripts with multiple responsibilities

Rules:

- group code by feature first, then by layer
- prefer cohesive packages over flat root-level files
- split files when they start carrying multiple responsibilities
- avoid creating a separate file for one trivial class if the module is still small
- avoid deep inheritance trees unless they add real value
- prefer composition, protocols, and explicit interfaces

## Naming Rules

Prefer explicit names:

- `blueprint_profit_service.py`
- `market_order_repository.py`
- `update_character_assets_use_case.py`

Avoid vague names:

- `utils.py`
- `helpers.py`
- `service.py`
- `manager.py` unless the responsibility is genuinely clear

## Testing Guidance

When tests are added:

- domain logic should be covered with unit tests first
- application use cases should have focused integration tests
- infrastructure code should be tested around adapters and repository behavior
- UI tests should stay limited and targeted

Mirror tests by module whenever possible.

## Decision-Making Rules For Future Tasks

For each new task, prefer this order of thinking:

1. Which bounded context owns this feature: `industry`, `market`, `platform`, or `app`?
2. Is this domain logic, application orchestration, infrastructure integration, or presentation code?
3. Can the change stay inside one feature module?
4. If code looks reusable, is it truly cross-module, or only locally convenient?
5. Will this change create a future dumping ground or preserve clean boundaries?

If a requested change would break these rules, pause and confirm the tradeoff before implementing a shortcut.

## Architecture Evolution Rule

If the architecture needs to evolve, prefer extending the modular monolith rather than bypassing it.

Examples:

- add a new feature module instead of a global script
- add a new platform adapter instead of embedding API calls in UI code
- add a public module API instead of importing internal infrastructure across modules

Any architecture-changing decision should update this file so future tasks follow the same direction.
