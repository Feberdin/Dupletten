#!/usr/bin/env bash
# Zweck:
#   Findet doppelte Film- und Serien-Dateien in Radarr-/Sonarr-Bibliotheken,
#   zeigt die Gruppen an und fragt interaktiv, ob ausgewaehlte Kopien geloescht
#   werden sollen.
# Input/Output:
#   Input sind ein oder mehrere --movies-root/--series-root Verzeichnisse.
#   Output ist eine menschenlesbare Liste mit Duplikat-Gruppen, Prompts fuer
#   Loeschentscheidungen und eine Abschluss-Zusammenfassung.
# Wichtige Invarianten:
#   - Ohne ausdrueckliche Auswahl wird nichts geloescht.
#   - Es werden nur bekannte Video-Dateien betrachtet.
#   - Leere Ordner werden nur bis zum angegebenen Root entfernt, nie darueber.
# Debugging:
#   Mit --debug oder LOG_LEVEL=debug starten. Dann werden Root-Pruefungen,
#   erzeugte Duplikat-Keys und Skip-Gruende geloggt.

set -u

SCRIPT_DIR="$(CDPATH= cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(CDPATH= cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
# Die Kernlogik lebt in einer separaten Datei, damit Tests die Funktionen direkt
# laden koennen und das CLI fokussiert auf Parsing und Interaktion bleibt.
# shellcheck source=../lib/media_duplicates.sh
. "$PROJECT_ROOT/lib/media_duplicates.sh"

usage() {
  cat <<'EOF'
Verwendung:
  ./bin/media_duplicates.sh --movies-root "/pfad/zu/Filmen"
  ./bin/media_duplicates.sh --series-root "/pfad/zu/Serien"
  ./bin/media_duplicates.sh --movies-root "/movies" --series-root "/series" --list-only

Optionen:
  --movies-root PATH   Film-Root, kann mehrfach verwendet werden
  --series-root PATH   Serien-Root, kann mehrfach verwendet werden
  --list-only          Nur anzeigen, nie nach dem Loeschen fragen
  --debug              Ausfuehrliches Logging aktivieren
  --help               Diese Hilfe anzeigen

Beispiele:
  ./bin/media_duplicates.sh --movies-root "/data/media/Filme"
  ./bin/media_duplicates.sh --series-root "/data/media/Serien" --debug
EOF
}

MOVIE_ROOTS=()
SERIES_ROOTS=()
LIST_ONLY=0
TMP_DIR=''
SUMMARY_GROUPS=0
SUMMARY_DELETED_FILES=0
SUMMARY_DELETED_BYTES=0
QUIT_REQUESTED=0
PARSED_SELECTIONS=''

cleanup() {
  if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
    rm -rf "$TMP_DIR"
  fi
}

trap cleanup EXIT INT TERM

add_root() {
  local kind="$1"
  local input_path="$2"
  local resolved_path

  if [ ! -d "$input_path" ]; then
    die "Verzeichnis nicht gefunden: $input_path" || exit 1
  fi

  if [ ! -r "$input_path" ]; then
    die "Verzeichnis nicht lesbar: $input_path" || exit 1
  fi

  resolved_path="$(canonicalize_directory "$input_path")" || {
    die "Verzeichnis konnte nicht aufgeloest werden: $input_path" || exit 1
  }

  log_debug "Registriere $kind-Root: $resolved_path"

  case "$kind" in
    movie)
      MOVIE_ROOTS+=("$resolved_path")
      ;;
    series)
      SERIES_ROOTS+=("$resolved_path")
      ;;
  esac
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --movies-root)
        [ "$#" -ge 2 ] || {
          die "Fehlender Pfad nach --movies-root" || exit 1
        }
        add_root movie "$2"
        shift 2
        ;;
      --series-root)
        [ "$#" -ge 2 ] || {
          die "Fehlender Pfad nach --series-root" || exit 1
        }
        add_root series "$2"
        shift 2
        ;;
      --list-only)
        LIST_ONLY=1
        shift
        ;;
      --debug)
        set_media_duplicates_log_level debug
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        die "Unbekannte Option: $1" || exit 1
        ;;
    esac
  done

  if [ "${#MOVIE_ROOTS[@]}" -eq 0 ] && [ "${#SERIES_ROOTS[@]}" -eq 0 ]; then
    die "Mindestens ein --movies-root oder --series-root ist erforderlich." || exit 1
  fi
}

write_record() {
  local media_type="$1"
  local root="$2"
  local file_path="$3"
  local duplicate_key size resolution

  if ! is_video_file "$file_path"; then
    log_debug "Ueberspringe Nicht-Video-Datei: $file_path"
    return 0
  fi

  if contains_unsafe_path_characters "$file_path"; then
    log_warn "Pfad wegen Tab/Newline uebersprungen: $file_path"
    return 0
  fi

  if [ ! -r "$file_path" ]; then
    log_warn "Datei nicht lesbar, uebersprungen: $file_path"
    return 0
  fi

  size="$(file_size_bytes "$file_path")" || {
    log_warn "Dateigroesse konnte nicht gelesen werden: $file_path"
    return 0
  }

  resolution="$(resolution_from_name "$(basename_path "$file_path")")"

  case "$media_type" in
    movie)
      duplicate_key="$(movie_duplicate_key "$file_path")"
      ;;
    series)
      duplicate_key="$(series_duplicate_key "$file_path")"
      ;;
    *)
      log_warn "Unbekannter Medientyp fuer Datei: $file_path"
      return 0
      ;;
  esac

  log_debug "Key [$media_type]: $duplicate_key <- $file_path"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$duplicate_key" "$media_type" "$size" "$resolution" "$root" "$file_path" >> "$RECORDS_FILE"
}

scan_root() {
  local media_type="$1"
  local root="$2"

  log_info "Scanne $media_type-Root: $root"
  while IFS= read -r -d '' file_path; do
    write_record "$media_type" "$root" "$file_path"
  done < <(find "$root" -type f -print0)
}

print_group_lines() {
  local item_count="$1"
  local idx zero_based size resolution path marker

  for ((idx = 1; idx <= item_count; idx++)); do
    zero_based=$((idx - 1))
    size="$(human_size "${GROUP_SIZES[$zero_based]}")"
    resolution="${GROUP_RESOLUTIONS[$zero_based]}"
    path="${GROUP_PATHS[$zero_based]}"
    marker=''
    if [ "$idx" -eq 1 ]; then
      marker=' (Empfehlung: behalten, groesste Datei)'
    fi
    printf '  [%d] %s | %s | %s%s\n' "$idx" "$size" "$resolution" "$path" "$marker"
  done
}

parse_selection() {
  local raw_input="$1"
  local max_index="$2"
  local normalized_input token
  PARSED_SELECTIONS=''

  normalized_input="$(printf '%s' "$raw_input" | tr ',' ' ')"
  for token in $normalized_input; do
    case "$token" in
      [0-9]*)
        if [ "$token" -lt 1 ] || [ "$token" -gt "$max_index" ]; then
          return 1
        fi
        case " $PARSED_SELECTIONS " in
          *" $token "*) ;;
          *)
            PARSED_SELECTIONS="${PARSED_SELECTIONS}${PARSED_SELECTIONS:+ }${token}"
            ;;
        esac
        ;;
      *)
        return 1
        ;;
    esac
  done

  [ -n "$PARSED_SELECTIONS" ]
}

selected_count() {
  local count=0 token
  for token in $1; do
    count=$((count + 1))
  done
  printf '%s\n' "$count"
}

delete_selected_items() {
  local token array_index file_path root_path file_size

  for token in $PARSED_SELECTIONS; do
    array_index=$((token - 1))
    file_path="${GROUP_PATHS[$array_index]}"
    root_path="${GROUP_ROOTS[$array_index]}"
    file_size="${GROUP_SIZES[$array_index]}"

    if rm -f -- "$file_path"; then
      SUMMARY_DELETED_FILES=$((SUMMARY_DELETED_FILES + 1))
      SUMMARY_DELETED_BYTES=$((SUMMARY_DELETED_BYTES + file_size))
      log_info "Datei geloescht: $file_path"
      remove_empty_parent_directories "$file_path" "$root_path"
    else
      log_error "Datei konnte nicht geloescht werden: $file_path"
    fi
  done
}

prompt_for_group_action() {
  local item_count="$1"
  local count_selected confirmation

  while true; do
    printf 'Loeschen? Nummern eingeben (z. B. 2 oder 2,3), Enter = behalten, q = abbrechen: '
    IFS= read -r answer <&3 || {
      QUIT_REQUESTED=1
      return 0
    }

    case "$answer" in
      '')
        return 0
        ;;
      q|Q|quit|QUIT)
        QUIT_REQUESTED=1
        return 0
        ;;
    esac

    if ! parse_selection "$answer" "$item_count"; then
      printf 'Ungueltige Eingabe. Bitte nur vorhandene Nummern eingeben.\n'
      continue
    fi

    count_selected="$(selected_count "$PARSED_SELECTIONS")"
    if [ "$count_selected" -eq "$item_count" ]; then
      printf 'Du hast alle Dateien dieser Gruppe markiert. Zum Schutz bitte DELETE-ALL tippen: '
      IFS= read -r confirmation <&3 || {
        QUIT_REQUESTED=1
        return 0
      }
      if [ "$confirmation" != 'DELETE-ALL' ]; then
        printf 'Abgebrochen, es wurde nichts geloescht.\n'
        return 0
      fi
    fi

    delete_selected_items
    return 0
  done
}

render_and_handle_group() {
  local key="$1"
  local item_count="$2"

  SUMMARY_GROUPS=$((SUMMARY_GROUPS + 1))
  printf '\n%s\n' "$(pretty_duplicate_key "$key")"
  print_group_lines "$item_count"

  if [ "$LIST_ONLY" -eq 1 ]; then
    printf '  Aktion: Nur Anzeige (--list-only), keine Datei geloescht.\n'
    return 0
  fi

  prompt_for_group_action "$item_count"
}

read_group_file() {
  local line_type first second third fourth fifth
  local current_key='' current_count=0
  GROUP_SIZES=()
  GROUP_RESOLUTIONS=()
  GROUP_ROOTS=()
  GROUP_PATHS=()

  while IFS=$'\t' read -r line_type first second third fourth fifth; do
    case "$line_type" in
      GROUP)
        current_key="$first"
        current_count="$third"
        GROUP_SIZES=()
        GROUP_RESOLUTIONS=()
        GROUP_ROOTS=()
        GROUP_PATHS=()
        ;;
      ITEM)
        GROUP_SIZES+=("$second")
        GROUP_RESOLUTIONS+=("$third")
        GROUP_ROOTS+=("$fourth")
        GROUP_PATHS+=("$fifth")
        ;;
      END)
        render_and_handle_group "$current_key" "$current_count"
        if [ "$QUIT_REQUESTED" -eq 1 ]; then
          return 0
        fi
        ;;
    esac
  done < "$GROUPS_FILE"
}

print_summary() {
  printf '\nZusammenfassung:\n'
  printf '  Gefundene Duplikat-Gruppen: %d\n' "$SUMMARY_GROUPS"
  printf '  Geloeschte Dateien: %d\n' "$SUMMARY_DELETED_FILES"
  printf '  Freigegebener Speicher: %s\n' "$(human_size "$SUMMARY_DELETED_BYTES")"
  if [ "$QUIT_REQUESTED" -eq 1 ]; then
    printf '  Lauf wurde vorzeitig vom Benutzer beendet.\n'
  fi
}

main() {
  parse_args "$@"
  exec 3<&0

  TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/media-duplicates.XXXXXX")" || {
    die 'Temporres Arbeitsverzeichnis konnte nicht erstellt werden.' || exit 1
  }
  RECORDS_FILE="$TMP_DIR/records.tsv"
  SORTED_FILE="$TMP_DIR/sorted.tsv"
  GROUPS_FILE="$TMP_DIR/groups.tsv"
  : > "$RECORDS_FILE"

  for root in "${MOVIE_ROOTS[@]}"; do
    scan_root movie "$root"
  done

  for root in "${SERIES_ROOTS[@]}"; do
    scan_root series "$root"
  done

  if [ ! -s "$RECORDS_FILE" ]; then
    printf 'Keine passenden Video-Dateien gefunden.\n'
    return 0
  fi

  LC_ALL=C sort -t "$(printf '\t')" -k1,1 -k3,3nr "$RECORDS_FILE" > "$SORTED_FILE"
  group_records_to_file "$SORTED_FILE" "$GROUPS_FILE"

  if [ ! -s "$GROUPS_FILE" ]; then
    printf 'Keine Duplikate gefunden.\n'
    return 0
  fi

  read_group_file
  print_summary
}

main "$@"
