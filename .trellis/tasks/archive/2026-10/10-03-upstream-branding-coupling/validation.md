# Validation

## Outcome
- Branch: enhanced-hedgehog; scoped to upstream branding preparation, tests and documentation.
- Fresh official source: v4.3.0 / 33d200b2fba9d5138803916a788cef5eae31b1aa.
- Branding patch existing production-file footprint: 27 -> 7. The 20 gettext diff sections are removed.
- Fixed pin, strict patches, 3-file legal byte-review guard and unknown new visual-resource review remain.

## Checks
1. Baseline Python: 89 tests passed.
2. Final full Python after Unicode decoder fix: 91 tests passed.
3. Real offline Git preparation regressions: 10 tests passed; unrelated internal identifiers and nonvisual static files preserved, missing old icons allowed, unknown visuals still stopped before patching. Wrapped strings/CRLF/Unicode/escape/contexts/comments/obsolete entries and idempotence covered; selected plural shape rejected without corrupting the catalog.
4. Fresh prepare against pinned official tag succeeded with all current patches.
5. Independently reconstructed all 20 old catalog diff sections from original upstream Git blobs and applied the old branding patch in a disposable directory. All decoded active field semantics match the new prepared output: 20 catalogs / 80 renamed message entries. All 3 upstream legal originals are byte-identical.
6. Actual isolated Docker format, warnings-as-errors compile and selected ExUnit suite: 176 passed. Shared-layout rendering and four gettext messages cover all known locales; token/url interpolation is preserved.
7. Native linux/arm64 app and adapter Docker builds passed. Both images have the expected architecture and non-root UID; bundled LICENSE/NOTICE/TRADEMARK/MODIFICATIONS checks passed as applicable.
8. Adapter health passed with network none, no host port and a disposable data volume. Temporary container/volume removed.
9. Reviewer fixed use of splitlines(): literal U+2028/U+0085 in a quoted translation are not PO physical line separators. Decoder now splits only LF, with regression.
10. First real ExUnit run found one invalid new assertion requiring English Tesla in every translated API-key message. Chinese upstream correctly says 特斯拉. Removed only that assertion; GeoRelay, no-TeslaMate and actual token/url interpolation remain. Final 176-test run passed.
11. Final fresh preparation after the fixes has 298 byte-identical Docker production input files to the already-built verified images; changes after those builds only affect tests/decoder behavior on the new Unicode regression.
12. Full-scope trellis-check found no remaining scoped issues. git diff --check and Python compile checks passed.

## Limits and coordination
- No cloud amd64/arm64 run was started; native arm64 verification must not be described as full multiarchitecture CI success. CI still retains both native architecture jobs.
- Main application + temporary database startup smoke work is separately owned by user-specified agent 6a15578b-7e7b-4723-8171-019691cb9cfa on feat/beta-review-release. Its completion notification reports local arm64 success; that separate branch is not integrated here.
- The finite message mapping covers the current four known UI messages. New public brand copy requires maintaining the mapping/rendered tests; no claim that every future page is automatically brand-clean.
- No production service/data, external registry, main merge or remote publication was changed by this task.
- Raw test/build output stayed in temporary local logs; only summarized assertions are recorded here.

## Review
Implementation and independent Trellis review completed. Current changes are ready for branch review and future dualarchitecture CI.
