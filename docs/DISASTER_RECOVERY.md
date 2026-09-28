# Disaster Recovery

Goal: rebuild the platform on a clean machine using this repository plus separately protected secrets/backups.

## Recovery order
1. obtain supported Windows/WSL2/Docker environment
2. clone repository
3. create local `.env`
4. run preflight
5. start core
6. restore PostgreSQL/Open WebUI data if needed
7. restore optional component state
8. reinstall local models from documented model list rather than storing weights in Git
9. validate provider connectivity
10. validate web UI and gateway

The repository alone must never contain production secrets or private datasets.
