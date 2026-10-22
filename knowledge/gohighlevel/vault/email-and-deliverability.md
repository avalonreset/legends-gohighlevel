# Email and telecom deliverability

## 1. Custom SMTP (`Brevo`, `SendGrid`, `Amazon SES`) vs. LC Email

Sub-accounts in GoHighLevel can send email through two paths:

| Path | How billing works | Deliverability and reputation |
|---|---|---|
| **Custom SMTP (BYO Email)** | **\$0.00 agency/HighLevel cost.** Outbound email routes directly through the sub-account's own SMTP credentials (such as Brevo, SendGrid, Mailgun, or Amazon SES). HighLevel does not meter or bill Custom SMTP sends. | Uses the sub-account's dedicated provider and authenticated sending domain (`SPF`, `DKIM`, `DMARC`). |
| **LC Email (LeadConnector)** | Metered against the sub-account's pre-paid HighLevel wallet (`$0.000675` base cost per email, `1.05x` rebilled). | Uses HighLevel's managed Mailgun infrastructure or a dedicated sending domain configured under Email Services. |

Once Custom SMTP (`blockAddSmtp: false`) is unlocked on a sub-account (see [Agency Governance](agency-governance.md)), the sub-account admin can open **Settings > Email Services > SMTP & Mailgun Services**, click **Add Service**, select **Other** (or their provider), enter their SMTP host, port, username, and password, and click **Set as active**.

## 2. Subdomain MX isolation (`inbound.<domain>` vs. Root MX)

Never point a business's root domain `MX` records (`@`) to Mailgun/HighLevel if the domain already uses Google Workspace (`smtp.google.com`) or Microsoft 365 for corporate email. Replacing root `MX` records breaks primary inbox delivery.

Instead, isolate HighLevel inbound and outbound mail on a dedicated subdomain (for example `inbound.example.com` or `mail.example.com`):

1. **Root domain (`example.com`):** Keep `MX` records pointed to Google Workspace (`smtp.google.com`, priority 1) or Microsoft 365.
2. **HighLevel subdomain (`inbound.example.com`):**
   - `TXT` (`SPF`) on `inbound.example.com`: `v=spf1 include:mailgun.org ~all`
   - `TXT` (`DKIM`) on `<selector>._domainkey.inbound.example.com`
   - `MX` on `inbound.example.com`: `mxa.mailgun.org` (priority 10) and `mxb.mailgun.org` (priority 10)
   - `CNAME` on `email.inbound.example.com`: `mailgun.org`
   - `TXT` (`DMARC`) on `_dmarc.inbound.example.com`

## 3. Telecom and A2P 10DLC compliance guardrails

Because sub-account carrier violations can trigger fines or suspend the parent agency account:

- Require **A2P 10DLC** brand and campaign registration through The Campaign Registry before automated SMS sending in the United States.
- Obtain explicit prior written consent before automated text messaging or AI voice calls (TCPA compliance).
- Honor `STOP` opt-outs immediately, respect recipient local quiet hours, and never import purchased or scraped contact lists.
