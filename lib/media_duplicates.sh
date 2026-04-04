#!/usr/bin/env bash
# Zweck:
#   Hilfsfunktionen fuer das Duplikat-Tool fuer Radarr-/Sonarr-Medienbibliotheken.
# Input/Output:
#   Erwartet Dateipfade, Root-Verzeichnisse und Dateinamen; gibt normalisierte
#   Schluessel, Log-Ausgaben und aufbereitete Gruppen-Dateien zurueck.
# Wichtige Invarianten:
#   - Loeschen passiert nie in dieser Bibliothek, nur im aufrufenden CLI.
#   - Dateinamen mit Tab- oder Newline-Zeichen gelten als unsicher und sollen
#     vom CLI uebersprungen werden.
#   - Die Erkennung arbeitet bewusst heuristisch und gruppiert nur nach klaren
#     Film-/Serien-Merkmalen.
# Debugging:
#   LOG_LEVEL=debug oder --debug im CLI aktivieren. Dann werden erkannte Keys,
#   Skip-Gruende und Gruppierungsschritte geloggt.

# Logging existiert, damit man bei ungewoehnlichen Dateinamen nachvollziehen
# kann, warum ein Pfad als Duplikat erkannt oder uebersprungen wurde.
MEDIA_DUPLICATES_LOG_LEVEL="${MEDIA_DUPLICATES_LOG_LEVEL:-${LOG_LEVEL:-info}}"

set_media_duplicates_log_level() {
  MEDIA_DUPLICATES_LOG_LEVEL="$1"
}

log_level_number() {
  case "$1" in
    debug) printf '%s\n' 10 ;;
    info) printf '%s\n' 20 ;;
    warn) printf '%s\n' 30 ;;
    error) printf '%s\n' 40 ;;
    *) printf '%s\n' 20 ;;
  esac
}

should_log_level() {
  local wanted current
  wanted="$(log_level_number "$1")"
  current="$(log_level_number "$MEDIA_DUPLICATES_LOG_LEVEL")"
  [ "$wanted" -ge "$current" ]
}

log_message() {
  local level="$1"
  shift
  if should_log_level "$level"; then
    printf '[%s] %s\n' "$(printf '%s' "$level" | tr '[:lower:]' '[:upper:]')" "$*" >&2
  fi
}

log_debug() {
  log_message debug "$@"
}

log_info() {
  log_message info "$@"
}

log_warn() {
  log_message warn "$@"
}

log_error() {
  log_message error "$@"
}

die() {
  log_error "$@"
  return 1
}

# Diese Hilfen kapseln Plattform-Unterschiede zwischen macOS und Linux, damit
# das Tool auch in gemischten NAS-/Mac-Umgebungen laeuft.
canonicalize_directory() {
  (
    cd "$1" >/dev/null 2>&1 || exit 1
    pwd -P
  )
}

basename_path() {
  local path="$1"
  path="${path%/}"
  printf '%s\n' "${path##*/}"
}

file_basename_no_extension() {
  local name
  name="$(basename_path "$1")"
  printf '%s\n' "${name%.*}"
}

file_size_bytes() {
  if stat -f '%z' "$1" >/dev/null 2>&1; then
    stat -f '%z' "$1"
    return 0
  fi

  if stat -c '%s' "$1" >/dev/null 2>&1; then
    stat -c '%s' "$1"
    return 0
  fi

  wc -c < "$1" | tr -d '[:space:]'
}

human_size() {
  awk -v bytes="$1" '
    BEGIN {
      split("B KB MB GB TB PB", units, " ")
      size = bytes + 0
      unit = 1
      while (size >= 1024 && unit < 6) {
        size /= 1024
        unit++
      }
      if (unit == 1) {
        printf "%d %s", size, units[unit]
      } else {
        printf "%.1f %s", size, units[unit]
      }
    }
  '
}

contains_unsafe_path_characters() {
  case "$1" in
    *$'\t'*|*$'\n'*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_video_file() {
  local lower
  lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *.mkv|*.mp4|*.avi|*.mov|*.m4v|*.ts|*.m2ts|*.wmv|*.mpg|*.mpeg)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolution_from_name() {
  local lower
  lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *2160p*|*4k*|*uhd*)
      printf '%s\n' '2160p/4K'
      ;;
    *1080p*)
      printf '%s\n' '1080p'
      ;;
    *720p*)
      printf '%s\n' '720p'
      ;;
    *576p*|*480p*)
      printf '%s\n' 'SD'
      ;;
    *)
      printf '%s\n' 'unbekannt'
      ;;
  esac
}

# Wir normalisieren aggressiv, damit "Movie.Name.2024.1080p" und
# "Movie Name (2024)" denselben Kern-Schluessel bekommen.
normalize_text() {
  printf '%s' "$1" |
    tr '[:upper:]' '[:lower:]' |
    sed -E '
      s/\[[^][]*\]/ /g;
      s/\([^)]*\)/ /g;
      s/\{[^}]*\}/ /g;
      s/[._-]+/ /g;
      s/&/ and /g;
      s/[^[:alnum:] ]+/ /g;
      s/[[:space:]]+/ /g;
      s/^ //;
      s/ $//;
    '
}

is_release_token() {
  case "$1" in
    2160p|1080p|720p|576p|480p|360p|4k|uhd|bluray|blu-ray|brrip|bdrip|webrip|webdl|web|dl|hdrip|hdtv|x264|x265|h264|h265|hevc|av1|remux|proper|repack|extended|unrated|criterion|atmos|dts|aac|ac3|ddp|ddp5|ddp5.1|truehd|ma|dv|hdr10|sample)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Beispiel:
#   "Dune.Part.Two.2024.2160p" -> "dune part two|2024"
movie_parts_from_text() {
  local normalized title year token
  normalized="$(normalize_text "$1")"
  title=''
  year=''

  set -- $normalized
  for token in "$@"; do
    case "$token" in
      19[0-9][0-9]|20[0-9][0-9])
        year="$token"
        break
        ;;
      *)
        if is_release_token "$token"; then
          break
        fi
        title="${title}${title:+ }${token}"
        ;;
    esac
  done

  printf '%s|%s\n' "$title" "$year"
}

movie_duplicate_key() {
  local path base_name parent_name
  local base_parts parent_parts
  local base_title base_year parent_title parent_year
  local chosen_title chosen_year

  path="$1"
  base_name="$(file_basename_no_extension "$path")"
  parent_name="$(basename_path "$(dirname "$path")")"

  base_parts="$(movie_parts_from_text "$base_name")"
  parent_parts="$(movie_parts_from_text "$parent_name")"

  base_title="${base_parts%|*}"
  base_year="${base_parts#*|}"
  parent_title="${parent_parts%|*}"
  parent_year="${parent_parts#*|}"

  chosen_title="$base_title"
  chosen_year="$base_year"

  if [ -z "$chosen_title" ] || [ "$chosen_title" = 'movie' ] || [ "$chosen_title" = 'video' ]; then
    chosen_title="$parent_title"
  fi

  if [ -z "$chosen_year" ] && [ -n "$parent_year" ]; then
    chosen_year="$parent_year"
  fi

  if [ "${#parent_title}" -gt "${#chosen_title}" ] && [ -z "$base_year" ]; then
    chosen_title="$parent_title"
  fi

  if [ -z "$chosen_title" ]; then
    chosen_title="$(normalize_text "$base_name")"
  fi

  if [ -z "$chosen_title" ]; then
    chosen_title='unbekannter film'
  fi

  printf 'movie|%s|%s\n' "$chosen_title" "${chosen_year:-unknown}"
}

series_folder_name() {
  local path parent_name grandparent_name parent_normalized
  path="$1"
  parent_name="$(basename_path "$(dirname "$path")")"
  grandparent_name="$(basename_path "$(dirname "$(dirname "$path")")")"
  parent_normalized="$(normalize_text "$parent_name")"

  case "$parent_normalized" in
    season*|staffel*|specials|special*)
      if [ -n "$grandparent_name" ]; then
        printf '%s\n' "$grandparent_name"
        return 0
      fi
      ;;
  esac

  printf '%s\n' "$parent_name"
}

pad_episode_token() {
  printf '%s\n' "$1" | awk '
    {
      input = tolower($0)
      output = ""
      while (match(input, /[se][0-9]+/)) {
        prefix = substr(input, RSTART, 1)
        number = substr(input, RSTART + 1, RLENGTH - 1) + 0
        output = output sprintf("%s%02d", prefix, number)
        input = substr(input, RSTART + RLENGTH)
      }
      print output
    }
  '
}

# Beispiel:
#   "The.Office.S01E01.1080p" -> "s01e01"
#   "Show.1x02"               -> "s01e02"
extract_episode_id() {
  local lower token
  lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"

  token="$(printf '%s\n' "$lower" | sed -En 's/.*(s[0-9]{1,2}e[0-9]{1,2}(e[0-9]{1,2})*).*/\1/p')"
  if [ -n "$token" ]; then
    pad_episode_token "$token"
    return 0
  fi

  token="$(printf '%s\n' "$lower" | sed -En 's/.*([0-9]{1,2})x([0-9]{1,2}).*/\1 \2/p')"
  if [ -n "$token" ]; then
    set -- $token
    printf 's%02de%02d\n' "$1" "$2"
    return 0
  fi

  token="$(printf '%s\n' "$lower" | sed -En 's/.*((20[0-9]{2})[ ._-]([01][0-9])[ ._-]([0-3][0-9])).*/\2 \3 \4/p')"
  if [ -n "$token" ]; then
    set -- $token
    printf '%04d-%02d-%02d\n' "$1" "$2" "$3"
    return 0
  fi

  return 1
}

series_title_from_name() {
  local lower prefix
  lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  prefix="$(printf '%s\n' "$lower" |
    sed -E 's/[[:space:]]*(s[0-9]{1,2}e[0-9]{1,2}(e[0-9]{1,2})*|[0-9]{1,2}x[0-9]{1,2}|20[0-9]{2}[ ._-][01][0-9][ ._-][0-3][0-9]).*$//')"
  normalize_text "$prefix"
}

series_duplicate_key() {
  local path base_name folder_name episode_id title fallback_name
  path="$1"
  base_name="$(file_basename_no_extension "$path")"
  folder_name="$(series_folder_name "$path")"
  episode_id="$(extract_episode_id "$base_name" 2>/dev/null || true)"
  title="$(series_title_from_name "$base_name")"

  if [ -z "$title" ]; then
    title="$(normalize_text "$folder_name")"
  fi

  if [ -z "$title" ]; then
    title='unbekannte serie'
  fi

  if [ -n "$episode_id" ]; then
    printf 'series|%s|%s\n' "$title" "$episode_id"
    return 0
  fi

  fallback_name="$(normalize_text "$base_name")"
  if [ -z "$fallback_name" ]; then
    fallback_name='unbekannte datei'
  fi

  printf 'series|%s|file:%s\n' "$title" "$fallback_name"
}

pretty_duplicate_key() {
  local kind title identifier
  kind="${1%%|*}"
  title="${1#*|}"
  title="${title%|*}"
  identifier="${1##*|}"

  case "$kind" in
    movie)
      if [ "$identifier" = 'unknown' ]; then
        printf 'Film: %s\n' "$title"
      else
        printf 'Film: %s (%s)\n' "$title" "$identifier"
      fi
      ;;
    series)
      printf 'Serie: %s [%s]\n' "$title" "$identifier"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

# Gruppierung ueber awk haelt das CLI einfach und sorgt dafuer, dass interaktive
# Prompts nur echte Duplikat-Gruppen sehen.
group_records_to_file() {
  local input_file="$1"
  local output_file="$2"

  awk -F '\t' '
    function flush_group(    i) {
      if (count > 1) {
        print "GROUP\t" group_key "\t" group_type "\t" count
        for (i = 1; i <= count; i++) {
          print items[i]
        }
        print "END"
      }
      delete items
      count = 0
    }

    NF >= 6 {
      if (count == 0) {
        group_key = $1
        group_type = $2
      }

      if ($1 != group_key) {
        flush_group()
        group_key = $1
        group_type = $2
      }

      count++
      items[count] = "ITEM\t" count "\t" $3 "\t" $4 "\t" $5 "\t" $6
    }

    END {
      flush_group()
    }
  ' "$input_file" > "$output_file"
}

remove_empty_parent_directories() {
  local file_path="$1"
  local root_path="$2"
  local current_dir

  current_dir="$(dirname "$file_path")"
  while [ -n "$current_dir" ] && [ "$current_dir" != "$root_path" ] && [ "$current_dir" != '/' ]; do
    if rmdir "$current_dir" 2>/dev/null; then
      log_info "Leerer Ordner entfernt: $current_dir"
      current_dir="$(dirname "$current_dir")"
    else
      break
    fi
  done
}
