# Akvo Chronicle: product roadmap,  2026 –  2027

Akvo Chronicle is an open-source, AGPLv3-licensed platform for longitudinal
entity monitoring. Register the thing you're tracking once (a water point,
a school, a household, a borehole, a coral reef) and every visit after that
adds to its history. This roadmap sets out where the platform is going over
the next 12 months, in priority order.

## Where Akvo Chronicle stands today

The platform already does more than collect forms. A programme configures
its own forms, indicators and administrative structure, and changes take
effect without a software release. A subject specialist can build a form
directly in the graphical builder, no developer required.

Field teams collect data offline on Android, and it syncs automatically once
they're back online. Every submission attaches to a registered entity, so
staff can see whether a water point, school or household is improving or
declining over repeated visits.

Approvals follow a programme's own administrative structure, and every
change is tracked, so there's a clear record of who approved what.

Akvo has run monitoring programmes at national scale in Kenya, Fiji, the
Central African Republic, Haiti, Somalia/Puntland, Tanzania and Liberia,
including work with the World Bank and UNICEF. The code is public under
AGPLv3, the platform is free to use, and a client can pull their full
dataset out in open formats whenever they want, with or without Akvo's
help. The platform is also multi-tenant: an organisation can provision its
own independent instance directly, under the open-core model, without
waiting on Akvo to set one up.

## Foundational capability stays open

For complex deployments, Akvo also supports client engagements directly:
custom feature development, configuration and broader data services. When
that work adds a new foundational capability to the platform, every Akvo
Chronicle user gets it, whether or not they funded the build. Client-specific
configuration stays with that client.

## Roadmap

### 1. Self-service, no-code dashboards — Q3 2026

Right now, building a dashboard means asking Akvo or a partner to do it. By
Q3 2026 that changes: an admin user adds widgets, defines variables and
puts together a view themselves, without writing code or opening a support
ticket. This also has to land before the AI-assisted
dashboard work in the next item. An assistant that builds dashboards needs
the same no-code layer a human would use.

### 2. Deep AI integration — Q4 2026, alongside public launch

Four pieces, roughly in the order one depends on the next.

An in-app assistant, trained on Akvo Chronicle's user guides and support
docs, that answers "how do I set up an approval chain" or "why did this
submission fail validation" without sending someone off to a manual. Akvo
already builds retrieval-augmented knowledge systems for other platforms;
this brings that work into the product itself.

AI-assisted questionnaire configuration: an administrator describes what
they want to measure and gets back a draft form (question types, skip
logic, validation) to review and adjust in the existing builder before it
publishes.

The same pattern applied to dashboards: describe the indicator, get a draft
widget back, review it before it goes live.

And natural-language insight queries. A user asks a question in plain
language, and the assistant turns it into a query against data already
collected instead of a general web answer. None of this exists yet. These
are the kind of questions it should be able to answer for a WASH
deployment:

- "How many water points in Turkana have been non-functional for more than
  90 days?"
- "Show the trend in failed water-quality tests for boreholes in this
  district over the last two years."
- "Which sanitation facilities failed their handwashing-access check this
  quarter, and in which sub-counties?"

Right now, answering any of those means a configured dashboard or a manual
export. The point is to answer them directly, in the tool.

### 3. Migration tooling from standalone data collection tools — Q4 2026, alongside public launch

An organisation running KoboToolbox, ODK or similar has no supported way in
today. Moving means rebuilding every form from scratch and hand-importing
raw exports. By Q4 2026 we want an import path for form definitions and
historical data from these tools, so switching to Akvo Chronicle doesn't
mean losing years of records.

### 4. Sector-specific pre-loaded questionnaires — Q4 2026, alongside public launch

Setting up a new deployment starts from a blank form today. By Q4 2026,
sector-specific libraries change that. A WASH deployment starts pre-loaded
with JMP-aligned questionnaires for schools, health care facilities and
households.

An agriculture deployment starts with farmer-focused questionnaires, and a
climate deployment starts with drought-monitoring instruments. Each library
builds on the existing form builder, so a team adjusts a ready instrument
instead of starting from zero.

### 5. Interoperability and open connectors — Q1 2027

There's no native connector to another sector information system today.
Interoperability today means a documented API for reading and submitting
data. That's useful, but it puts the integration work on whoever's
connecting to us. Three connectors would close specific gaps:

- Data loggers, so automated groundwater readings land in the same record
  as an enumerator's visit.
- Spatial platforms like GeoNode, so the point and boundary data already in
  Akvo Chronicle can be published to and pulled from a shared spatial
  layer.
- Open-data catalogues like CKAN, so a programme's monitoring data can go
  into a national or sectoral open-data catalogue as part of the normal
  export path.

### 6. Crowdsourced data collection via messaging channels — Q1 2027

Data collection today assumes an enumerator with the Akvo Chronicle app. By
Q1 2027, three messaging adapters open a crowdsourced channel alongside it:
WhatsApp, SMS and Facebook Messenger. A community member reports a broken
pump or a contaminated water source through a channel they already use, and
it lands in the same entity record as a trained enumerator's visit. It
still moves through the same approval workflow before counting as verified
data.

### 7. Complete Digital Public Goods registration — Q1 2027

Akvo has already submitted Akvo Chronicle for Digital Public Goods Alliance
registration. What's left is finishing that process by Q1 2027. Open
licensing under AGPLv3 already covers the DPG Standard's licensing
indicator.

The rest of the indicators haven't been checked against Akvo's current
documentation yet: data ownership and export, privacy and do-no-harm, use
of open standards, platform independence. We're flagging that here as work
for the product and legal teams to confirm. We're not claiming it's already
handled.


