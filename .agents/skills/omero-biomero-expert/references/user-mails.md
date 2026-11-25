# User mails for a production upgrade

Every production upgrade sends two short mails to all OMERO users. Mail 1 asks users not to start long work before the window and to object in time if something critical is running, because running work (also on the HPC) is cancelled and its results can be lost. in Dutch with English below: an announcement before the downtime and a "back online" mail after
the smoke test passes. They are for users, not administrators: no versions of
components, Slurm, storage formats or other technical detail.

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

Mail 1, announcement:

```text
Subject: OMERO-onderhoud / OMERO maintenance: [DATE] [START]–[END]

(English below)

Beste OMERO-gebruiker,

Op [DATE] is OMERO van [START] tot ongeveer [END] niet beschikbaar, omdat we upgraden
naar NL-BIOMERO [VERSION].

Wat betekent dit voor u?
- Start na [CUTOFF TIME] geen lange analyses of grote imports meer. Wat om [START] nog loopt,
  ook op het HPC-cluster, wordt gestopt; de resultaten daarvan kunnen verloren gaan en u moet
  het daarna opnieuw starten.
- Loopt er bij u iets belangrijks dat niet onderbroken mag worden, of komt dit tijdstip slecht
  uit? Laat het ons vóór [REPLY BY] weten via [CONTACT], dan zoeken we een oplossing.
- Uw opgeslagen data is veilig: we maken vooraf een volledige back-up.
- Tijdens het onderhoud toont de OMERO-website een onderhoudspagina.

We sturen een kort bericht zodra OMERO weer beschikbaar is.

Vragen? Neem contact op met [CONTACT].

Met vriendelijke groet,
[TEAM]

---

Dear OMERO user,

On [DATE], from [START] until about [END], OMERO will be unavailable while we upgrade it
to NL-BIOMERO [VERSION].

What this means for you:
- Please do not start long analyses or large imports after [CUTOFF TIME]. Anything still
  running at [START], including jobs on the HPC cluster, will be stopped; its results may be
  lost and you will need to start it again afterwards.
- Is something important running that must not be interrupted, or is this time a problem?
  Let us know before [REPLY BY] via [CONTACT] and we will find a solution.
- Your stored data is safe: we make a full backup before the upgrade.
- During the maintenance, the OMERO website shows a maintenance page.

We will send a short message when OMERO is back.

Questions? Contact [CONTACT].

Kind regards,
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
