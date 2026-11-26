#!/bin/sh
# MQTT certificates and accounts for the broker in compose.yaml. Needs openssl and docker.
#
#   ./mqtt.sh certs <hostname>   private CA (kept) and a broker certificate for <hostname>
#   ./mqtt.sh backend-user       the listener account, password taken from .env
#   ./mqtt.sh user <device_uid>  one account per device; asks for the password
#                                (or reads MQTT_PASSWORD, for scripts)
#   ./mqtt.sh remove <username>
#
# After adding an account:                 docker compose kill -s HUP mosquitto
# After removing one or renewing the certificate:  docker compose restart mosquitto
# (a restart also drops sessions that are already open).
set -eu
cd "$(dirname "$0")"

IMAGE=eclipse-mosquitto:2.0
CA_DIR=secrets/mqtt-ca      # the CA key stays here and is never mounted into a service
BROKER_DIR=secrets/mqtt     # what the broker reads

die() { echo "mqtt.sh: $*" >&2; exit 1; }

# Run a shell command as root in a throwaway container with the broker files at /s.
in_broker_dir() {
    mkdir -p "$BROKER_DIR"
    docker run --rm -v "$PWD/$BROKER_DIR:/s" "$@"
}

# The broker (uid 1883) alone reads the key and passwords; certificates stay public.
OWN='chown -R 1883:1883 /s && chmod 755 /s && for f in /s/*; do
    case "$f" in *.crt) chmod 644 "$f" ;; *) chmod 600 "$f" ;; esac; done'

certs() {
    host=$1
    case "$host" in *[!A-Za-z0-9.-]*|'') die "hostname may hold letters, digits, dots and hyphens" ;; esac
    mkdir -p "$CA_DIR"
    chmod 700 "$CA_DIR"
    if [ ! -f "$CA_DIR/ca.key" ]; then
        openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=AEGIS MQTT CA" \
            -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
            -keyout "$CA_DIR/ca.key" -out "$CA_DIR/ca.crt"
        chmod 600 "$CA_DIR/ca.key"
    fi
    openssl req -newkey rsa:2048 -nodes -subj "/CN=$host" \
        -keyout "$CA_DIR/server.key" -out "$CA_DIR/server.csr"
    printf 'subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n' \
        "$host" > "$CA_DIR/server.ext"
    openssl x509 -req -in "$CA_DIR/server.csr" -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" \
        -CAcreateserial -days 825 -extfile "$CA_DIR/server.ext" -out "$CA_DIR/server.crt"
    in_broker_dir -v "$PWD/$CA_DIR:/ca:ro" "$IMAGE" sh -c \
        "cp /ca/ca.crt /ca/server.crt /ca/server.key /s/ && $OWN"
    rm -f "$CA_DIR/server.key" "$CA_DIR/server.csr" "$CA_DIR/server.ext"
    echo "Broker certificate for $host is ready. Give devices $BROKER_DIR/ca.crt."
}

check_name() {
    case "$1" in
        *[!A-Za-z0-9._:-]*|'') die "a username is a device_uid: letters, digits, . _ : -" ;;
    esac
    [ "${#1}" -le 100 ] || die "a device_uid has at most 100 characters"
}

set_password() {
    name=$1
    if [ -n "${MQTT_PASSWORD:-}" ]; then
        export MQTT_PASSWORD
        in_broker_dir -e MQTT_PASSWORD "$IMAGE" sh -c \
            "touch /s/passwords && mosquitto_passwd -b /s/passwords '$name' \"\$MQTT_PASSWORD\" && $OWN"
    else
        in_broker_dir -it "$IMAGE" sh -c "touch /s/passwords && mosquitto_passwd /s/passwords '$name' && $OWN"
    fi
}

case "${1:-}" in
    certs)
        [ $# -eq 2 ] || die "usage: mqtt.sh certs <hostname>"
        certs "$2" ;;
    backend-user)
        [ -f .env ] || die "create deploy/.env first"
        MQTT_PASSWORD=$(sed -n 's/^AEGIS_MQTT_BACKEND_PASSWORD=//p' .env | tr -d '\r')
        [ -n "$MQTT_PASSWORD" ] || die "set AEGIS_MQTT_BACKEND_PASSWORD in deploy/.env"
        set_password aegis-backend ;;
    user)
        [ $# -eq 2 ] || die "usage: mqtt.sh user <device_uid>"
        check_name "$2"
        [ "$2" != aegis-backend ] || die "that name belongs to the backend (use backend-user)"
        set_password "$2" ;;
    remove)
        [ $# -eq 2 ] || die "usage: mqtt.sh remove <username>"
        check_name "$2"
        in_broker_dir "$IMAGE" sh -c "mosquitto_passwd -D /s/passwords '$2' && $OWN" ;;
    *)
        die "usage: mqtt.sh certs <hostname> | backend-user | user <device_uid> | remove <username>" ;;
esac
