#!/bin/bash
# Installation script for use with openmicroscopy/docs/install/VM/omerovm.sh
#
# export OMERO_POST_INSTALL_SCRIPTS=setup_omero_searcher.sh
# bash omverovm.sh

set -e -u -x

# Note OMERO_PREFIX should be set by the caller, the set -e -u ensures
# the echo will fail if its not set
SEARCHER_JOB=${SEARCHER_JOB:-"ANALYSIS-OMERO-SEARCHER-merge"}
PYSLID_JOB=${PYSLID_JOB:-"ANALYSIS-OMERO-PYSLID-merge"}
RICERCA_JOB=${RICERCA_JOB:-"ANALYSIS-OMERO-RICERCA-merge"}
PYSLID_DATA_DIR=${PYSLID_DATA_DIR:-"/home/omero/pyslid.data"}

echo "OMERO_PREFIX=${OMERO_PREFIX}"
echo "SEARCHER_JOB=${SEARCHER_JOB}"
echo "PYSLID_DATA_DIR=${PYSLID_DATA_DIR}"

OMERO_BUILD_URL="http://hudson.openmicroscopy.org.uk/job/$SEARCHER_JOB/lastSuccessfulBuild"
RICERCA_BUILD_URL="http://hudson.openmicroscopy.org.uk/job/$RICERCA_JOB/lastSuccessfulBuild"
PYSLID_BUILD_URL="http://hudson.openmicroscopy.org.uk/job/$PYSLID_JOB/lastSuccessfulBuild"

readAPIValue() {
    URL=$1; shift
    wget -q -O- $URL | sed 's/^<.*>\([^<].*\)<.*>$/\1/'
}

echo "Grabbing last successful Hudson build of OMERO.searcher"
URL=`readAPIValue $OMERO_BUILD_URL"/api/xml?xpath=/freeStyleBuild/url"`
FILE=`readAPIValue $OMERO_BUILD_URL"/api/xml?xpath=//relativePath[contains(.,'OMERO-searcher')]"`

wget -Nq "${URL}artifact/${FILE}"

DL_ARCHIVE=`basename $FILE`
DL_FOLDER=OMERO-searcher
unzip -o $DL_ARCHIVE
cd $DL_FOLDER

if [ -f /usr/bin/apt-get ]; then
    # Debian
    sudo apt-get install -qy libfreeimage3
elif [ -f /usr/bin/yum ]; then
    # Redhat
    sudo yum -y install freeimage
else
    echo "Unknown" package manager
    exit 2
fi

URL=`readAPIValue $RICERCA_BUILD_URL"/api/xml?xpath=/freeStyleBuild/url"`
FILE=`readAPIValue $RICERCA_BUILD_URL"/api/xml?xpath=//relativePath[contains(.,'ricerca')]"`
sudo pip install "${URL}artifact/${FILE}"

URL=`readAPIValue $PYSLID_BUILD_URL"/api/xml?xpath=/freeStyleBuild/url"`
FILE=`readAPIValue $PYSLID_BUILD_URL"/api/xml?xpath=//relativePath[contains(.,'pyslid')]"`
sudo pip install "${URL}artifact/${FILE}"

# Disable dependencies since we've installed them above
./install.sh "$OMERO_PREFIX" --nodeps

mkdir -p "$PYSLID_DATA_DIR"
sed -i.bak -e \
    "s%^omero_contentdb_path = .*$%omero_contentdb_path = \\'$PYSLID_DATA_DIR\\'%" \
    "$OMERO_PREFIX/lib/python/omeroweb/omero_searcher/omero_searcher_config.py"

sudo service omero restart
sudo service omero-web restart

