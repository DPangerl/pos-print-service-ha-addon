#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Read config from HA add-on options
BASE_URLS=$(bashio::config 'base_urls | join(",")')
POLL_INTERVAL=$(bashio::config 'poll_interval')
AUTH_TOKEN=$(bashio::config 'auth_token')
PRINTER_DEVICE=$(bashio::config 'printer_device')

export BASE_URLS
export POLL_INTERVAL
export AUTH_TOKEN
export PRINTER_DEVICE

bashio::log.info "Starting Thermal Print Service"
bashio::log.info "Polling URLs: ${BASE_URLS}"
bashio::log.info "Poll interval: ${POLL_INTERVAL}s"
bashio::log.info "Printer device: ${PRINTER_DEVICE}"

exec python3 /print-todos.py
