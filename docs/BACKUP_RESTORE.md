# Backup and Restore

The repository must contain everything required to reconstruct the platform except secrets and runtime data.

## Back up
- PostgreSQL / LiteLLM state
- Open WebUI state
- local configuration
- list of installed optional components
- list of installed local models
- optional component persistence

## Rebuild target
```text
new computer
-> clone repository
-> install prerequisites
-> create .env
-> start core
-> restore runtime data if desired
-> reconnect provider credentials
```

Do not store backups in this public repository.
