# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Update how migrations are applied for a more consistent database build.

## [1.0.0a7] - 2026-05-03

### Added

- Automatic database migration support.

### Changed

- (Internal) Migrate all CLI commands to use domain objects directly with cattrs instead of separate display models.
- (Internal) Update database layer to use sqlalchemy instedd of sqlmodel.
- Updated database table schemas.

### Removed

- (Internal) Remove Sqlmodel dependency.

## [1.0.0a6] - 2026-04-29

### Added

- (Internal) Add new repository function to update security properties.
- (Internal) Add new Lot accounting service to simplify computations of investment lots and cost-basis.
- Add new --output-file flag to redirect csv/json output to a file.

### Changed

- (Internal) Refactor Transaction, Price, and Report services into new repository pattern.
- (Internal) Refactor Transaction, Price, and Report service tests to use a dummy repository.
- (Internal) Restructure Account, Security, Transaction and Price models resulting in performance improvements.

## [1.0.0a5] - 2026-04-08

### Added

- (Internal) Add new CLI integration tests for more robust testing.
- (Internal) Add new tests for SQLite Account & Security repositories

### Changed

- `niveshpy securities add` will no longer update existing securities.
- (Internal) Refactor Account & Security into new repository pattern.
- (Internal) Refactor Account & Security service tests to use a dummy repository.

### Fixed

- Fix breaking issue with deferred annotations on Python versions 3.11-3.13.

## [1.0.0a4] - 2026-04-04

### Changed

- Performance improvements across the board to reduce cold-start times.
- (Internal) Move GitHub Actions workflows to use uv.

### Fixed

- Fix failing documentation build.

## [1.0.0a3] - 2026-03-26

### Added

- New holdings report.
- New asset allocation report.
- New --cost flag for transactions.
- New portfolio performance report.
- New portfolio summary report.

### Changed

- Unified decimal formatting for cleaner UX.
- Standardized logging with level guidelines and consistent coverage across all modules.
- Expanded test suite — added coverage for CAS parser, plugin system, CLI commands, and exception hierarchy.

### Fixed

- Text queries being grouped incorrectly.

## [1.0.0a2] - 2026-01-08

### Added

- Unit testing for core components.
- Python 3.14 support.

### Changed

- Migrate to using sqlmodel/sqlalchemy with sqlite database.
- Standardize exceptions into a proper hierarchy.
- Simplified synchronization of prices.
- Performance improvements for top command (`niveshpy -h`)
- Updated documentation to reflect recent changes.
- Updated dependencies.
- Simplified deletion workflow.

### Fixed

- Bulk updates deleting all transactions irrespective of accounts.
- Concurrency issues in bulk updates.
- Unified error handling with clear messages.
- Range operator not supporting one-sided open ranges in amount queries.
- Security losing existing properties on update.

## [1.0.0a1] - 2025-11-09

### Added

- New CLI interface for easier use
- New Github workflow for automated testing and coverage.
- New classifiers to properly describe the project

### Changed

- Redesigned entire app from the group-up to focus on CLI instead.

### Fixed

- Problem with publishing assets to Github Releases
- Documentation URL fixes


## [0.1.0.dev0] - 2025-05-25

### Added

- Basic project structure for Python package.
- Ability to fetch and store latest and historical quotes.
- Pre-built plugin: amfi (Mutual Fund)
- Documentation

[unreleased]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a7...HEAD
[1.0.0a7]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a6...v1.0.0a7
[1.0.0a6]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a5...v1.0.0a6
[1.0.0a5]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a4...v1.0.0a5
[1.0.0a4]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a3...v1.0.0a4
[1.0.0a3]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a2...v1.0.0a3
[1.0.0a2]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a1...v1.0.0a2
[1.0.0a1]: https://github.com/yashovardhan99/niveshpy/compare/v0.1.0.dev0...v1.0.0a1
[0.1.0.dev0]: https://github.com/yashovardhan99/niveshpy/releases/tag/v0.1.0.dev0