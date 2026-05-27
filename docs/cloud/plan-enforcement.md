# Plan enforcement

Phlatline enforces plan limits at the API layer. Seat limits, schedule limits, and run retention are checked on every relevant request — not batched or eventually consistent. When a limit is reached, the API returns HTTP 402.

---

## Seat limits

Each plan defines a maximum number of workspace members (`seats`). The seat limit is checked when a workspace owner or admin sends a workspace invite.

**Route:** `POST /workspaces/{slug}/invites`

When the current member count equals the plan's seat limit, the invite is rejected before the invite token is created:

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{"error": "seat_limit_reached"}
```

The member count includes accepted members only; pending invites do not consume a seat.

---

## Schedule limits

Each plan defines a maximum number of active schedules. The schedule count is checked when a new schedule is created.

**Route:** `POST /workspaces/{slug}/schedules`

When the workspace's active schedule count equals the plan's schedule limit, the request is rejected:

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{"error": "schedule_limit_reached"}
```

!!! note "Two separate schedule gates"
    The schedule route applies two checks in order:

    1. **Binary gate** — is the plan allowed to use scheduled diagnostics at all? Plans without this feature return 402 regardless of count.
    2. **Count gate** — has the workspace reached its schedule limit? This check uses `plan_limits.schedules` (e.g. 5 for Solo, 25 for Team, unlimited for Business).

    Both checks return the same `schedule_limit_reached` error body.

---

## Run retention

Each plan includes a retention window (`retention_days`). When you list runs, the API excludes runs older than your plan's retention window from the response.

**Route:** `GET /v1/workspaces/{workspace_slug}/runs`

- Runs outside the retention window are silently excluded — the endpoint returns HTTP 200 with a filtered list.
- Pagination applies to the filtered set.
- Workspace membership is required.

**Query parameters:**

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `page` | `1` | — | Page number (1-indexed) |
| `limit` | `50` | `200` | Results per page |

**Retention window by plan:**

| Plan | Retention |
|------|-----------|
| Free | 30 days |
| Solo | 90 days |
| Team | 365 days |
| Business | Unlimited |

---

## Upgrade modal

When the Phlatline dashboard receives a 402 response from a plan-gated endpoint, the upgrade modal appears automatically. The modal:

- Shows the limit that was hit (seats or schedules).
- Links to the billing settings page to compare plans.
- Dismisses without navigating away, so the user does not lose their current context.

The modal is triggered by 402 responses on invite creation and schedule creation. Other 402 responses (e.g. retention filter) do not trigger the modal.

---

## Handling 402 responses in the API

If you are building against the Phlatline API directly, treat `402 Payment Required` on any plan-gated endpoint as a soft rejection — the resource was not created. The `error` field in the response body identifies the specific limit:

| `error` value | Trigger |
|---------------|---------|
| `seat_limit_reached` | `POST /workspaces/{slug}/invites` |
| `schedule_limit_reached` | `POST /workspaces/{slug}/schedules` |

Example handling:

```python
response = client.post(f"/workspaces/{slug}/invites", json=payload)
if response.status_code == 402:
    error = response.json()["error"]
    if error == "seat_limit_reached":
        # prompt user to upgrade or remove inactive members
        ...
```

!!! note
    402 responses from plan-gated routes do not count against your rate limit.
