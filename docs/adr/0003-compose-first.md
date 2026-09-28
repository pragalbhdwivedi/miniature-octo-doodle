# ADR 0003: Docker Compose before Kubernetes

Status: Accepted

## Decision
Make Docker Compose the first operational deployment and maintain Kubernetes as a later deployment target.

## Rationale
The laptop has limited disk space and the project needs a simple recovery path.

## Consequence
Kubernetes must not become a prerequisite for the first working version.
