#!/bin/bash

# Abort on error
set -e

echo "OMERO.searcher installation script"

usage() {
    echo "USAGE: $(basename $0) OMERO_PREFIX [--nodeps] [--conf5|--conf4|--noconf]"
    echo "  OMERO_PREFIX: The root directory of the OMERO server installation"
    echo "  --nodeps: Don't install requirements"
    echo "  --conf5: Attempt to automatically configure for OMERO-5 (default)"
    echo "  --conf4: Attempt to automatically configure for OMERO-4.4"
    echo "  --noconf: Don't attempt to automatically configure any OMERO.web app settings"
    exit $1
}

check_py_mod() {
    python -c "import $1" || {
        echo "$2"
        if [ $3 -gt 0 ]; then
            exit $3
        fi
    }
}

NODEPS=0
CONF=5
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

        "--conf5")
            CONF=5
            ;;

        "--conf4")
            CONF=4
            ;;

        "--noconf")
            CONF=0
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
    OLD_CONFIG=$(mktemp -t omero_searcher_config.XXXXXX)
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


OMERO="$OMERO_SERVER/bin/omero"
TABsearcher='["Searcher", "searcher/plugin_config/right_search_form.js.html", "right_search_form"]'
WEBsearcher='"omero_searcher"'

CONFIGweb=omero.web.apps
CONFIGtab=omero.web.ui.right_plugins

if [ $CONF -eq 0 ]; then
    echo "Skipping OMERO.searcher web configuration"
fi

if [ $CONF -eq 5 ]; then
    echo "Configuring OMERO web-apps"

    "$OMERO" config remove "$CONFIGweb" "$WEBsearcher" || true
    "$OMERO" config append "$CONFIGweb" "$WEBsearcher" || {
        echo "ERROR: Failed to configure $CONFIGweb"
        exit 2
    }

    "$OMERO" config remove "$CONFIGtab" "$TABsearcher" || true
    "$OMERO" config append "$CONFIGtab" "$TABsearcher" || {
        echo "ERROR: Failed to configure $CONFIGtab"
        exit 2
    }
fi

if [ $CONF -eq 4 ]; then
    echo "Configuring OMERO web-apps"

    CONFIG_KEY=$("$OMERO" config get "$CONFIGweb") || {
        echo "ERROR: Failed to get $CONFIGweb"
        exit 2
    }

    CONFIG_RIGHT=$("$OMERO" config get "$CONFIGtab") || {
        echo "ERROR: Failed to get $CONFIGtab"
        exit 2
    }

    if [ -z "$CONFIG_KEY" -a -z "$CONFIG_RIGHT" ];
    then
        "$OMERO" config set "$CONFIGweb" '["omero_searcher"]' || {
            echo "ERROR: Failed to configure $CONFIGweb"
            exit 2
        }

        TABacquisition='["Acquisition", "webclient/data/includes/right_plugin.acquisition.js.html", "metadata_tab"]'
        TABpreview='["Preview", "webclient/data/includes/right_plugin.preview.js.html", "preview_tab"]'
        "$OMERO" config set omero.web.ui.right_plugins \
            "[$TABacquisition, $TABpreview, $TABsearcher]" || {
            echo "ERROR: Failed to configure $CONFIGtab"
            exit 2
        }
    else
        # TODO: Automatically append omero_searcher to the omero.web.apps
        # config key (requires parsing the existing value of omero.web.apps
        # if any)
cat <<EOF

***** WARNING *****
OMERO web-apps auto-configuration failed.
The $CONFIGweb or $CONFIGtab configuration keys are non-empty.
See INSTALL.md for help on manual configuration.
EOF
    fi
fi

if [ -z "$OLD_CONFIG" ]; then
cat <<EOF
If this is a new installation you must create the OMERO.searcher data
directory, see $CONFIG

EOF
fi
