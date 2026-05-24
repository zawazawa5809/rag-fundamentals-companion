<!-- License: CC0-1.0 -->
# Stratus REST API Reference

> Generated from: `stratus/openapi.yaml`
> Last build: 2026-05-19 03:14 JST
> Generator: openapi-generator-cli 7.5.0

This document is **auto-generated** from the OpenAPI specification. Do not edit manually. To update, modify `openapi.yaml` in the `stratus-platform` repository and rerun the generator.

## Base URL

```
https://api.stratus.haruna-tech.com/v1
```

## Authentication

All endpoints require an Authorization header.

```
Authorization: Bearer <access_token>
```

Tokens are issued by the Auth Service. See `POST /v1/auth/token`.

## Endpoint Catalog

| Method | Path | Description | Auth | Min Plan |
| ------ | ---- | ----------- | ---- | -------- |
| POST | `/v1/auth/token` | Exchange API key for short-lived access token | API key | Starter |
| POST | `/v1/auth/refresh` | Refresh access token | refresh token | Starter |
| GET | `/v1/auth/whoami` | Return current token claims | access token | Starter |
| POST | `/v1/ingestion/events` | Submit a batch of events | access token | Starter |
| POST | `/v1/ingestion/metrics` | Submit a batch of metrics | access token | Starter |
| GET | `/v1/dashboards` | List dashboards | access token | Starter |
| GET | `/v1/dashboards/{id}` | Get a single dashboard | access token | Starter |
| POST | `/v1/dashboards` | Create a dashboard | access token | Starter |
| GET | `/v1/storage/queries/{id}` | Get query result | access token | Pro |
| POST | `/v1/storage/queries` | Submit ad-hoc query | access token | Pro |
| POST | `/v1/notifications/rules` | Create alert rule | access token | Pro |
| GET | `/v1/notifications/history` | List notification history | access token | Pro |

## Schema: `Token`

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "expires_in": 3600,
  "tenant_id": "string",
  "scopes": ["string"]
}
```

## Schema: `IngestionEvent`

```json
{
  "ts": "ISO-8601 timestamp",
  "event_type": "string",
  "payload": "object",
  "source": "string"
}
```

## Schema: `Dashboard`

```json
{
  "id": "uuid",
  "name": "string",
  "owner": "user_id",
  "widgets": [{ "type": "string", "config": "object" }],
  "shared_with": ["squad_id"],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

## Error codes

| HTTP | Code | Meaning |
| ---- | ---- | ------- |
| 400 | `INVALID_PAYLOAD` | リクエストボディの schema 不一致 |
| 401 | `INVALID_TOKEN` | トークン期限切れもしくは不正 |
| 403 | `INSUFFICIENT_PLAN` | プランで許可されていない operation |
| 404 | `NOT_FOUND` | リソース不在 |
| 409 | `CONFLICT` | 同名リソース存在 |
| 429 | `RATE_LIMITED` | レート制限超過 |
| 500 | `INTERNAL_ERROR` | サーバ内部エラー |

## Versioning

API は `/v1/` で安定。互換性破壊変更は `/v2/` を作る方式。各 endpoint の `Sunset` ヘッダで deprecation 予定を通知する。

## Notes (auto-generated footer)

- This reference reflects the **currently deployed** Stratus 4.x API surface.
- For information about the upcoming 5.0 boundary changes (Auth integration into API Gateway), refer to `stratus-microservice-boundaries-draft.md` (NOTE: that document describes a future state and is not yet implemented).
