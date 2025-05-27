# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2024-05-25

### Added
- documentation
- keycoak connection error handling
- complete database migrations
- a helm chart

### Fixed
- missing keycloak env vars
-

### Changed
- Improved start-dev in Makefile, enhanced database issues
- using pydantic classes in some cases now (e.g. for provider config)
- load processes async
- made the process of determining which are visible to the user more concise and more explicit
- added base logger and logging
- simplyfied keycloak connection settings
- improved settings management
- improved database connection pooling and connection re-use
- fixed dev setup and eased dev setup mileage

## [1.1.0] - 2024-07-22

### Changed

- added package management system (poetry)
- using project template (copier)
- moved source code inside src folder and restructured it
