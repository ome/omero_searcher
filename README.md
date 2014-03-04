OMERO.searcher
==============

OMERO.searcher provides content-based image search for
[OMERO](http://openmicroscopy.org/).

See [INSTALL.md](INSTALL.md) for prerequisites and installation instructions.


Basic instructions
------------------

1. Calculate features for images in a dataset, project, or screen by running
the `Feature Calculation` script using the default parameters.
2. Select one or more reference images, click the `Searcher` tab in the
right-hand pane, and search.
3. Search filters can be used to limit the search to a particular user,
dataset, project or screen.


Known issues
------------

This is beta quality software.

* Features calculated by OMERO.searcher are stored independently of the
OMERO repository.
* Features should be calculated by a group owner to avoid problems with
permissions.
* The OMERO.searcher web-app requires direct access to the features store.
* Multiple simultaneous feature calculation processes will conflict with
each other.
* If images are modified, moved or deleted then the feature Content
database will become desynchronized. If errors occur when performing a
search it may be necesssary to run the `Rebuild ContentDB` script.


Contact
-------

All feedback, good or bad, is always welcome:

* [Forum](https://www.openmicroscopy.org/community/)
* [Mailing lists](https://www.openmicroscopy.org/site/community/mailing-lists)
* [Github issues](https://github.com/openmicroscopy/omero_searcher/issues)
