# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[unreleased]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a2...HEAD
[1.0.0a2]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a1...v1.0.0a2
[1.0.0a1]: https://github.com/yashovardhan99/niveshpy/compare/v0.1.0.dev0...v1.0.0a1
[0.1.0.dev0]: https://github.com/yashovardhan99/niveshpy/releases/tag/v0.1.0.dev0