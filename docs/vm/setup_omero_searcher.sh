#!/bin/bash
# Installation script for use with openmicroscopy/docs/install/VM/omerovm.sh
#
# export OMERO_POST_INSTALL_SCRIPTS=setup_omero_searcher.sh
# bash omverovm.sh

set -e -u -x

# Note OMERO_PREFIX should be set by the caller, the set -e -u ensures
# the echo will fail if its not set
SEARCHER_JOB=${SEARCHER_JOB:-"ANALYSIS-OMERO-SEARCHER-merge"}
PYSLID_DATA_DIR=${PYSLID_DATA_DIR:-"/home/omero/pyslid.data"}

echo "OMERO_PREFIX=${OMERO_PREFIX}"
echo "SEARCHER_JOB=${SEARCHER_JOB}"
echo "PYSLID_DATA_DIR=${PYSLID_DATA_DIR}"

OMERO_BUILD_URL="http://hudson.openmicroscopy.org.uk/job/$SEARCHER_JOB/lastSuccessfulBuild"

readAPIValue() {
    URL=$1; shift
    wget -q -O- $URL | sed 's/^<.*>\([^<].*\)<.*>$/\1/'
}

echo "Grabbing last successful Hudson build of OMERO.searcher"
URL=`readAPIValue $OMERO_BUILD_URL"/api/xml?xpath=/freeStyleBuild/url"`
FILE=`readAPIValue $OMERO_BUILD_URL"/api/xml?xpath=//relativePath[contains(.,'searcher')]"`

wget -Nq "${URL}artifact/${FILE}"

DL_ARCHIVE=`basename $FILE`
DL_FOLDER=OMERO-searcher
unzip -o $DL_ARCHIVE
cd $DL_FOLDER

sudo apt-get install -qy libfreeimage3


# Need to wrap pip with sudo
sed -i.bak -e "s/^pip /sudo -S pip /" install.sh
./install.sh "$OMERO_PREFIX"

mkdir -p "$PYSLID_DATA_DIR"
sed -i.bak -e \
    "s%^omero_contentdb_path = .*$%omero_contentdb_path = \\'$PYSLID_DATA_DIR\\'%" \
    "$OMERO_PREFIX/lib/python/omeroweb/omero_searcher/omero_searcher_config.py"

sudo /etc/init.d/omero restart
sudo /etc/init.d/omero-web restart

