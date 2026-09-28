# Upgrade Policy

Do not blindly track `latest` forever.

## Upgrade process
1. inspect current upstream release notes
2. record current versions
3. back up persistent state
4. test upgrade in an isolated/reviewable way
5. validate health and routing
6. update pinned image/version references
7. update BUILD_STATUS and troubleshooting notes

For security-sensitive or breaking upgrades, use a pull request rather than an unreviewed direct change.
