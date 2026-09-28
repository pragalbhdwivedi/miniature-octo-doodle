# Component Lifecycle

Canonical component metadata lives in `config/components.yaml`.

## States
- available
- installed
- running
- stopped
- update_available
- unsupported
- blocked

## Install-later contract
Before installing an optional component:
1. check free disk
2. verify dependencies
3. verify current upstream project status/version
4. estimate or measure download footprint
5. show the user what will be installed
6. require explicit approval
7. stop if critical disk reserve would be violated

## Removal
Removal must distinguish:
- container/image removal
- configuration removal
- persistent-data removal

Persistent data must never be deleted implicitly.
