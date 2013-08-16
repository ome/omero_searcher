#!/bin/bash
# Installation script for use with openmicroscopy/docs/install/VM/omerovm.sh
#
# export OMERO_POST_INSTALL_SCRIPTS=setup_omero_searcher.sh
# bash omverovm.sh

set -e -u -x

PASSWORD=${PASSWORD:-"omero"}
SEARCHER_JOB=${SEARCHER_JOB:-"ANALYSIS-OMERO-SEARCHER-merge"}
OMERO_PATH="/home/omero/OMERO.server"
OMERO_BIN=$OMERO_PATH/bin
OMERO_BUILD_URL="http://hudson.openmicroscopy.org.uk/job/$SEARCHER_JOB/lastSuccessfulBuild"
PYSLID_DATA_DIR="/home/omero/pyslid.data"

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

#echo $PASSWORD | sudo -S apt-get install -qy libfreeimage3 python-pip
# The version of pip on the VM image doesn't install recursive dependencies
# from pyslid setup.py
#echo $PASSWORD | sudo -S pip install mahotas==0.9.4
#echo $PASSWORD | sudo -S pip install milk==0.4.3
#echo $PASSWORD | sudo -S pip install pymorph==0.96
#echo $PASSWORD | sudo -S pip install pyslic==0.6.1
echo $PASSWORD | sudo -S apt-get install -qy libfreeimage3


# Need to wrap pip with sudo
# The version of pip is useless, and ignores git branch specifications, so
# disable parsing of the requirements file and install everything manually

#pushd pyslid
#git remote add update https://github.com/manics/pyslid.git
#git fetch update
#git checkout update/merge_all
#echo $PASSWORD | sudo -S pip install $PWD
#popd

#echo $PASSWORD | sudo -S pip install git+git://github.com/icaoberg/ricerca.git@master


sed -i.bak -e "s/^pip /echo $PASSWORD | sudo -S pip /" install.sh
#sed -i.bak -e "s/^pip /#pip /" install.sh
./install.sh $OMERO_PATH

mkdir -p "$PYSLID_DATA_DIR"
sed -i.bak -e \
    "s%^omero_contentdb_path = .*$%omero_contentdb_path = \\'$PYSLID_DATA_DIR\\'%" \
    "$OMERO_PATH/lib/python/omeroweb/omero_searcher/omero_searcher_config.py"

echo $PASSWORD | sudo -S /etc/init.d/omero restart
echo $PASSWORD | sudo -S /etc/init.d/omero-web restart

