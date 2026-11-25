# User mails for a production upgrade

Every production upgrade sends two short mails to all OMERO users, in Dutch with
English below: an announcement before the downtime and a "back online" mail after
the smoke test passes. Mail 1 asks users not to start long work before the window
and to object in time if something important is running, because running work
(also on the HPC cluster) is stopped and its results can be lost. The mails are
for users, not administrators: no component versions, Slurm, storage formats or
other technical detail.

## Who does what

- The release coordinator drafts both mails in the release plan
  (`plans/releases/X.Y.Z.md`, section "User mails") with placeholders for
  everything site-specific. The plan is public, so nothing site-specific goes in.
- The production agent fills the placeholders from its private configuration
  (the site's public OMERO URL, contact address, times), sends a test to itself
  and a small group, then to everyone with `omero admin email --everyone`.
  Mail 1 goes out as early as possible, optionally again 30 minutes before the
  start with "Herinnering / Reminder:" before the subject. Mail 2 goes out only
  after the smoke test passes.

## Mail 2 from the release notes

Take the release's Major Features and keep only what users notice: three to five
one-line bullets in plain language, each saying what the user can now do and,
where it helps, where to find it in the interface. Leave out features that are
off at the site. Start the mail with a link to the site's OMERO, so users can try
it right away; the documentation link is secondary.

## Templates

Mail 1, announcement (one time, only what users must do; no reassurance that
contradicts the stop):

```text
Subject: OMERO [WHEN] offline [START]–[END] / OMERO offline [WHEN EN] [START]–[END]

(English below)

Beste OMERO-gebruiker,

[WHEN], [DATE], is OMERO van [START] tot ongeveer [END] offline voor een upgrade naar
NL-BIOMERO [VERSION].

- Start geen imports of BIOMERO-analyses meer die na [START] nog lopen.
- Wat om [START] nog loopt, ook op het HPC-cluster, wordt gestopt. Die resultaten gaan
  verloren; start het daarna opnieuw.
- Loopt er iets dat niet gestopt mag worden? Mail ons vóór [REPLY BY]: [CONTACT]

We laten het weten zodra OMERO weer beschikbaar is. Excuses voor het ongemak.

[TEAM]

---

Dear OMERO user,

[WHEN EN], [DATE EN], OMERO is offline from [START] until about [END] for an upgrade to
NL-BIOMERO [VERSION].

- Do not start imports or BIOMERO analyses that would still be running after [START].
- Anything still running at [START], including on the HPC cluster, is stopped. Those results
  are lost; start it again afterwards.
- Something running that must not be stopped? Mail us before [REPLY BY]: [CONTACT]

We will let you know when OMERO is back. Apologies for the inconvenience.

[TEAM]
```

Mail 2, back online:

```text
Subject: OMERO is weer beschikbaar / OMERO is back: nieuw in NL-BIOMERO [VERSION]

(English below)

Beste OMERO-gebruiker,

OMERO is weer beschikbaar. Probeer het meteen: [OMERO_URL]

Nieuw in deze versie:
[3-5 BULLETS IN DUTCH]

Werkt iets niet meer zoals voorheen? Neem contact op met [CONTACT] en vermeld wat u deed
en wanneer. Handleiding: [USER_GUIDE_URL]

Met vriendelijke groet,
[TEAM]

---

Dear OMERO user,

OMERO is available again. Try it now: [OMERO_URL]

New in this version:
[3-5 BULLETS IN ENGLISH]

Something not working as before? Contact [CONTACT] and mention what you were doing and
when. User guide: [USER_GUIDE_URL]

Kind regards,
[TEAM]
```
