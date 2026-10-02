# README layout references

Checked on 2026-10-02 using GitHub REST API metadata and the README returned at each recorded commit. Star counts are a snapshot, not a quality score.

| Project | Stars | Default branch | README reviewed |
| --- | ---: | --- | --- |
| Immich | 115,459 | `main` | [5372d5e](https://github.com/immich-app/immich/blob/5372d5ef19eb3ee3eddf8002ba404e99cdfe330e/README.md) |
| Syncthing | 89,103 | `main` | [05b6704](https://github.com/syncthing/syncthing/blob/05b6704ef5080b8013c690b83b831d0dbedca5a0/README.md) |
| RustDesk | 125,000 | `master` | [fada664](https://github.com/rustdesk/rustdesk/blob/fada664df7a294d1d1a9ca3e7cd3637069122f17/README.md) |

## Patterns to use

1. **Put language choice at the top.** RustDesk places its section navigation and translated README links together near the title; Immich links translated files before its main sections. This project only needs `English | 简体中文`, with the current language as plain text and the other as a relative link. Both files should have the same sections and screenshot sources.
2. **Keep the opening small.** Immich uses a title, a short description, and a visual preview. Use a plain project title, a sentence describing TeslaMate plus mainland AMap address lookup, and the required unofficial-project statement. Avoid a release number in the title or identity paragraph.
3. **Provide direct routes through the page.** RustDesk has a compact row of section anchors. Use `Getting started · Features · Screenshots · Updates · Documentation`, translated in the Chinese file. Installation should identify the patched TeslaMate image and adapter, then link to the detailed guide rather than reproducing a full stack.
4. **Group the screenshots and identify their source.** RustDesk gives screenshots their own section with meaningful captions; Immich uses one large overview image. Keep the three required upstream TeslaMate images in one section, with concise captions and a source note. One overview image followed by two secondary images, optionally in a native `<details>` block, keeps the page readable without a complex HTML layout.
5. **Move operational detail out of the homepage.** Syncthing links a separate Docker README and documentation site, while its main README remains short. Keep configuration tables, SQLite backup instructions, failure semantics, and build commands in the AMap guide. The homepage can describe the stable-release tracking process and link `upstream.json` for the currently pinned build version.

Only the information order and navigation pattern are references. Do not copy these projects' logos, badges, star widgets, marketing claims, or installation commands. Current README styles also include elements we do not need, such as a long translation list, activity charts, and a complete platform build matrix.
