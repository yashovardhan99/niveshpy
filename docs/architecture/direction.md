# General Direction

## Date

2026-04-05

## Context

The project is growing, and current architecture has friction in:

- performance overhead from heavy internal model validation/conversion
- persistence coupling inside services
- lack of migration-friendly persistence boundaries
- upcoming long-term async goal

## Decisions

1. Architecture pattern

      1. Use Enhanced Service Layer with selective DDD concepts.
      2. Do not adopt MVC.
      3. Do not adopt full DDD.

2. Persistence architecture

      1. Introduce Repository pattern as the main decoupling layer.
      2. Services should call repositories, not DB session/query primitives directly.

3. SQL stack direction

      1. Move from SQLModel-centered persistence toward SQLAlchemy-first persistence.
      2. Use SQLAlchemy ORM for domain entities.
      3. Use SQLAlchemy Core selectively for heavy reporting/aggregation queries.
      4. Add Alembic after SQLAlchemy ORM baseline is in place.

4. Model/validation direction

      1. Reduce internal Pydantic usage gradually for performance.
      2. Keep strict validation at external boundaries where it still adds value.
      3. Prefer lightweight internal structures (dataclasses/value objects, then attrs).

5. attrs/cattrs decision

      1. attrs + cattrs are a good fit for this project.
      2. Use cattrs hooks for Decimal/date/enum/nested conversions.
      3. Replace manual display mapping and RootModel batch wrappers with cattrs-based conversion.

6. Async decision

      1. Async is a future goal, not immediate.
      2. Prepare async-ready repository contracts later, after persistence boundaries stabilize.

## Alternatives Considered

- MVC: rejected (UI-centric, weak fit for CLI/service layering)
- Full DDD: rejected (too heavy for current scale)
- SQLAlchemy Core-only: rejected as default (less ergonomic for domain CRUD)

## Consequences

### Positive

- safer long-running migration
- clearer domain/persistence boundaries
- better performance trajectory
- easier async adoption later

### Negative

- temporary dual-path complexity during migration
- additional contract/integration testing required during transitions
