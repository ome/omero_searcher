#!/bin/bash

# Abort on error
set -e

echo "OMERO.searcher installation script"

usage() {
    echo "USAGE: `basename $0` OMERO_PREFIX [--nodeps] [--noconf] [--omero5]"
    echo "  OMERO_PREFIX: The root directory of the OMERO server installation"
    echo "  --nodeps: Don't install requirements"
    echo "  --noconf: Don't attempt to automatically configure any OMERO.web app settings"
    echo "  --omero5: Attempt to automatically configure OMERO.searcher for OMERO5"
    exit $1
}

check_py_mod() {
    set +e
    python -c "import $1"
    if [ $? -ne 0 ]; then
        echo "$2"
        if [ $3 -gt 0 ]; then
            exit $3
        fi
    fi
    set -e
}

NODEPS=0
NOCONF=0
OMERO_VERSION=4
OMERO_SERVER=

while [ $# -gt 0 ]; do
    arg="$1"
    shift

    case "$arg" in
        "-h")
            usage 0
            ;;

        "--nodeps")
            NODEPS=1
            ;;

        "--noconf")
            NOCONF=1
            ;;

        "--omero5")
            OMERO_VERSION=5
            ;;

        *)
            if [ -n "$OMERO_SERVER" ]; then
                echo "Unexpected arguments"
                usage 1
            fi
            OMERO_SERVER="$arg"
            ;;
    esac
done

if [ -z "$OMERO_SERVER" ]; then
    usage 1
fi

if [ ! -d "$OMERO_SERVER" ]; then
    echo "Invalid server directory: $OMERO_SERVER"
    usage 2
fi


SCRIPT_DEST="$OMERO_SERVER/lib/scripts/searcher"
WEB_DEST="$OMERO_SERVER/lib/python/omeroweb/omero_searcher"
CONFIG="$WEB_DEST/omero_searcher_config.py"

if [ $NODEPS -eq 1 ]; then
    echo "Skipping dependencies"
else
    echo "Checking for PIL, numpy and scipy"
    check_py_mod PIL "ERROR: Please install PIL" 1
    check_py_mod numpy "ERROR: Please install numpy" 1
    check_py_mod scipy "ERROR: Please install scipy" 1
    check_py_mod tables \
"WARNING: Pytables appears to be missing. If OMERO.tables is running
on a different server this doesn't matter, otherwise please check
OMERO.tables is running." 0

    echo "Installing python dependencies"
    pip install -r requirements.txt
fi

if [ -e "$CONFIG" ]; then
    echo "Saving old configuration"
    OLD_CONFIG=`mktemp -t omero_searcher_config.XXXXXX`
    cat "$CONFIG" >> "$OLD_CONFIG"
fi

if [ -e "$SCRIPT_DEST" -o -e "$WEB_DEST" ]; then
cat <<EOF

***** WARNING *****
Deleting $SCRIPT_DEST
and $WEB_DEST
in 5s, hit Ctrl-C to abort
EOF
    sleep 5
    rm -rf "$SCRIPT_DEST" "$WEB_DEST"
fi

echo "Installing scripts"
mkdir "$SCRIPT_DEST"
cp -a scripts/* "$SCRIPT_DEST"

echo "Installing web-app"
mkdir "$WEB_DEST"
cp -a *.py templates templatetags "$WEB_DEST"

if [ -n "$OLD_CONFIG" ]; then
    echo "Restoring previous configuration"
    mv "$OLD_CONFIG" "$CONFIG"
fi

if [ $NOCONF -eq 1 ]; then
    echo "Skipping OMERO.searcher web configuration"
else
    echo "Configuring OMERO web-apps"
    OMERO="$OMERO_SERVER/bin/omero"

    # Disable exit on failure so that we can print out a more informative
    # message
    set +e
    CONFIG_KEY=`"$OMERO" config get omero.web.apps`
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to run $OMERO config"
        exit 2
    fi

    CONFIG_RIGHT=`"$OMERO" config get omero.web.ui.right_plugins`
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to run $OMERO config"
        exit 2
    fi

    if [ $OMERO_VERSION -eq 4 -a -z "$CONFIG_KEY" ]; then
        "$OMERO" config set omero.web.apps '["omero_searcher"]'
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to run $OMERO config"
            exit 2
        fi

    elif [ $OMERO_VERSION -eq 5 -a -z "$CONFIG_KEY" -a -z "$CONFIG_RIGHT" ];
    then
        "$OMERO" config set omero.web.apps '["omero_searcher"]'
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to run $OMERO config"
            exit 2
        fi

        TABacquisition='["Acquisition", "webclient/data/includes/right_plugin.acquisition.js.html", "metadata_tab"]'
        TABpreview='["Preview", "webclient/data/includes/right_plugin.preview.js.html", "preview_tab"]'
        TABsearcher='["Searcher", "searcher/plugin_config/right_search_form.js.html", "right_search_form"]'
        "$OMERO" config set omero.web.ui.right_plugins \
            "[$TABacquisition, $TABpreview, $TABsearcher]"
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to run $OMERO config"
            exit 2
        fi
    else
        # TODO: Automatically append omero_searcher to the omero.web.apps
        # config key (requires parsing the existing value of omero.web.apps
        # if any)
cat <<EOF

***** WARNING *****
OMERO web-apps configuration failed.
The omero.web.apps or omero.web.ui.right_plugins configuration keys are
non-empty. See INSTALL.md for help.
EOF
    fi
fi

if [ -z "$OLD_CONFIG" ]; then
cat <<EOF
If this is a new installation you must create the OMERO.searcher data
directory, see $CONFIG

EOF
fi
