# Mobile Data Collection — Step-by-Step Guide for Enumerators

**Who this guide is for:** field staff (enumerators / data collectors) who will use the
Akvo MIS mobile app on an Android phone or tablet to collect data, and the supervisors
who set them up.

**No technical knowledge is needed.** Follow the steps in order the first time. After
that, you will mostly repeat Steps 6–9 every working day.

---

## Contents

1. [First, understand the two kinds of forms](#1-first-understand-the-two-kinds-of-forms)
2. [What you need before you start](#2-what-you-need-before-you-start)
3. [Step 1 — Download and install the app](#3-step-1--download-and-install-the-app)
4. [Step 2 — Get your passcode](#4-step-2--get-your-passcode)
5. [Step 3 — Open the app and log in](#5-step-3--open-the-app-and-log-in)
6. [Step 4 — Find your way around the home screen](#6-step-4--find-your-way-around-the-home-screen)
7. [Step 5 — Sync once before you go to the field](#7-step-5--sync-once-before-you-go-to-the-field)
8. [Step 6 — Fill in a registration form](#8-step-6--fill-in-a-registration-form)
9. [Step 7 — Fill in a monitoring form](#9-step-7--fill-in-a-monitoring-form)
10. [Step 8 — Saving a draft and coming back later](#10-step-8--saving-a-draft-and-coming-back-later)
11. [Step 9 — Press Sync: what actually happens](#11-step-9--press-sync-what-actually-happens)
12. [Step 10 — Where your data goes on the server](#12-step-10--where-your-data-goes-on-the-server)
13. [Settings you may want to change](#13-settings-you-may-want-to-change)
14. [Troubleshooting](#14-troubleshooting)
15. [Glossary](#15-glossary)

---

## 1. First, understand the two kinds of forms

The whole app is built around one simple idea: **you register a thing once, then you
visit it again and again over time.**

### Registration form

A **registration form** creates a brand-new *datapoint*.

A datapoint is the thing you are collecting data about — a water scheme, a school, a
household, a borehole, a clinic. Registration is the **first-ever** questionnaire you
fill in for that thing. It usually asks for the permanent facts: the name, where it is
(GPS), who owns it, when it was built, what type it is.

> You fill in a registration form **once per thing, ever**. If someone else already
> registered that water scheme last year, you do **not** register it again.

### Monitoring form

A **monitoring form** adds a new visit to a datapoint that **already exists**.

Monitoring asks the questions that change over time: is it working today? what is the
water quality reading? how many people used it this month? is the pump broken?

A monitoring form is always **attached to a registration datapoint**. You cannot fill in
a monitoring form on its own — you first choose *which* registered thing you are
monitoring, and then the form opens.

### Side by side

| | Registration | Monitoring |
|---|---|---|
| **Purpose** | Create a new datapoint | Record a new visit / update to an existing datapoint |
| **How often** | Once per thing | Many times — monthly, quarterly, yearly |
| **Where you start it** | Home screen → the form → **New Submission** | Home screen → the registration form → pick the datapoint → **Monitoring Forms** |
| **Needs an existing datapoint?** | No | Yes — the datapoint must already be on your phone |
| **Typical questions** | Name, GPS location, type, owner | Condition today, readings, number of users, photos of the problem |

### A worked example

1. In January you visit **Nasinu Borehole 4** for the first time. It is not in the
   system yet, so you fill in the **registration form**: name, GPS, depth, year built.
   → This creates the datapoint.
2. In April you go back. The borehole already exists in the app, so you open it and fill
   in the **monitoring form**: is it functioning, water quality reading, photo of the
   pump.
3. In July you go back again → another **monitoring form** on the same borehole.

One registration. Many monitoring visits.

### Important: monitoring only works after a sync

A monitoring form needs the registration datapoint to be *on your phone*. There are two
ways it gets there:

- **You registered it yourself on this phone**, or
- **You pressed Sync** and the app downloaded it from the server — this is how you
  monitor things registered by a colleague, or registered before your phone existed.

This is the single most common reason a new enumerator cannot find the datapoint they
want to monitor: **they have not synced yet.** See [Step 5](#7-step-5--sync-once-before-you-go-to-the-field).

---

## 2. What you need before you start

- An **Android** phone or tablet.
- An **internet connection** — for the download, the first login, and for syncing. You
  do **not** need internet while you are actually filling in forms.
- Your **passcode** — see [Step 2](#4-step-2--get-your-passcode).
- The **address of your MIS server**, for example `http://localhost:3000` when you are
  testing on a local installation, or your organisation's real web address. Your
  supervisor will tell you which one to use.

> **Note on `localhost:3000`:** this address only works on a computer that is running
> the system locally — a phone cannot reach it. On a real phone you use the address your
> organisation gives you (for local testing, your computer's IP address, e.g.
> `http://192.168.1.20:3000`).

---

## 3. Step 1 — Download and install the app

1. On the device, open a web browser.
2. Go to your MIS address followed by **`/app`**, for example:

   ```
   http://localhost:3000/app
   ```

   This link is not a page — it immediately starts downloading the app installer file
   (an `.apk` file, named something like `akvo-mis-mobile.apk`).
3. When the download finishes, tap the downloaded file to install it.
4. Android will most likely warn you that the app is not from the Play Store and ask you
   to **allow installation from this source**. Tap **Settings**, switch the permission
   on, then go back and tap **Install**.
5. When it finishes, tap **Open** — or find the app icon in your app drawer.

> If `/app` shows an error instead of downloading, the installer has not been uploaded to
> your server yet. Tell your administrator; nobody can install the app until that is done.

---

## 4. Step 2 — Get your passcode

You do **not** log in with an email and password. You log in with a **passcode** — a
short code that the system generated for you.

The passcode is more than a password. It carries your whole work assignment with it:

- **which forms** you are allowed to fill in (registration and monitoring), and
- **which areas** (villages, districts, provinces) your data will be filed under.

That is why it is sometimes called a *mobile assignment*.

### Option A — Ask your supervisor (most common)

Ask the person who manages the platform for "my mobile assignment passcode". They will
read it out or send it to you. It looks like a random string of about 8 characters.

Tell them which forms and which area you need — they set that up at the same time.

### Option B — Create it yourself (if you have access to the web platform)

If you can log in to the MIS website and your account has permission to manage mobile
assignments:

1. Log in to the platform in a web browser.
2. Go to **Control Center**, then in the sidebar open **Users** → **Manage Mobile Users**.
   The page is titled **Mobile Data Collectors**.
3. Click **Add new data collector**.
4. Fill in:
   - **Name** — a label so you can recognise it later, e.g. "Deden – Nasinu district".
   - **Forms** — tick the forms this device may use. Registration forms are shown as the
     parent, and their monitoring forms are listed underneath. **Ticking a monitoring
     form automatically ticks its registration form**, because monitoring cannot exist
     without registration.
   - **Administration / area** — the village, district or province this device collects
     data for.
5. **Save.**
6. Back on the list, **expand the row** you just created. A small panel shows the Name,
   **Passcode**, Administration(s) and Forms. Use the copy button next to the passcode —
   this is what you type into the phone.

You do not choose the passcode yourself; the system generates it when you save. If you
lose it, expand the row again and read it — it is always visible there.

> This menu is hidden from the super admin and from the top-level administrator, on
> purpose: those accounts have no known subordinates to assign. If you cannot see
> **Manage Mobile Users**, ask an admin at your own administrative level.

> **Keep it private.** Anyone with your passcode can submit data as you, from any device.

---

## 5. Step 3 — Open the app and log in

1. Open the app. The first screen says **Get Started**.

   <img src="../docs/assets/mobile-auth-1.png" alt="The Get Started welcome screen" width="300">

2. If a box labelled **Input Server URL** appears, type the address of your MIS server
   (the same address your supervisor gave you) and continue. If no box appears, the
   address is already built into the app — just carry on.
3. Tap **Get Started**.
4. On the login screen, type your **passcode** into the *Enumerator passcode* box.
   - Tap the **eye icon** on the right of the box to reveal what you typed and check it.
     The screen reminds you: **the passcode is case sensitive**. It is easy to mistype.
   - The **app version** is shown at the bottom of this screen — useful when reporting a
     problem.

   <img src="../docs/assets/mobile-auth-2.png" alt="The passcode login screen" width="300">

5. Tap **LOG IN**.

**What the app does at this moment** (you need internet here):

- It checks the passcode against the server.
- It downloads **every form** in your assignment — registration and monitoring.
- It downloads the **lookup lists** those forms need: your administrative areas
  (province → district → village), organisations, and entity lists. These are what make
  the dropdowns work later when you are offline.
- It saves all of this **inside the phone**, so the app works with no signal from now on.

The first login can take a minute or two on a slow connection. When it finishes you land
on the home screen.

If you see *"Invalid enumerator passcode"*, the code is wrong or was deleted — check it
with your supervisor. If you see *"No connection"*, you are offline; the **first** login
must be done online.

---

## 6. Step 4 — Find your way around the home screen

The home screen is called **Form Lists**.

<img src="../docs/assets/mobile-homepage.png" alt="The Form Lists home screen with form cards and the Sync Datapoint button" width="320">

It shows:

- **Your user name**, just under the title.
- **The list of forms** you are allowed to use, as cards. Each card shows the form
  **Version** and three running counts:
  - **Submitted** — completed on this phone,
  - **Saved** — unfinished drafts,
  - **Synced** — already delivered to the server.
- A **search box** to find a form quickly when the list is long.

  <img src="../docs/assets/mobile-home-search.png" alt="Typing in the search box filters the form list" width="480">

- A blue **Sync Datapoint** button, floating at the bottom.
- The **person icon** (top-left) opens the **Users** page, which shows which passcode
  this phone is currently logged in with.

  <img src="../docs/assets/mobile-home-users.png" alt="The person icon opens the Users page" width="480">

- The **⋮ menu** (top-right) opens **Settings**.

  <img src="../docs/assets/mobile-home-settings.png" alt="The three-dot menu opens Settings" width="480">

At the very bottom, a coloured bar sometimes appears. That is the status bar. It tells
you what the app is doing right now:

| Bar | Meaning |
|---|---|
| Red — *"You're offline…"* | No internet. You can still collect data; it will sync later. |
| Blue — *"Uploading submissions…"* | Your completed forms are being sent to the server. |
| Blue — *"Downloading datapoints… 40%"* | Existing datapoints are being pulled from the server. |
| Green — *"Done!"* | Sync finished successfully. Disappears after a few seconds. |
| Red — *"Unable to sync. Please try again."* | Something failed. See [Troubleshooting](#14-troubleshooting). |

---

## 7. Step 5 — Sync once before you go to the field

**Do this while you still have internet, before you travel.**

Tap **Sync Datapoint** on the home screen and wait for the green **Done!**. While it
runs, the button itself changes to **Syncing…** and cannot be tapped again.

<img src="../docs/assets/mobile-sync.png" alt="Tapping Sync Datapoint turns the button into Syncing" width="520">

This pulls down the registration datapoints that already exist on the server for your
area. Without it, the **Monitoring Forms** list will be empty for datapoints you did not
create yourself, and you will not be able to do your monitoring visits.

Depending on how many datapoints exist in your area, this can take a while the first
time. Later syncs are much faster, because the app only fetches what has changed since
your last sync.

---

## 8. Step 6 — Fill in a registration form

Use this when the thing you are looking at is **not yet in the system**.

1. On the home screen, tap the **registration form** you need.
2. You now see the list of submissions already made with that form. If nothing has been
   collected yet it says **"No data collected yet — Click New Submission to begin"**.
   Have a quick look — **is the thing you are about to register already in the list?**
   If it is, do not register it again; do a monitoring submission instead
   ([Step 7](#9-step-7--fill-in-a-monitoring-form)).
3. Tap the **New Submission** button at the bottom.

   <img src="../docs/assets/mobile-registration.png" alt="From the home screen, open the registration form, tap New Submission, fill it in and Submit" width="720">

4. Answer the questions.
   - Questions marked with a red asterisk (**\***) are required and must be answered
     before you can submit.
   - The form is split into **sections (question groups)**. Use **Next** and **Back** at
     the bottom to move between them. The counter in the middle (for example **5/8**)
     shows which section you are on.
   - Tap that **counter** to open the list of sections and jump straight to any of them:
     - **Blue dot** = that section is complete and valid.
     - **Grey dot** = something in that section is still missing.

     <img src="../docs/assets/mobile-submit-1.png" alt="Tapping the section counter shows all sections with blue and grey status dots" width="560">

   - For a **GPS question**, tap **Use current location** / **Refresh location** and wait
     for the reading to settle. If it says *Accuracy: Low Precision*, go outdoors and
     wait a few more seconds before accepting it.
   - For a **photo question**, tap **Use Camera** or pick from the gallery. The photo
     stays on the phone until you sync.
5. When every section is blue, tap **Submit**.
6. You will see **"Data point submitted"**. The submission is now stored on the phone,
   waiting to be sent.

The new datapoint immediately appears in the list, marked with an **orange clock icon**
(waiting to sync). After a successful sync it changes to a **green tick** and the green
**Done!** bar appears at the bottom.

<img src="../docs/assets/mobile-submit-2.png" alt="After Submit the datapoint shows a clock icon, then a green tick once synced" width="720">

---

## 9. Step 7 — Fill in a monitoring form

Use this when the thing already exists — either because you registered it, or because it
came down in a sync.

1. On the home screen, tap the **registration form** that the datapoint belongs to.
   (Yes — you start from the *registration* form. That is where the datapoints live.)
2. Find the datapoint you are visiting in the list. Use the search box at the top — it
   searches by datapoint name.
3. **Tap the datapoint.** A screen opens, titled with the datapoint's name, holding two
   sections:
   - **Datapoint → View details** — read the answers already recorded, to confirm you
     have the right place.
   - **Monitoring Forms** — the list of monitoring forms available for this datapoint.
4. Tap the **monitoring form** you need.

   <img src="../docs/assets/mobile-monitoring.png" alt="Tap a datapoint, then choose a form under Monitoring Forms, then fill it in and Submit" width="720">

5. You now see the list of monitoring visits already recorded for that datapoint. Tap
   **New Submission** to start a new visit.
6. Some answers are **pre-filled** from the registration (name, location, and other
   fields that do not change). Check them, correct them if reality has changed, and fill
   in the rest.
7. Tap **Submit**.

The monitoring submission is stored on the phone with a clock icon, exactly like a
registration, and is sent on the next sync.

> **The datapoint is not in the list?** Three usual reasons: (a) you have not synced —
> go back to [Step 5](#7-step-5--sync-once-before-you-go-to-the-field); (b) the datapoint
> is outside the area assigned to your passcode; (c) it was never registered — in which
> case you should do a registration first.

---

## 10. Step 8 — Saving a draft and coming back later

You do not have to finish a form in one sitting. Tap the **⋮ menu** in the top-right
corner of the form, and a small menu offers two choices:

- **Save as Draft** — keeps everything you have typed so far and closes the form.
- **Exit without Saving** — throws away what you typed in this session. The app asks
  *"Are you sure want to exit form submission?"* — tap **Exit** to confirm or **Cancel**
  to go back. There is no undo.

<img src="../docs/assets/mobile-exit.png" alt="The form menu offers save or exit, and exiting asks for confirmation" width="560">

> In some older versions of the app, **Save as Draft** is labelled **Save and Exit**, as
> in the screenshots. It does the same thing.

### Finding your draft again

Open the same form and tap the **document-with-clock icon** in the top-right corner of
the submission list. That switches the list from *submitted* to *saved drafts*. Drafts
carry a yellow **Draft** badge. Tap one to carry on filling it in. Tap the **✕** in the
same corner to go back to the submitted list.

A small **red dot** on that icon means you have drafts waiting.

<img src="../docs/assets/mobile-exit-save.png" alt="Saving as draft, then reopening it from the drafts icon in the top-right corner" width="720">

Drafts are **not** counted as collected data and do not go through approval until you
finish them and tap **Submit**.

---

## 11. Step 9 — Press Sync: what actually happens

Everything you collect stays **on the phone** until it is synced. Syncing is the moment
your work reaches the office.

### The two ways sync happens

- **Automatically.** The app syncs in the background on a timer (by default about once
  an hour, adjustable in Settings). If it is set to Wi-Fi only, it waits for Wi-Fi.
- **Manually.** You tap **Sync Datapoint** on the home screen. That is the only manual
  sync button — there is nothing to press inside a form.

Do a manual sync whenever you come back into signal, and at the end of every working day.

<img src="../docs/assets/mobile-submit-3-manual.png" alt="A manual sync in progress and finished: the Synced count increases and a notification confirms it" width="640">

While it runs, the button reads **Syncing…** and a blue bar sits at the bottom. When it
finishes, the bar turns green (**Done!**), a notification says *"Sync submission
completed"*, and the **Synced** count on each form card goes up.

### What happens, in order, when you press Sync

Sync goes **both ways** — it pushes your work up and pulls other people's work down.

**1. Your completed submissions are uploaded (push).**

Bar reads *"Uploading submissions…"*.

The app takes your submitted-but-not-yet-synced forms in batches of about 20 and, for
each one:

- Uploads the **photos, attachments and signatures** first, a few at a time, and gets
  back a server location for each file.
- Sends the **answers** — with those file locations swapped in — to the server.
- On success, marks that submission with a **green tick** and deletes the local copies of
  the uploaded photos to free up storage on the phone.

Each submission carries a unique key, so if the connection drops and the app retries, the
server recognises the repeat and stores it **once**, not twice.

If one submission fails, it is put back in the queue and retried on the next sync — the
others still go through. Nothing is lost or silently discarded.

**2. Drafts are synced.**

Bar reads *"Syncing drafts…"*. Unfinished drafts are backed up to the server so they are
not lost if the phone is damaged. They are stored as drafts, not as real data, and do not
enter the approval process.

**3. Your forms and lookup lists are refreshed.**

The app re-checks your passcode with the server and:

- **Downloads new or updated forms.** If your supervisor edited a questionnaire or
  assigned you a new one, you get it here.
- **Removes forms** that were taken off your assignment.
- **Re-downloads the lookup lists** — administrative areas, organisations and entity
  lists — so your dropdowns stay current.

**4. Existing datapoints are downloaded (pull).**

Bar reads *"Downloading datapoints… 60%"* with a progress percentage.

The app fetches the registration datapoints for your assigned area, one form and one page
at a time, and stores them on the phone. **These are the datapoints you will be able to
monitor.** Only what is new or changed since your last sync is downloaded, which is why
the first sync is slow and later ones are quick.

Two safety rules apply here:

- A datapoint on your phone that has **unsent changes** is never overwritten by the
  server copy. Your unsynced work always wins.
- The download can be interrupted (signal lost, app closed) and it will **resume from
  where it stopped** on the next sync rather than starting over.

**5. Finish.**

Bar turns green — **"Done!"** — and disappears after a few seconds. A notification also
appears. Your submissions now show green ticks, and any newly downloaded datapoints are
available for monitoring.

### If it fails

The bar turns red: *"Unable to sync. Please try again."*, sometimes with a count of
failed items. Nothing is deleted. The failed items stay in the queue and are retried on
the next automatic or manual sync. Common causes are in [Troubleshooting](#14-troubleshooting).

### The short version

| Direction | What moves |
|---|---|
| **Phone → Server** | Completed submissions, photos and attachments, drafts |
| **Server → Phone** | New/updated forms, administrative and entity lists, existing registration datapoints |

---

## 12. Step 10 — Where your data goes on the server

Once a submission reaches the server:

- It is filed under the **administrative area** attached to your passcode (or the area you
  chose in the form, if the form asks for one), and recorded under your name as
  submitter.
- If the form has an **approval workflow**, the submission becomes **pending**. A
  supervisor sees it in the **Approvals** page and either approves it or rejects it with
  a comment. Only once approved does it become official data.
- If the form has **no approvers**, it becomes data straight away.

Your phone is not told the approval result, so if a submission is rejected your
supervisor will contact you directly. On the phone, a **green tick simply means
"delivered to the server"** — not "approved".

Approved data appears on the web platform under **Manage Data**, feeds the dashboards,
and can be exported to Excel from the **Downloads** page.

---

## 13. Settings you may want to change

Open **Settings** from the **⋮ menu** in the top-right of the home screen.

### Advanced

<img src="../docs/assets/mobile-settings-1.png" alt="Settings, Advanced: server URL, passcode, sync interval and sync Wi-Fi" width="560">

- **Server URL** — the address of your MIS server. Shown for reference; you cannot edit
  it here.
- **Passcode** — the passcode this phone is logged in with. Handy if you have forgotten
  it, but treat this screen as sensitive.
- **Sync interval** — how often the app syncs by itself, **in seconds**. Shorter means
  fresher data and more battery and data use.
- **Sync Wifi** — when on, automatic sync waits for Wi-Fi. Turn this on if mobile data is
  expensive. You can still tap **Sync Datapoint** to force a sync at any time.

### Geolocation

<img src="../docs/assets/mobile-settings-2.png" alt="Settings, Geolocation: GPS threshold, accuracy level and timeout" width="560">

- **GPS threshold** — how far off the GPS reading is allowed to be, in metres, before the
  app complains.
- **Accuracy level** — higher accuracy is more precise but takes longer to get a fix.
- **Geolocation timeout** — how many seconds the app waits for a GPS reading before
  giving up.

### Image Quality

- **Compression Level** — how much photos are shrunk before upload. Higher compression
  means smaller files and faster syncing over a weak connection, at the cost of detail.

### Language

Switch the app interface language (English / French).

### About, and updating the app

**About** shows the app version — have it ready when reporting a problem. If a newer
version exists, tap **Update application**, then **Update** in the dialog. Do this on
Wi-Fi. Sync your work **before** updating.

<img src="../docs/assets/mobile-update-version.png" alt="Settings, About, then Update application prompts to install the new version" width="720">

> **Reset** on the Settings screen erases all local users, forms and datapoints,
> including anything not yet synced. Never use it unless support tells you to.

---

## 14. Troubleshooting

| Problem | What to do |
|---|---|
| *"Invalid enumerator passcode"* at login | Check for typos (tap the eye icon). Confirm the passcode with your supervisor — it may have been deleted or replaced. |
| *"No connection"* at login | The **first** login needs internet. Move to a place with signal or Wi-Fi and try again. |
| `/app` does not download anything | The installer has not been uploaded to the server. Tell your administrator. |
| Android blocks the installation | Allow *install from unknown sources* for your browser in Android settings, then tap the downloaded file again. |
| The form I need is not in the list | It is not on your assignment. Ask your supervisor to add it, then press **Sync Datapoint**. |
| **Monitoring Forms** section is empty for a datapoint | No monitoring form is assigned for that registration form — ask your supervisor. |
| The datapoint I want to monitor is missing | Press **Sync Datapoint** while online. If still missing, it is outside your assigned area or was never registered. |
| Submissions still show a clock icon | They have not synced yet. Get online and press **Sync Datapoint**. |
| Red bar: *"Unable to sync"* | Check you really have internet; check whether **Sync Wi-Fi only** is on; try again in a better signal. If it keeps failing, note the failed count and contact support. |
| A submission shows **"File missing"** | The photo file was deleted from the phone, so it can never upload. Open that submission, **retake the photo** or **re-attach the file**, then sync again. |
| Sync is extremely slow the first time | Normal — it is downloading every existing datapoint in your area. Later syncs only fetch changes. |
| Phone is full | Sync. Uploaded photos are removed from the phone automatically once they reach the server. |

**Never** use *Reset* in Settings as a fix — see the warning in
[Settings](#13-settings-you-may-want-to-change). It erases everything on the phone,
including work that has not been synced.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **Enumerator** | The field worker collecting data. You. |
| **Passcode / mobile assignment** | The code you log in with. It carries your forms and your assigned area. |
| **Datapoint** | The real-world thing you collect data about — a scheme, a school, a household. |
| **Registration form** | The form that creates a new datapoint. Filled once per thing. |
| **Monitoring form** | A follow-up form attached to an existing datapoint. Filled every visit. |
| **Draft / saved** | A form you started but have not submitted. |
| **Submitted** | A completed form stored on the phone, waiting to be sent. |
| **Synced** | Sent to the server. Shown with a green tick. |
| **Administration** | The geographic or organisational hierarchy — province → district → village. |
| **Pending / approval** | A submission on the server waiting for a supervisor to approve it. |
