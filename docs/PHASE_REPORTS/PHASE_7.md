# Phase 7 — reliability and academic handover

Date: 2026-11-01 (Australia/Sydney). Implementation delivered and installed as **0.7.0**. Automated, real-corpus recovery and accelerated editing validation complete. Multi-day author acceptance and explicit v1.0 sign-off remain pending; no release publication or tag was created.

## Author experience

USER_GUIDE.md now starts with academic work: finding remembered passages, comparing arguments, reviewing terminology/people/chronology, saving summaries and maps, following a revision's implications, and deciding what to do with suggestions. It uses ordinary-language example questions and explains evidence limits without command syntax, database terminology or installation details. OPERATIONS.md holds the technical setup, privacy, backup, recovery and startup instructions. CODEX_WORKFLOW.md now uses the implemented setup --codex option instead of implying that a separately running terminal connects Codex automatically.

## Reliability changes

- backup snapshots the index, analysis/review data if present, and configuration to a new private directory. backup-check validates checksums, supported schema/identity, SQLite integrity/foreign keys and analysis dependency provenance.
- restore verifies before and after copying into a separate new directory. It does not overwrite damaged/current data, activate the recovery, or modify Word files. The copied configuration is historical reference; activation uses the existing book configuration with an explicit new data_dir.
- Shared writer locks and an exclusive backup lock coordinate application operations; SQLite write reservations protect snapshot inputs. Readers remain read-only. Handled failures clean new partial outputs; interrupted directories marked .incomplete are rejected.
- setup --codex creates book-specific AGENTS.md instructions without replacing existing files or symlinks. Commands include an exact executable/config path and cover queries, analysis and maintenance.
- scripts/install.sh installs locally without changing shell profiles. startup generates an optional macOS LaunchAgent plist without loading it. Output is discarded rather than accumulating logs. No service was installed.
- Missing-source messages no longer say a revision was retained when the document never had a successful revision.

## Executed validation

**112 regression tests pass** (recorded final test run 1.82 seconds), lint and formatting pass. Coverage includes corrupt active-index recovery; damaged/incomplete backups, symlinks and path traversal; no-overwrite/source-overlap guards; preserved analysis review history; lock exclusion and read availability; simulated disk failure; schema-1 backup/restore followed by backed-up migration; and mismatched analysis dependencies. Earlier extraction, transaction rollback, revision, native/polling and analysis tests remain in the suite.

A separate clean Python environment was created under .verify/phase7/clean, with a non-editable installation and pinned watchdog. The local install script was also exercised against the existing editable installation. Both report 0.7.0. Installed-command walkthroughs are recorded alongside the private release artifacts.

The generated startup file passed Apple's plutil -lint. This is structural validation, not proof of actual login behavior. No launchctl activation or user login restart was performed.

## Real-book measurements and recovery

All 17 configured DOCX files were extracted and independently ingested into a private benchmark index. They total **2,361,143 bytes**; the largest file is **283,535 bytes**. Timings on this Mac (one local corpus, warm caches possible):

| Operation | Measured time |
|---|---:|
| Extract all 17 files | 0.341 s |
| Ingest into new index | 0.458 s |
| Re-ingest unchanged corpus | 0.008 s |
| Search, median of 15 runs across five terms | 0.036 s |
| Search, slowest of those runs | 0.116 s |
| Update an edited private copy of the largest source | 0.068 s |
| Snapshot real index/analysis/configuration | 0.036 s |

The real snapshot was verified and restored under .verify/phase7/recovered-data. The restored source status was current, saved analysis counts matched, and searches for three representative terms returned exactly the same records as the original. Both live database hashes were unchanged. All 17 Word source hashes were unchanged. The active book configuration was not switched. Private artifacts and detailed measurements: .verify/phase7/results.json and verified-backup/.

Two bounded accelerated editing trials each made **40 atomic replacement saves** of a synthetic DOCX: one with native events, one with polling. Both ended with the exact latest marker retrievable, current freshness and clean watcher exit. Intermediate saves may be coalesced by debounce; the test does not require retaining every transient version. It is not a multi-day Word/cloud-sync trial.

## Privacy and operations

Backups and generated files use private permissions; .verify is owner-only. Source data are excluded from public fixtures, and private artifacts are ignored. No credentials, telemetry, unattended provider, automatic upload or persistent application logging were added. Backup retention is indefinite and manual; backup files do not include Word originals, conversations or standalone exported reports. Checksums detect corruption, not hostile tampering by someone able to replace the manifest.

## Remaining release gate

The author should use the release candidate over several normal writing days and confirm reliable saves, useful scholarly answers, revision comparison and a recovery copy. Actual login startup is optional and remains untested in the user's session. This stage cannot truthfully claim elapsed multi-day acceptance during a short automated run. No known failure remained in the executed test suite; the limitations in LIMITATIONS_AND_ROADMAP.md remain explicit.

The next step is ordinary author use and feedback, followed by explicit v1.0 sign-off when satisfied. There is no further numbered implementation phase in the original plan.

Installed walkthrough confirmed backup-check, restore-to-new-folder, setup --codex in a path containing spaces, preservation of existing instructions, and startup generation with installed=false. Both environments pass pip check. A pre-existing user watcher was observed and left running; no new persistent watcher/service was started by these checks. Restart an existing watcher after upgrading so its running process loads the new code. Final source check still reports 17 current and byte-unchanged manuscripts.
