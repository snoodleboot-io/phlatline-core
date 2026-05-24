# Setting up SSO/SAML

## Prerequisites

- **Plan:** Business plan required. SSO is not available on free or Pro plans.
- **Role:** Workspace owner. Only workspace owners can configure and activate SSO.

---

## Overview

Phlatline supports SP-initiated SAML 2.0. In this flow:

- **Phlatline (SP):** Generates the AuthnRequest, validates the SAML assertion, and creates or updates the user session.
- **Your IdP:** Authenticates the user, signs the SAML assertion, and redirects back to Phlatline's ACS URL.

Phlatline does not support IdP-initiated SSO. Users must start the login flow from the Phlatline login page.

---

## Step-by-step setup

### 1. Navigate to Settings → SSO

Go to **Settings** → **SSO** in your workspace. This page shows your current SSO configuration status and all the values you need to configure your IdP.

### 2. Enter your email domain

Enter the domain that should be covered by SSO (e.g. `acme.com`). All users whose email addresses match this domain will be subject to SSO policy once you activate it.

### 3. Enter your IdP metadata

Provide either a metadata URL or paste the metadata XML directly:

- **Metadata URL (recommended):** Phlatline will fetch metadata at login time, so key rotations propagate automatically.
- **Metadata XML:** Paste the raw XML if your IdP does not expose a public metadata URL.

**Okta:** In your Okta application, go to **Sign On** → **SAML Signing Certificates** and copy the **Metadata URL**.

### 4. Save the configuration

Click **Save**. The configuration is saved in `pending` status — SSO is not yet active and users can still log in with email and password.

### 5. Domain verification

Phlatline requires you to prove ownership of the domain before activating SSO.

1. Copy the DNS TXT record shown on the SSO settings page.
2. Add it to your DNS as a TXT record at `_phlatline.{domain}` (e.g. `_phlatline.acme.com`).
3. Click **Verify** once the record is in place.

DNS propagation can take up to 48 hours depending on your DNS provider and TTL settings. If verification fails, wait and try again.

### 6. Activate SSO

Once the domain is verified, click **Activate**. SSO moves to `active` status — users can now log in via SSO, but email and password login still works.

Before enforcing SSO, test the login flow in a **private or incognito window** to confirm your IdP configuration is correct.

### 7. Enforce SSO (optional)

Click **Enforce** to block email and password login for all users whose email matches your verified domain. Users who attempt password login will be redirected to your IdP.

Workspace owners retain emergency bypass access (see [Emergency bypass](#emergency-bypass) below) even when enforcement is active.

---

## IdP-specific guides

### Okta

1. In Okta Admin, go to **Applications** → **Create App Integration** → **SAML 2.0**.
2. Set the **Single sign-on URL** (ACS URL) to:
   ```
   https://app.phlatline.io/auth/saml/{slug}/acs
   ```
3. Set the **Audience URI (SP Entity ID)** to:
   ```
   https://app.phlatline.io/saml/{slug}
   ```
   Replace `{slug}` with your workspace slug, visible on the SSO settings page.
4. Set **Name ID format** to `EmailAddress`.
5. Under **Attribute Statements**, optionally map `phlatline_role` to a user attribute.
6. Save the app, then copy the **Metadata URL** from **Sign On** → **SAML Signing Certificates** and paste it into Phlatline's SSO settings.

### Azure AD

1. In the Azure portal, go to **Azure Active Directory** → **Enterprise applications** → **New application** → **Create your own application**.
2. Choose **Integrate any other application you don't find in the gallery**.
3. Go to **Single sign-on** → **SAML**.
4. Under **Basic SAML Configuration**, set:
   - **Identifier (Entity ID):** `https://app.phlatline.io/saml/{slug}`
   - **Reply URL (ACS URL):** `https://app.phlatline.io/auth/saml/{slug}/acs`
5. Set **Name ID** to `user.mail` (email format).
6. Optionally add a **Claim** for `phlatline_role` mapped to an app role or user attribute.
7. Download the **Federation Metadata XML** and paste it into Phlatline's SSO settings.

### Google Workspace

1. In the Google Admin console, go to **Apps** → **Web and mobile apps** → **Add app** → **Add custom SAML app**.
2. Name the app (e.g. `Phlatline`) and click **Continue**.
3. Copy the **SSO URL** and **Certificate** — you can optionally paste the metadata XML into Phlatline instead.
4. On the **Service provider details** page, set:
   - **ACS URL:** `https://app.phlatline.io/auth/saml/{slug}/acs`
   - **Entity ID:** `https://app.phlatline.io/saml/{slug}`
   - **Name ID format:** `EMAIL`
   - **Name ID:** `Basic Information > Primary email`
5. Optionally add an attribute mapping for `phlatline_role`.
6. Save and enable the app for the relevant organizational units.

---

## Attribute mapping

Phlatline reads the following attributes from the SAML assertion:

| SAML attribute | Description |
|---|---|
| `NameID` | Required. Must be in email format. Used as the user's email address. |
| `phlatline_role` | Optional. Sets the user's workspace role on JIT provisioning. Valid values: `member`, `admin`. |

If `phlatline_role` is set to `owner`, Phlatline rejects the value and clamps it to `member`. This prevents privilege escalation through the IdP. The rejection is logged in your audit trail.

---

## Emergency bypass

If your IdP is unavailable and you cannot log in via SSO:

1. Navigate to `/app/emergency-bypass`.
2. Enter your **email address** and **workspace slug**.
3. Phlatline sends a 6-digit OTP to your email address.
4. Enter the OTP to gain access.

The OTP expires after 15 minutes and is rate-limited to 5 attempts.

---

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| "No active SSO configuration for domain" | Domain not verified, or SSO config status is not `active` or `enforced` | Verify the domain and click Activate on the SSO settings page |
| "SAML assertion already consumed" | Browser replay or IdP/SP clock skew | Check IdP clock skew settings; Phlatline's default tolerance is 120 seconds |
| "Your access to this workspace has been revoked" | SCIM deprovisioning removed this user's membership | Contact your workspace owner to restore access |
| Redirect loop after login | ACS URL or Entity ID mismatch in IdP config | Check that the URLs in your IdP match exactly what is shown on the Phlatline SSO settings page |
