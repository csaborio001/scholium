# Installation, maintenance and recovery

This is the technical companion to the [academic user guide](USER_GUIDE.md). Authors can ask Codex to carry out these operations rather than learning the commands.

## Install or upgrade on this Mac

```sh
cd /Users/csaborio/code/scholium
./scripts/install.sh
```

Requires Python 3.12+ (the script uses python3.12 when creating a new environment) and network access for installation. It installs inside this project, preserves existing book configurations and does not modify shell profiles or start services. For other Python 3.12+ installations, create .venv with that interpreter before running the script. Installed manuscript operations work without network access. If needed, add this line once to ~/.zshrc and open a new terminal:

```sh
export PATH="/Users/csaborio/code/scholium/.venv/bin:$PATH"
```

After upgrading, stop an already running foreground watcher with Ctrl-C and run `scholium watch` again from the same book workspace so it loads the new version.

The current release candidate is 0.7.0. It is not a signed-off v1.0 release. Full command details: [CLI.md](CLI.md). Older installation/extraction detail: [INSTALLATION_REFERENCE.md](INSTALLATION_REFERENCE.md).

## Configure a book and connect Codex

In the book workspace you intend to open in VS Code:

```sh
scholium setup . --codex
```

This creates scholium.toml if missing and a book-specific AGENTS.md if missing. Neither is overwritten. Edit manuscript.source_dirs in the configuration to select your Word folder; keep storage.data_dir separate. Codex instructions contain the installed executable and absolute configuration path, so the application source folder need not be open. Start a new Codex conversation in this book workspace. If AGENTS.md already exists, setup reports that it was kept: merge the new manuscript instructions rather than replacing unrelated rules. Paths in a copied instruction file must be updated if you move the executable or book configuration.

Your existing book can be connected without changing its configuration:

```sh
scholium setup /Users/csaborio/code/scholium-tests --codex
```

Use `scholium doctor` to check configuration and `scholium ingest --all` to index. Use `--config /absolute/path/to/scholium.toml` before commands when working elsewhere. Setup does not automatically edit the source paths, read manuscripts, or ingest them. Permissions may need to be granted through the Codex client for the folders named by the configuration.

## Back up saved work

```sh
scholium backup
```

The command returns a new backup directory inside the configured data directory's backups folder. Or choose a new destination:

```sh
scholium backup --output /absolute/path/to/NEW-backup
scholium backup-check /absolute/path/to/NEW-backup
```

A backup includes index.sqlite3, analysis.sqlite3 if present, and the book configuration, plus a checksum manifest. SQLite snapshot APIs are used; application writers are excluded while the snapshot is taken, and database write reservations guard the existing databases. Reads can continue. If another writer/backup is active, wait or stop the watcher and retry. Restarts resume ordinary ingestion; the lock file itself may remain after exit and must not be deleted while in use.

Verification checks file sizes/hashes, supported database identity/schema, SQLite integrity and foreign keys, and analysis dependency revisions/hashes against the backed-up index. Checksums detect corruption, not malicious replacement by somebody able to rewrite the manifest. Treat backups as private and trusted local artifacts.

Backups do **not** contain Word originals, standalone extraction directories, private reports outside the databases, Codex chat history or the application environment. Keep independent Word backups. Retain backups on another protected device/service if required; this app does not upload them. No backup or revision pruning is automatic.

Files are created 0600 and backup directories 0700. A crash may leave an `.incomplete` marker; such a backup is rejected. Handled failures remove the newly created partial destination. Existing outputs are never overwritten. Unknown schemas and symlinks for backup files are rejected.

## Recover without overwriting the working copy

Stop any watcher before deciding to switch the active data directory. First verify and restore to a new, separate directory:

```sh
scholium backup-check /absolute/path/to/BACKUP
scholium restore /absolute/path/to/BACKUP --output /absolute/path/to/NEW-recovered-data
```

Recovery can run even if the active index is corrupt. It validates the backup before copying and validates the recovered files again. The current database and configuration are left unchanged. It rejects destinations in manuscript source folders, within the active data directory, or overlapping the backup.

To activate after reviewing the result, edit **the existing book's scholium.toml** and set storage.data_dir to the absolute recovered path. Then run:

```sh
scholium status
scholium analysis list
```

The scholium.toml copied into the backup/recovered directory is a historical reference, not the configuration to activate: relative paths were meaningful beside its original location. Keep using the existing book configuration and explicitly change its data_dir. Historical analyses may be outdated if Word sources have since changed; run ingest and reread affected analyses as appropriate. Preserve the old data folder until satisfied with recovery.

If no good backup exists, point the existing configuration at a new empty data directory and run ingest --all. This rebuilds current evidence from Word files but cannot reconstruct lost revisions, saved analyses or review decisions. Preserve the damaged files for diagnosis; never lower schema numbers by hand.

## Upgrades and schema compatibility

Index schema 1 is backed up automatically before migration to schema 2 on a writable operation. Read-only commands do not migrate. Analysis schema remains 1. backup-check accepts supported index schemas 1–2, but rejects unknown versions. An older restored index migrates when next ingested/watched; its original backup remains unchanged. Test evidence covers migration rollback and preservation of prior revisions.

## Watching and optional login startup on macOS

The ordinary option is foreground watching:

```sh
scholium watch
```

Keep the terminal open and stop with Ctrl-C. A second watcher for the same book is rejected. `--poll` uses periodic reconciliation if native events are unavailable. Source hashes are checked periodically even with native observation.

An optional login-start file can be generated, but is **not installed or loaded automatically**:

```sh
scholium startup --output /absolute/path/to/NEW-scholium.plist
```

The generated LaunchAgent starts watch with the exact executable/configuration paths. It runs at login when installed, does not restart repeatedly after errors, and discards stdout/stderr rather than accumulating manuscript or operational logs. For diagnostics use foreground watch. Executable/configuration moves require generating a new file. The generated file is tested structurally; actual login behavior must be checked in the user's macOS session.

Only if you explicitly choose login startup, copy the generated file into ~/Library/LaunchAgents using a unique filename, then load that exact file with `launchctl bootstrap gui/$(id -u) /absolute/path/to/installed.plist`. This starts it immediately as well as at later logins. Stop/unload with `launchctl bootout gui/$(id -u) /absolute/path/to/installed.plist`, then remove only that installed file to disable future login starts. Do not run a foreground watcher for the same book at the same time. These are user-session operations, not system-wide services; no service has been enabled by development or tests.

## Logs and privacy

Scholium creates no persistent log files by default. Watch streams operational metadata to the terminal; normal search/report output contains private text. If you redirect output, keep it in a protected private directory and choose your own deletion schedule. Do not include manuscript passages in support reports or public issue trackers. The optional startup file discards output, so there is no unbounded service-log retention.

Keep configuration, databases, backups, Word files, reports and exports out of source control, including in book workspaces outside this project's ignore rules. Generated AGENTS.md contains local paths; avoid publishing those if sensitive. No API credentials, unattended model calls, telemetry or automatic remote uploads are configured.

## Final acceptance trial

Use the application for several ordinary writing days: save in Word, ask evidence-based questions, compare a revision, review a saved analysis, and verify one backup/recovery copy. Report missed updates, misleading citations or recovery problems. Automated and accelerated editing tests do not replace this multi-day author trial. Version 1.0 requires the author's explicit sign-off after that trial.
