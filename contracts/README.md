# API Contracts

This directory stores representative JSON payloads for the core training-loop API.

The samples are intentionally checked by both sides:

- Backend unit tests validate every sample with the Pydantic response/request schemas.
- Frontend typecheck imports the same samples and validates their structural compatibility with TypeScript API types.

When changing an API shape, update the backend schema, frontend type, and the matching sample in the same PR. The goal is to catch accidental drift across the frontend/backend boundary before merge.
