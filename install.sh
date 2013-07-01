#!/bin/sh
#
# Install OMERO.searcher, retaining the previous configuration file if found
#

# Abort on error
set -e

if [ $# -ne 1 ]; then
    echo "USAGE: `basename $0` /path/to/omero/server/"
    exit 2
fi

OMERO_SERVER="$1"
SCRIPT_DEST="$OMERO_SERVER/lib/scripts/searcher"
WEB_DEST="$OMERO_SERVER/lib/python/omeroweb/omero_searcher"
CONFIG="$WEB_DEST/omero_searcher_config.py"

if [ -e "$CONFIG" ]; then
    OLD_CONFIG=`mktemp -t omero_searcher_config`
    cat "$CONFIG" >> "$OLD_CONFIG"
fi

if [ -e "$SCRIPT_DEST" -o -e "$WEB_DEST" ]; then
    echo "Deleting $SCRIPT_DEST and/or $WEB_DEST in 5s, hit Ctrl-C to abort"
    sleep 5
    rm -rf "$SCRIPT_DEST" "$WEB_DEST"
fi

mkdir "$SCRIPT_DEST"
cp -a scripts/* "$SCRIPT_DEST"

mkdir "$WEB_DEST"
cp -a *.py templates "$WEB_DEST"

if [ -n "$OLD_CONFIG" ]; then
    echo "Copying previous configuration"
    mv "$OLD_CONFIG" "$CONFIG"
fi

OMERO="$OMERO_SERVER/bin/omero"
CONFIG_KEY=`"$OMERO" config get omero.web.apps`
if [ -z "$CONFIG_KEY" ]; then
    "$OMERO" config set omero.web.apps "[\"omero_searcher\"]"
else
    # TODO: Automatically append omero_searcher to the omero.web.apps config key
    # (requires parsing the existing value of omero.web.apps if any)
    echo "omero.web.apps configuration key is non-empty."
    echo "Please enable OMERO.searcher manually by running :"
    echo "    omero config set omero.web.apps '[..., \"omero_searcher\"]'"
fi

