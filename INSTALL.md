OMERO.searcher installation
===========================

The easiest way to install OMERO.searcher on a clean OMERO.server (not
previously customised) is to check you have the required prerequisites,
run the supplied installation script, and configure OMERO.searcher.


Prerequisites
-------------

OMERO.searcher has several python dependencies. It is highly recommended
that you first create and activate a Python virtualenv which must contain
all the usual OMERO.server requirements.

In addition OMERO.searcher indirectly (via one of its Python dependencies)
requires the freeimage library to be installed in advance. On CentOS this
is available from the EPEL repository:

    yum install freeimage

On Debian it is available in the standard repositories:

    apt-get install libfreeimage3

On Mac OS X it can be installed using homebrew:

    brew install freeimage

Python prerequisites include the PIL, numpy and scipy Python modules.
Automatic installation of these modules sometimes fails, so it is
recommended that you install a distribution supplied version if available.
For example, on CentOS:

    yum install python-imaging numpy scipy

On Debian:

    apt-get install python-imaging python-numpy python-scipy

Alternatively install manually using pip:

    pip install PIL
    pip install numpy
    pip install scipy

Note OMERO.searcher requires OMERO.tables to be running. Although
OMERO.tables is included in OMERO.server it is automatically disabled if
Pytables is missing. See
http://www.openmicroscopy.org/site/support/omero5/sysadmins/unix/server-installation.html


Installation script
-------------------

The installation script will install OMERO.searcher, retaining the previous
configuration file if found. It will attempt to install several Python
dependencies. See below for manual installation instructions.

To install OMERO.searcher:

    ./install.sh /path/to/OMERO_SERVER

Run

    ./install.sh -h

for help on additional arguments.

If you have previously installed a web application the OMERO.web
configuration step will fail, see Configuration below for details on how to
manually enable OMERO.searcher in OMERO.web.


Manual installation
-------------------

Install Python dependencies by running

    pip install -r requirements.txt

Clone the OMERO.searcher repository into your OMERO.web directory

    cd $OMERO_SERVER/lib/python/omeroweb
    git clone https://github.com/openmicroscopy/omero_searcher.git

Move the feature calculation scripts into the scripts directory

    mv omero_searcher/scripts $OMERO_SERVER/lib/scripts/searcher


Configuration
-------------

After installing OMERO.searcher you must create a directory for storing
the feature databases. Edit the settings in

    $OMERO_SERVER/lib/python/omeroweb/omero_searcher/omero_searcher_config.py

and ensure the directory exists.

In addition OMERO.web must be configured to use the OMERO.searcher web-app.
If the automated configuration step failed during installation, or if you
wish to configure OMERO.searcher and OMERO.web manually, run something
along the lines of

    # OMERO 4.4
    omero config set omero.web.apps '[..., "omero_searcher"]'
    # OMERO 5
    omero config append omero.web.apps '"omero_searcher"'

You will also need to explicitly configure the right hand plugin pane:

    # OMERO 4.4
    omero config set omero.ui.right_plugins \
        '[[...], ["Searcher", "searcher/plugin_config/right_search_form.js.html", "right_search_form"]]'
    # OMERO 5
    omero config append omero.ui.right_plugins \
        '["Searcher", "searcher/plugin_config/right_search_form.js.html", "right_search_form"]'

For further details see

- http://www.openmicroscopy.org/site/support/omero5/developers/Web/CreateApp.html#add-your-app-to-omero-web
- http://www.openmicroscopy.org/site/support/omero5/developers/Web/WebclientPlugin.html#plugin-installation

You can now restart OMERO.web, remembering to first enter the virtualenv if
necessary.
