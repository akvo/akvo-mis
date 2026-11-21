#!/usr/bin/env bash
#
# Reproduce the "photo file missing" state on a pending submission, so the
# Retake photo / From Gallery repair path can be tested by hand.
#
# Local dev tool. Excluded from git via .git/info/exclude — do not commit.
#
# Requires: a rootable device (google_apis emulator image, not google_apis_playstore).
#
# Usage:
#   ./repro-missing-photo.sh              list pending submissions and their files
#   ./repro-missing-photo.sh break        break 1 photo on the newest pending submission
#   ./repro-missing-photo.sh break 3      break 3 photos across pending submissions
#   ./repro-missing-photo.sh break all    break every photo on pending submissions
#   ./repro-missing-photo.sh restore      put every backed-up file back
#
# Env:
#   PKG=com.akvo.dws_datapro ./repro-missing-photo.sh     target a standalone build
#                                                          (default: Expo Go)

set -euo pipefail

PKG="${PKG:-host.exp.exponent}"
DB="/data/data/${PKG}/files/SQLite/app.db"
BACKUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.repro-backup"

die() {
  printf '\033[31merror:\033[0m %s\n' "$1" >&2
  exit 1
}
info() { printf '\033[36m%s\033[0m\n' "$1"; }

command -v adb >/dev/null || die "adb not on PATH"
[ -n "$(adb devices | sed '1d' | grep -w device || true)" ] || die "no device attached"

# Album/gallery work and file deletion both need root. Play Store images refuse.
adb root >/dev/null 2>&1 || true
adb wait-for-device
adb shell "[ -r '${DB}' ]" >/dev/null 2>&1 ||
  die "cannot read ${DB}. Rootable image required (adb root must succeed), and the app must have run at least once."

# Every file:// answer belonging to an unsynced, submitted datapoint.
# Emitted as: <datapointId>|<uri>
pending_files() {
  adb shell "sqlite3 '${DB}' \"SELECT id || '|' || json FROM datapoints WHERE syncedAt IS NULL;\"" 2>/dev/null |
    tr -d '\r' |
    while IFS='|' read -r id rest; do
      [ -n "${id:-}" ] || continue
      printf '%s\n' "$rest" | grep -oE 'file://[^"]+' | while read -r uri; do
        printf '%s|%s\n' "$id" "$uri"
      done
    done
}

# adb shell test, tolerating paths with spaces
remote_exists() { adb shell "[ -f \"$1\" ] && echo yes || echo no" 2>/dev/null | tr -d '\r'; }

cmd_list() {
  info "Pending (unsynced) submissions on ${PKG}:"
  adb shell "sqlite3 '${DB}' \"SELECT id || '  ' || name FROM datapoints WHERE syncedAt IS NULL;\"" 2>/dev/null | tr -d '\r' | sed 's/^/  /'
  echo
  info "Files referenced by those submissions:"
  local any=0
  while IFS='|' read -r id uri; do
    [ -n "${id:-}" ] || continue
    any=1
    if [ "$(remote_exists "${uri#file://}")" = "yes" ]; then
      printf '  \033[32m present\033[0m  [%s] %s\n' "$id" "$(basename "$uri")"
    else
      printf '  \033[31m MISSING\033[0m  [%s] %s\n' "$id" "$(basename "$uri")"
    fi
  done < <(pending_files)
  [ "$any" = 1 ] || echo "  (none — create a submission with a photo and leave it unsynced)"
}

cmd_break() {
  local want="${1:-1}" broken=0
  mkdir -p "$BACKUP_DIR"
  while IFS='|' read -r id uri; do
    [ -n "${id:-}" ] || continue
    [ "$want" = all ] || [ "$broken" -lt "$want" ] || break
    local path="${uri#file://}"
    [ "$(remote_exists "$path")" = "yes" ] || continue
    # Back up first so restore is possible — this is a repro tool, not a shredder
    adb pull "$path" "${BACKUP_DIR}/$(basename "$path")" >/dev/null 2>&1 ||
      die "could not back up $path"
    printf '%s\n' "$path" >> "${BACKUP_DIR}/manifest.txt"
    adb shell "rm -f \"$path\""
    printf '  \033[31mbroke\033[0m  [%s] %s\n' "$id" "$(basename "$path")"
    broken=$((broken + 1))
  done < <(pending_files)

  if [ "$broken" = 0 ]; then
    die "nothing to break — no pending submission has an existing photo file"
  fi
  echo
  info "Broke ${broken} file(s). Backups in ${BACKUP_DIR}"
  echo "Open the submission in the app: it should show the missing-file notice"
  echo "with Retake photo and From Gallery. Run '$0 restore' to undo."
}

cmd_restore() {
  local manifest="${BACKUP_DIR}/manifest.txt"
  [ -f "$manifest" ] || die "no backups to restore (${manifest} not found)"
  local restored=0
  while read -r path; do
    [ -n "${path:-}" ] || continue
    local file="${BACKUP_DIR}/$(basename "$path")"
    [ -f "$file" ] || continue
    adb push "$file" "$path" >/dev/null 2>&1 || continue
    # adb push writes as root with 0666. Match the owning app instead, or the
    # restored file looks nothing like one the app wrote.
    local owner
    owner="$(adb shell "stat -c %U:%G \"$(dirname "$path")\"" 2>/dev/null | tr -d '\r')"
    [ -n "$owner" ] && adb shell "chown $owner \"$path\"" >/dev/null 2>&1 || true
    adb shell "chmod 600 \"$path\"" >/dev/null 2>&1 || true
    printf '  \033[32mrestored\033[0m  %s\n' "$(basename "$path")"
    restored=$((restored + 1))
  done < "$manifest"
  rm -f "$manifest"
  info "Restored ${restored} file(s)."
}

case "${1:-list}" in
  list)    cmd_list ;;
  break)   cmd_break "${2:-1}" ;;
  restore) cmd_restore ;;
  *)       die "unknown command '$1' (expected: list | break [N|all] | restore)" ;;
esac
