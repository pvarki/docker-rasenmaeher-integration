#!/bin/bash
CRL_FILE=/ca_public/crl.pem
echo "Waiting for "$CRL_FILE
while inotifywait -e modify,move,create,delete "$CRL_FILE"; do
    echo "CRL file changed. Reloading Nginx..."
    pkill -HUP nginx
done
