# Automated user provisioning (SCIM 2.0)

## Overview

SCIM 2.0 (RFC 7644) lets your identity provider automatically provision and deprovision users in Phlatline. When a user is assigned to the Phlatline app in your IdP, SCIM creates their Phlatline account. When they are removed or deactivated, SCIM revokes their workspace membership and invalidates their sessions immediately.

Supported IdP integrations: **Okta Lifecycle Management** and **Azure AD provisioning**.

SCIM requires an active SSO configuration. Set up [SSO/SAML](sso-setup.md) first.

---

## Supported operations

| Method and endpoint | Description |
|---|---|
| `POST /scim/v2/{workspace}/Users` | Provision a new user. Creates a Phlatline account and workspace membership. |
| `GET /scim/v2/{workspace}/Users/{id}` | Read a provisioned user. |
| `PATCH /scim/v2/{workspace}/Users/{id}` | Update a user. Setting `active: false` deprovisions them. |
| `DELETE /scim/v2/{workspace}/Users/{id}` | Hard deprovision. Revokes membership, invalidates all active sessions, and soft-deletes the user. |

Replace `{workspace}` with your workspace slug.

---

## Creating a SCIM token

1. Go to **Settings** → **SSO** → **SCIM Provisioning**.
2. Click **Create SCIM Token**.
3. Copy the token immediately — it is shown only once.

Each workspace can have one active SCIM token. Creating a new token invalidates the previous one.

---

## Okta SCIM setup

1. In your Okta Admin console, open the Phlatline application.
2. Go to **Provisioning** → **Configure API Integration**.
3. Enable **API integration** and enter:
   - **Base URL:** `https://app.phlatline.io/scim/v2/{your-workspace-slug}`
   - **API Token:** paste the SCIM token created above.
4. Click **Test API Credentials** to verify the connection.
5. Click **Save**, then go to **Provisioning** → **To App** and enable:
   - **Create Users**
   - **Update User Attributes**
   - **Deactivate Users**
6. Assign users or groups to the Phlatline app. Okta will provision them immediately.

---

## Azure AD SCIM setup

1. In the Azure portal, open the Phlatline enterprise application.
2. Go to **Provisioning** → **Get started**.
3. Set **Provisioning Mode** to **Automatic**.
4. Under **Admin Credentials**, enter:
   - **Tenant URL:** `https://app.phlatline.io/scim/v2/{your-workspace-slug}`
   - **Secret Token:** paste the SCIM token created above.
5. Click **Test Connection** to verify.
6. Under **Mappings**, review the attribute mappings (see [User attributes](#user-attributes) below).
7. Save and set **Provisioning Status** to **On**.

Azure AD runs provisioning cycles every 20–40 minutes. Trigger an **On Demand** provisioning cycle from the Provisioning page to provision a specific user immediately.

---

## User attributes

| SCIM attribute | Phlatline field | Notes |
|---|---|---|
| `userName` | email | Used as fallback if `emails[primary]` is absent |
| `emails[primary]` | email | Takes precedence over `userName` |
| `active` | membership status | `false` sets `revoked_at` on the workspace membership |

---

## Deprovisioning behavior

Setting `active: false` (PATCH) or sending a DELETE request has the following immediate effects:

- The user's workspace membership is revoked (`revoked_at` is set).
- All active sessions for the user are invalidated.
- The user cannot log in to the workspace until re-provisioned.

Deprovisioning does not delete the user's data. Workspace content (runs, reports, settings) is preserved and remains accessible to workspace owners.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | SCIM token revoked, expired, or wrong workspace slug in the URL | Regenerate the SCIM token in Settings → SSO → SCIM Provisioning; confirm the workspace slug in the base URL matches your workspace |
| `409 Conflict` | User is already a member of the workspace | Safe to ignore — this is an IdP retry. The user's membership is already correct. |
