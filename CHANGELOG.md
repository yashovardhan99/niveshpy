# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Migrate to using sqlmodel/sqlalchemy with sqlite database.
- Standardize exceptions into a proper hierarchy.

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

[unreleased]: https://github.com/yashovardhan99/niveshpy/compare/v1.0.0a1...HEAD
[1.0.0a1]: https://github.com/yashovardhan99/niveshpy/compare/v0.1.0.dev0...v1.0.0a1
[0.1.0.dev0]: https://github.com/yashovardhan99/niveshpy/releases/tag/v0.1.0.dev0