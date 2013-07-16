#!/bin/sh

# Abort on error
set -e

cat <<EOF
OMERO.searcher installation script
==================================

Installs OMERO.searcher, retains the previous configuration file if
found.

This script will attempt to install several Python dependencies. It
is highly recommended that you first create and activate a Python
virtualenv.

The Python mahotas module requires the freeimage library to be
installed in advance. On CentOS this is available from the EPEL
repository:
    yum install freeimage
On Mac OS X it can be installed using homebrew:
    brew install freeimage

EOF

usage() {
    echo "USAGE: `basename $0` OMERO_PREFIX"
    echo "  OMERO_PREFIX: The root directory of the OMERO server installation"
    exit $1
}

if [ $# -eq 0 -o "$1" = "-h" ]; then
    usage 0
fi

if [ $# -ne 1 ]; then
    echo "Unexpected arguments"
    usage 2
fi

if [ ! -d "$1" ]; then
    echo "Invalid server directory: $1"
    usage 2
fi


OMERO_SERVER="$1"
SCRIPT_DEST="$OMERO_SERVER/lib/scripts/searcher"
WEB_DEST="$OMERO_SERVER/lib/python/omeroweb/omero_searcher"
CONFIG="$WEB_DEST/omero_searcher_config.py"

echo "Installing python dependencies"
pip install -r requirements.txt

if [ -e "$CONFIG" ]; then
    echo "Saving old configuration"
    OLD_CONFIG=`mktemp -t omero_searcher_config.XXXXXX`
    cat "$CONFIG" >> "$OLD_CONFIG"
fi

if [ -e "$SCRIPT_DEST" -o -e "$WEB_DEST" ]; then
    echo
    echo "***** WARNING *****"
    echo "Deleting $SCRIPT_DEST and/or $WEB_DEST in 5s, hit Ctrl-C to abort"
    sleep 5
    rm -rf "$SCRIPT_DEST" "$WEB_DEST"
fi

echo "Installing scripts"
mkdir "$SCRIPT_DEST"
cp -a scripts/* "$SCRIPT_DEST"

echo "Installing web-app"
mkdir "$WEB_DEST"
cp -a *.py templates "$WEB_DEST"

if [ -n "$OLD_CONFIG" ]; then
    echo "Restoring previous configuration"
    mv "$OLD_CONFIG" "$CONFIG"
fi

echo "Configuring OMERO web-apps"
OMERO="$OMERO_SERVER/bin/omero"

# Disable exit on failure so that we can print out a more informative message
set +e
CONFIG_KEY=`"$OMERO" config get omero.web.apps`
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to run $OMERO config"
    exit 2
fi

if [ -z "$CONFIG_KEY" ]; then
    "$OMERO" config set omero.web.apps "[\"omero_searcher\"]"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to run $OMERO config"
        exit 2
    fi
else
    # TODO: Automatically append omero_searcher to the omero.web.apps config key
    # (requires parsing the existing value of omero.web.apps if any)
cat <<EOF

***** WARNING *****
OMERO web-apps configuration failed.
The omero.web.apps configuration key is non-empty. Please enable
OMERO.searcher manually by running something like:
    omero config set omero.web.apps '[..., \"omero_searcher\"]'"

EOF
fi

if [ -z "$OLD_CONFIG" ]; then
cat <<EOF
If this is a new installation you must create the OMERO.searcher data
directory, see $CONFIG

EOF
fi
