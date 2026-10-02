# Branding coupling research

Read-only research against current repository and existing upstream checkout `/tmp/teslamate-amap-prepared-check`, whose HEAD is the reviewed `33d200b2fba9d5138803916a788cef5eae31b1aa`. No product files changed.

## Actual catalog changes

The branding patch touches 20 catalogs: 19 `default.po` locales plus `default.pot`. Each contains the same four singular messages; that is 80 selected entries. Only 24 selected `msgstr` values are nonempty and contain the application name. All 20 patch sections were checked programmatically: their removed/added lines differ exclusively by the literal substitution `TeslaMate` -> `GeoRelay`.

Known source message keys:

1. `To ensure that your <strong>Tesla API tokens are stored securely</strong>, an encryption key must be provided to TeslaMate via the <code>ENCRYPTION_KEY</code> environment variable. Otherwise, a <strong>login will be required after every restart</strong>.`
2. `You are using the API key (%{token}) provided by %{url}. It will allow your TeslaMate to access the official Tesla Fleet API and Tesla Telemetry streaming.`
3. `Discard this interrupted import? Its completed-file checkpoints and rejection report will no longer be used. Imported TeslaMate data is kept.`
4. `No vehicle was found when TeslaMate started. Once your vehicle shows up in the Tesla app, reload the vehicle list.`

Evidence: `patches/0003-georelay-branding.patch:203-335`, `:336-375`, `:964-1051`; the corresponding source template changes remain at `:17-42`, `:86-98`, `:169-177`.

## Minimal targeted conversion contract

- Retain the semantic template/root-layout/GPX changes as reviewed patches. Remove only the 20 mechanical catalog sections from the patch.
- Discover `.po`/`.pot` catalogs under `elixir/priv/gettext`; do not freeze the set or number of locales.
- Parse active PO entries sufficiently to concatenate quoted continuation lines of `msgid` and `msgstr`. Match the **decoded full msgid** against the four known keys above (or their already-renamed equivalent for idempotence). Never match a substring in the complete file.
- For only these selected singular entries, rename the source key and the application-name literal in its translation. Preserve `%{token}`, `%{url}`, HTML, other Tesla names, flags, `msgctxt`, source-reference comments, and unrelated entries. Empty translations stay empty. Obsolete `#~` entries should remain untouched.
- Rewriting the selected field as one correctly escaped quoted line is enough; preserving its upstream wrapping is unnecessary. Joining quoted literals is necessary because future wrapping can even split `Tesla` and `Mate` across lines. Use stdlib literal decoding/encoding; no new gettext dependency or complete PO parser is needed for these four singular fields.
- Preserve all other entries byte-for-byte, including legal credits, required disclaimer, and technical identifiers. Do not touch `.ex` source or lowercase `teslamate` identifiers. This scope, rather than a repository-wide text replacement, protects module/technical references. A regression fixture should include unrelated `msgid "TeslaMate.HTTP"`, a legal-credit message, comments containing module/path references, and the verbatim disclaimer and assert unchanged output.
- Avoid a Unicode word-boundary regex for translations: actual translations contain German `TeslaMate-Daten`, Korean `TeslaMate로`/`TeslaMate를`/`TeslaMate는`, and Chinese text adjoining the brand without spaces. Once an entry is selected by its exact known UI key, the existing literal replacement matches the reviewed semantics.
- Do not require every locale to contain every key; additions/removals should not force maintenance solely through catalog inventory. The still-reviewed source template patches plus runtime/rendered assertions establish that active UI keys are supported. The `default.pot` four-key conversion can be verified in the prepared real source check, rather than imposing fixture-sensitive locale counts.
- A selected known key gaining a plural/unsupported PO shape is an actual semantic contract change: stop or leave it for explicit review, do not silently corrupt it. A new unrelated string containing `TeslaMate` must not fail preparation merely due to its spelling.

## Replace broad guards with current behavior checks

`prepare_upstream.py:57-61` currently freezes all static filenames; `:72-83` rejects any remaining TeslaMate text in all templates/catalogs; `:66-71` checks exact markup fragments. These are implementation guards, not the wording of the upstream terms.

The agreed static contract removes complete-set equality. Remove the **known upstream branded artifacts**, tolerant of already-missing artifacts, then stage the neutral favicon. Preserve arbitrary nonvisual assets, including their internal TeslaMate text. Unknown new visual resources still stop for manual review because they might be upstream Logos; limit that gate to an explicit visual-file class rather than every static filename. Retain rendered checks that header/favicon references resolve to GeoRelay assets. Current finite tests still do not prove every future page is brand-clean; do not claim otherwise.

Keep the current 3-file byte-identical legal review gate and ensure it still runs before patching or branding mutations. `NOTICE:11-15` requires intact notice and marked modifications; `TRADEMARK.md:52,54` requires independent name, no Logos, no misleading official status; `:66-70` requires the exact prominent disclaimer. The proposed catalog/guard simplification changes none of those requirements.

## Rendered coverage and gaps

Current branding ExUnit test (`0003:1099-1128`) visits `/settings` only, in `en`, `de`, `zh_Hans`, despite its title saying every locale. It verifies title, navbar wordmark, footer disclaimer/source/legal credit, encryption warning, project link, and favicon. The second test (`:1133-1138`) checks neutral favicon delivery and absence of the two familiar upstream icon files. Existing modified car-index test (`:1069-1083`) covers the English empty-vehicle message; modified drive-controller test (`:1056-1061`) covers GPX creator.

**Not all four message uses are rendered/tested today.** The signin API-key prose and interrupted-import confirmation have no brand assertion in the selected CI tests. Localized car/import/signin output and every locale are not covered. Settings placeholder/documentation link text also lack an explicit assertion, though their reviewed template patch remains.

Smallest added check: retain the existing shared-layout/runtime checks and add a direct gettext regression across configured locales for all four renamed UI keys, interpolating `%{token}`/`%{url}` where needed; it should assert `GeoRelay` and preserve those placeholders/other Tesla product wording. This catches translation fallback/compilation behavior without setting up new signin/import integration fixtures. If asserting actual use at all four call sites is required, extend the already-existing page tests or render those known templates with their existing assigns; do not suggest the current settings-only test covers the full surface.

Python preparation fixtures should prove wrapped/continued keys and translations convert; unrelated legal/technical/brand strings remain unchanged; unrelated static additions and missing old branded assets succeed; old branded artifacts are removed; legal changes and true patch conflicts still stop before mutation. No blanket source-wide or locale-inventory assertion should be reintroduced through tests.
