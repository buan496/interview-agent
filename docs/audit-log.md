# Audit Log v1

Audit log v1 records selected security and admin events in the database so production incidents can be investigated with the same `request_id` used by structured logs.

This is a selective audit ledger, not a high-volume request log. Ordinary page reads are intentionally not audited in v1.

## Event Scope

Recorded in PR #38:

- `login_success`: a user successfully signs in.
- `login_failed`: a sign-in attempt fails verification.
- `admin_access`: an allowlisted admin enters an admin API route.
- `admin_denied`: a non-admin attempts to enter an admin API route.

Extended in PR #40:

- `admin_access`: also records RBAC role-based admin access. Metadata includes `required_role`, `user_role`, and `access_source`.
- `admin_denied`: also records RBAC denial reasons such as `rbac_denied` and `content_operator_not_admin`.

Not covered in v1:

- Organization or tenant-level audit scopes.
- Frontend admin audit console.
- Full report access audit.
- Bulk data export or privacy request audit.

## Table

`audit_events` fields:

- `id`: audit event id.
- `actor_user_id`: authenticated actor id when available.
- `actor_phone_masked`: masked actor phone, for example `188****0001`.
- `actor_role`: `anonymous`, `user`, `admin`, or `content_operator`.
- `action`: event name such as `login_success`.
- `resource_type`: coarse resource domain, such as `auth` or `admin`.
- `resource_id`: optional resource id as a string.
- `target_user_id`: optional user affected by the operation.
- `request_id`: request correlation id from observability middleware.
- `status`: `success`, `failed`, or `denied`.
- `reason`: short machine-readable reason.
- `ip_address`: request client address when available.
- `user_agent`: request user agent when available.
- `metadata_json`: sanitized non-sensitive event metadata.
- `created_at`: database creation time.

Indexes exist for actor/time, action/time, and `request_id`.

## Query API

Admins can query audit events:

```http
GET /api/admin/audit-events
```

Supported filters:

- `action`
- `actor_user_id`
- `status`
- `limit`
- `offset`

The endpoint is protected by RBAC v1. `User.role=admin` can query it. `ADMIN_PHONES` remains a bootstrap/fallback path. Non-admin users receive `403` and the denied attempt is itself audited.

## Sensitive Data Rules

Audit metadata must not store:

- Authorization headers
- Access tokens
- JWT values
- Secrets or API keys
- Verification codes
- Full phone numbers
- User answer text
- Prompt text
- Model completion text

The audit helper masks metadata keys that contain sensitive terms such as `token`, `secret`, `code`, `authorization`, `phone`, `prompt`, `completion`, and `answer`.

## Failure Behavior

Audit writes are best effort. If an audit insert fails, the helper rolls back the audit transaction and emits `audit.write_failed` to structured logs. The original login or admin request is not failed solely because audit storage is unavailable.

## Troubleshooting

1. Collect `X-Request-ID` from the API response, browser network tab, or support ticket.
2. Search structured logs for the same `request_id`.
3. Query `/api/admin/audit-events` filtered by `request_id` through database tooling if route filters are insufficient.
4. Compare `http_request`, business events, and `audit_events` to identify actor, status, and reason.

For runtime logs and request correlation, see [Observability Foundation](observability.md).
