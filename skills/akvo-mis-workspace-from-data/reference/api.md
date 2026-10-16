# Akvo MIS HTTP API — what the workspace setup uses

This was verified against the akvo-mis source in September 2026. Every path
sits under `/api/v1/`. **None of these routes take a trailing slash.** Auth
is `Authorization: Bearer <token>`.

## Hosts

- Every workspace lives at `<subdomain>.<BASE_DOMAIN>`, for example
  `who.mis.akvotest.org`. The server works out the workspace from the `Host`
  header.
- **Base domain** (`mis.akvotest.org`): only `register` and `health/check`
  are called here.
- **Workspace host**: everything else, login included. Calling login on the
  base domain gets a 400: "Sign in at your workspace address".
- **Unknown subdomain**: 404 `{"message":"Workspace not found"}`.
- **A token used on another workspace's host**: 403.
- **Server without routing** (`BASE_DOMAIN` unset): `GET tenant-info` answers
  204 on every host. Workspaces cannot be created there.

## Sign-up (anonymous)

| Step | Call | Notes |
|---|---|---|
| probe | `GET tenant-info` on the new host | 404 means the subdomain is free; 200 means it is taken |
| register | `POST register` on the base domain, body `{email, password, subdomain}` | Creates the workspace and an **inactive** super admin, then emails an activation link. The subdomain must match `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`, 63 characters at most, and be unique. The password goes through Django's validators (8+ characters, not common, not all digits, not too close to the email). Emails are unique per workspace only. |
| activate | The user clicks `https://<sub>.<base>/activate/<token>`. The page calls `POST register/activate {token}` | The token lasts 7 days and can't be forged, because it is signed with the server secret. **There is no emailed temporary password.** The password is whatever `register` was sent. |
| resend | `POST register/resend-activation {email}` on the workspace host | Always returns 200. |
| login | `POST login {email, password}` on the workspace host | Returns `{token, configured, is_superuser, ...}`. A 401 carrying `unverified: true` means the account is not activated yet. The token lasts 12 h, but the profile check expires after 4 h of inactivity, so log in again. There is no refresh endpoint. |
| configure | `POST register/configure {first_name, last_name, level_0_name, root_unit_name}` | Required exactly once. It creates level 0 and the root unit. Calling it again gets 400 "already configured". The web app sends unconfigured users to `/configure`. |
| password | `POST user/forgot-password {email}` on the workspace host | How the user replaces the temporary password afterwards. |

The account is a super admin inside its workspace. Its submissions skip
approval, and it can manage users, forms, the hierarchy and dashboards. There
are no rate limits or captcha, and no CSRF check for JWT calls.

## Administration

- **List levels:** `GET levels-management` returns `[{id, name, level}]`. It is not paginated and needs super admin.
- **Add a level:** `POST levels-management {name}` appends at max+1.
  - Only possible **while the root is the only unit**. After that: 400 "Levels cannot be added once administrative units exist".
  - Rename with `PUT levels-management/{id} {name}`.
- **Add a unit:** `POST administrations {name, parent}` returns 201 `{id, name, parent:{id}, level:{id,name}, ...}`.
  - The level is the parent's level + 1, and that level must exist.
  - Leave `code` out: `code: null` returns a 500.
- **List units:** `GET administrations?page=&page_size=100&parent=&level=&search=` returns `{current, total, total_page, data}`.
- **Other routes:** `PUT` and `DELETE administrations/{id}`. The delete returns 409 if data references the unit.
- **Bulk upload:** an xlsx upload exists (`upload/bulk-administrations`), but it is asynchronous and reports errors **only by email**. Use one POST per unit.

## Forms (form builder)

- **Create:** `POST manage/forms` returns 201 in editor format, with every group and question `id`.
  - Body: `{name, description, type: 1|2, parent?, question_group:[{name, label, order, repeatable, question:[{order, label, name, type, required, meta, option:[{label, value, order}], rule, extra, dependency, tooltip:{text}}]}]}`.
  - `type` is 1 for registration and 2 for monitoring.
  - Each question **needs** `order` and `label`; a missing one returns a 500.
- **Types:** `input text number date option multiple_option geo cascade image signature attachment autofield geoshape geotrace tree table`.
- **Administration picker:** `type: "cascade", extra: {"type": "administration"}`.
- **Number rule:** `rule: {min, max, allowDecimal}`.
- **Dependency:** `[{"id": <question id>, "options": ["<option value>"]}]`.
  - It needs server ids, so create first, then `PUT manage/forms/{id}` with the returned editor JSON plus the dependencies.
  - Don't invent numeric ids: id lookups are **not** scoped to the workspace, so a clash overwrites another workspace's question.
- **Monitoring form:** `type: 2, parent: <registration form id>`. The parent must already be **published**.
- **Publish:** `POST manage/forms/{id}/publish`. Drafts receive no data and are invisible to the web and mobile apps. Editing a published form stores a draft version, which goes live only on the next publish.
- **Find existing:** `GET manage/forms?type=registration|monitoring&search=` returns registration forms with their `children`.

## Data

- **Submit one record:** `POST form-pending-data/{form_id}`, synchronous, returns 200 `{"message":"ok"}` or 400 `{message, details}`.
  ```json
  {"data": {"name": "WP-001 - Kilifi tank", "administration": 96,
            "geo": [-0.34, 35.63], "uuid": "<uuid>", "submission_key": "<≤64>"},
   "answer": [{"question": 600201, "value": "WP-001"}]}
  ```
- **Value encoding:**
  - input, text and date are strings (date as `"2026-05-10"`).
  - number is a number.
  - option, multiple_option and geo are **lists**: `["borehole"]` (option values, not labels) and `[lat, lng]`.
  - An administration cascade is the **unit id** as a number.
  - Empty `""` and `[]` are rejected, so leave blank answers out.
- **`submission_key`:** the idempotency key. Re-sending the same key writes nothing.
- **`uuid` on a registration:** stored as the record's uuid.
- **`uuid` on a monitoring form:** links the row to the registration with that uuid. The row then copies the registration's administration and geo.
- **Approval:** super-admin submissions go straight to data, never pending. Nobody needs to approve them.
- **Historical dates:** they **cannot** be backdated. Every record is stamped with the upload time, and the Excel and mobile timestamps are ignored. Keep dates in a `date` question.
- **Excel bulk upload** (`upload/excel/{form_id}`): cannot link monitoring rows to parents, reports errors only by email, and is killed after 10 minutes. Don't use it for this flow.
- **Count records:** `GET form-data/{form_id}?page=1` returns `{total, ...}`.
