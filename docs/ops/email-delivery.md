# Email delivery

Phlatline sends transactional email through the [Postmark](https://postmarkapp.com) HTTP API. This covers workspace invites, alert notifications, password-reset messages, and scheduled-diagnostic failure notices.

---

## Required environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTMARK_API_KEY` | **Yes** | — | Postmark server API token. The app **will not start** if this is absent. |
| `EMAIL_FROM` | No | `noreply@phlatline.dev` | The sender address shown to recipients. Must be a verified Postmark sender signature. |

!!! warning "Fail-fast on startup"
    If `POSTMARK_API_KEY` is missing, the backend raises a `RuntimeError` at module import time and refuses to start. Set the variable before deploying. In CI and test environments, callers mock `send_email` directly — the live transport is never exercised.

---

## Verifying email is working

After a successful email dispatch, the backend logs:

```
[EMAIL] sent to=<recipient> subject=<subject>
```

Search your log aggregator for `[EMAIL] sent` after triggering an invite or password-reset flow. If the log line appears, the message was accepted by Postmark. Delivery to the inbox is then Postmark's responsibility — check the Postmark dashboard for bounce or spam events.

---

## When `EmailDeliveryError` appears in logs

`EmailDeliveryError` is raised when Postmark returns a non-2xx response. Typical causes:

| Cause | How to identify | Fix |
|-------|-----------------|-----|
| Invalid or revoked API key | Postmark returns HTTP 401 | Rotate the key in Postmark → **API Tokens** and update `POSTMARK_API_KEY` |
| Unverified sender signature | Postmark returns HTTP 422, body mentions "sender signature" | Add and verify `EMAIL_FROM` address in Postmark → **Sender Signatures** |
| Postmark outage | HTTP 500 or network timeout | Check [status.postmarkapp.com](https://status.postmarkapp.com); retries are not automatic — the calling code handles failure |
| Recipient address rejected | Postmark returns error code 406 | Transient hard bounce; the recipient address is invalid |

Log lines include the Postmark error code and message:

```
[EMAIL] delivery failed to=<recipient> postmark_error=<code> message=<text>
```

Use the error code to look up the cause in [Postmark's error documentation](https://postmarkapp.com/developer/api/overview#error-codes).

---

## Fire-and-forget design

The workspace invite route sends email **after** the invite token is persisted to the database. Email dispatch is fire-and-forget: if `send_email` raises `EmailDeliveryError`, the error is logged and the invite creation response is still returned to the caller with HTTP 201.

This means:

- **The invite token is never lost on email failure.** The invited user can still be re-invited, or you can retrieve the invite link from the database directly.
- **No automatic retry.** If email delivery fails, the operator must either re-send the invite from the UI or trigger a re-invite via the API.
- **Other call sites (alerts, password reset) are not fire-and-forget.** Email failures in alert dispatch and password-reset flows propagate to the caller as HTTP 500 unless the caller handles them explicitly.

!!! note "Why fire-and-forget for invites?"
    Invite delivery failure is non-critical: the workspace owner can always re-send. Making the invite endpoint dependent on email transport would cause workspace management operations to fail during Postmark outages, which is a worse user experience than a delayed invite email.
