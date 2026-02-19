#!/usr/bin/env bash
# shellcheck disable=SC2155
set -euo pipefail

# Usage:
#   wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | bash -
#   wget -q -O - https://raw.githubusercontent.com/stephen-kim/ha-navien-smart/latest/install.sh | ARCHIVE_TAG=v0.1.2 bash -

DOMAIN="${DOMAIN:-navien_smart}"
REPO_PATH="${REPO_PATH:-stephen-kim/ha-navien-smart}"
ARCHIVE_TAG="${ARCHIVE_TAG:-${1:-latest}}"
HUB_DOMAIN="${HUB_DOMAIN:-github.com}"
ARCHIVE_URL="https://${HUB_DOMAIN}/${REPO_PATH}/archive/${ARCHIVE_TAG}.zip"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}INFO:${NC} $1"; }
warn() { echo -e "${YELLOW}WARN:${NC} $1"; }
error() { echo -e "${RED}ERROR:${NC} $1"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || error "'$1' is required but not installed."
}

download() {
  local url="$1"
  local out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$out" "$url"
  else
    error "Neither 'curl' nor 'wget' is installed."
  fi
}

find_ha_config_dir() {
  local -a paths=(
    "$PWD"
    "$PWD/config"
    "/config"
    "$HOME/.homeassistant"
    "/usr/share/hassio/homeassistant"
  )

  for path in "${paths[@]}"; do
    if [ -f "$path/configuration.yaml" ] && [ -d "$path/.storage" ]; then
      echo "$path"
      return
    fi
    if [ -f "$path/home-assistant.log" ]; then
      echo "$path"
      return
    fi
  done
}

main() {
  require_cmd unzip

  local ha_dir
  ha_dir="$(find_ha_config_dir || true)"
  [ -n "${ha_dir:-}" ] || error "Home Assistant config directory not found."

  info "Home Assistant config directory: $ha_dir"
  info "Archive URL: $ARCHIVE_URL"

  local cc_dir="$ha_dir/custom_components"
  mkdir -p "$cc_dir"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' EXIT

  local zip_file="$tmp_dir/${ARCHIVE_TAG}.zip"
  info "Downloading package..."
  download "$ARCHIVE_URL" "$zip_file"

  info "Unpacking package..."
  unzip -q "$zip_file" -d "$tmp_dir"

  local src_dir
  src_dir="$(find "$tmp_dir" -type d -path "*/custom_components/${DOMAIN}" | head -n 1 || true)"
  [ -n "${src_dir:-}" ] || error "Could not find custom_components/${DOMAIN} in archive."

  if [ -d "$cc_dir/$DOMAIN" ]; then
    warn "Existing custom_components/${DOMAIN} found. Replacing..."
    rm -rf "$cc_dir/$DOMAIN"
  fi

  cp -R "$src_dir" "$cc_dir/$DOMAIN"
  info "Installation complete: $cc_dir/$DOMAIN"
  info "Restart Home Assistant before configuring the integration."
}

main "$@"
