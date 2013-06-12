from omero import scripts
from omero.util import script_utils
import omero.model
from omero.rtypes import rstring, rlong
from datetime import datetime
import itertools
import sys

import pyslid
from omeroweb.omero_searcher.omero_searcher_config import omero_contentdb_path
pyslid.database.direct.set_contentdb_path(omero_contentdb_path)


# 0 or 1 based indexing in the UI?
IDX_OFFSET = 0



def listExistingCZTS(conn, imageId, ftset):
    """
    List the available CZT and scales for features associated with an image
    feature table.
    Returns a list of tuples (C, Z, T, scale)
    """
    try:
        ftnames, ftvalues = pyslid.features.get(
            conn, 'vector', imageId, set=ftset)
        return [r[1:5] for r in ftvalues]
    except pyslid.utilities.PyslidException:
        return []


def extractFeaturesOneChannel(conn, image, scale, ftset, scaleSet,
                              channels, zslice, timepoint,
                              disableCdb):
    """
    Calculate features for one image, link to the image, save to the ContentDB.
    @param scaleSet a read write parameter, calculated scales should be
    appended to this set so that a single removeDuplicates call can be made at
    the end.
    """
    message = ''
    imageId = image.getId()
    pixels = 0

    mid = 'image:%d c:%s z:%d t:%d' % (imageId, channels, zslice, timepoint)

    print 'Calculating features ftset:%s scale:%e %s' % (ftset, scale, mid)
    [fids, features, scalec] = pyslid.features.calculate(
        conn, imageId, scale, ftset, True, None,
        pixels, channels, zslice, timepoint, debug=True)

    if features is None:
        m = 'Feature calculation failed for %s\n' % mid
        sys.stderr.write(m)
        return message + m

    # Create an individual OMERO.table for this image
    #print fids
    #print features
    answer = pyslid.features.link(
        conn, imageId, scale, fids, features, ftset, field=True, rid=None,
        pixels=0, channel=channels[0], zslice=zslice, timepoint=timepoint)

    if answer:
        print 'Extracted features from %s' % mid
    else:
        m = 'Failed to link features to %s\n' % mid
        sys.stderr.write(m)
        return message + m

    if disableCdb:
        print 'ContentDB update disabled'
        return message

    # Create the global contentDB
    # TODO: Implement this per-dataset level (already supported by PySLID)
    # TODO: Set servername, change update parameter from username to userid
    server = 'NA'
    # Username can change, UserId should be constant
    username = image.getOwner().getId()
    try:
        answer, um = pyslid.database.direct.update(
            conn, server, username, scale,
            imageId, pixels, channels[0], zslice, timepoint,
            fids, features, ftset)
        if answer:
            scaleSet.add(scale)
            return message

    except omero.SecurityViolation as e:
        # Ignore e.serverStackTrace in client message
        um = '%s %s' % (e.serverExceptionClass, e.message)

    m = 'Failed to update ContentDB with %s : %s\n' % (mid, um)
    sys.stderr.write(m)
    return message + m


def extractFeatures(conn, image, scale, ftset, scaleSet,
                    channels, zselect, tselect, recalc, disableCdb):
    """
    Extract features for the requested channel(s)
    """

    message = ''
    imageId = image.getId()

    if recalc:
        existing = []
    else:
        existing = listExistingCZTS(conn, imageId, ftset)

    if zselect[0]:
        zslice = image.getSizeZ() / 2
    else:
        if (zselect[1] < IDX_OFFSET or
            zselect[1] >= image.getSizeZ() + IDX_OFFSET):
            m = 'Z-slice %d not found in Image id:%d\n' % (zselect[1], imageId)
            sys.stderr.write(m)
            return message + m
        zslice = zselect[1] - IDX_OFFSET

    if tselect[0]:
        timepoint = image.getSizeT() / 2
    else:
        if (tselect[1] < IDX_OFFSET or
            tselect[1] >= image.getSizeT() + IDX_OFFSET):
            m = 'Timepoint %d not found in Image id:%d\n' % (
                tselect[1], imageId)
            sys.stderr.write(m)
            return message + m
        timepoint = tselect[1] - IDX_OFFSET

    allChannels = channels[0]

    if allChannels:
        readoutCh = range(image.getSizeC())
    else:
        if (channels[1] < IDX_OFFSET or
            channels[1] >= image.getSizeC() + IDX_OFFSET):
            m = 'Channel %d not found in Image id:%d\n' % (channels[1], imageId)
            sys.stderr.write(m)
            return message + m
        readoutCh = [channels[1] - IDX_OFFSET]

    if ftset == 'slf33':
        otherChs = []
    if ftset == 'slf34':
        if (channels[2] < IDX_OFFSET or
            channels[2] >= image.getSizeC() + IDX_OFFSET):
            m = 'Channel %d not found in Image id:%d\n' % (channels[2], imageId)
            sys.stderr.write(m)
            return message + m
        otherChs = [channels[2] - IDX_OFFSET]

    for c in readoutCh:
        chs = [c] + otherChs

        if (c, zslice, timepoint, scale) in existing:
            print 'Features already present for %d %d.%d.%d (%e)' % (
                imageId, c, zslice, timepoint, scale)
        else:
            message += extractFeaturesOneChannel(
                conn, image, scale, ftset, scaleSet, chs, zslice, timepoint,
                disableCdb)

    return message


def processImages(client, scriptParams):
    message = ''

    # for params with default values, we can get the value directly
    dataType = scriptParams['Data_Type']
    ids = scriptParams['IDs']
    ftset = scriptParams['Feature_set']

    channels = (scriptParams['Readout_All_Channels'],
                scriptParams['Select_Readout_Channel'],
                scriptParams['Select_Reference_Channel'])

    zselect = (scriptParams['Use_Middle_Z'], scriptParams['Select_Z'])
    tselect = (scriptParams['Use_Middle_T'], scriptParams['Select_T'])

    if scriptParams['Enable_Advanced_Options']:
        recalc = scriptParams['Recalculate_Existing_Features']
        scale = float(scriptParams['Scale'])
        disableCdb = scriptParams['Disable_ContentDB_Update']
    else:
        recalc = True
        scale = 1.0
        disableCdb = False

    try:
        nimages = 0
        scaleSet = set()

        conn = omero.gateway.BlitzGateway(client_obj=client)

        # Get the objects
        objects, logMessage = script_utils.getObjects(conn, scriptParams)
        print logMessage

        if not objects:
            message += logMessage
            return message

        # TODO: Consider wrapping each image calculation with a trry-catch
        # so that we can attempt to continue on error?

        if dataType == 'Image':
            for image in objects:
                print 'Processing image id:%d' % image.getId()
                msg = extractFeatures(
                    conn, image, scale, ftset, scaleSet,
                    channels, zselect, tselect, recalc, disableCdb)
                message += msg + '\n'

        else:
            if dataType == 'Project':
                datasets = [proj.listChildren() for proj in objects]
                datasets = itertools.chain.from_iterable(datasets)
            else:
                datasets = objects

            for d in datasets:
                print 'Processing dataset id:%d' % d.getId()
                for image in d.listChildren():
                    print 'Processing image id:%d' % image.getId()
                    msg = extractFeatures(
                        conn, image, scale, ftset, scaleSet,
                        channels, zselect, tselect, recalc, disableCdb)
                    message += msg + '\n'

        # Finally tidy up by removing duplicates
        for s in scaleSet:
            print 'Removing duplicates from scale:%g' % s
            a, msg = pyslid.database.direct.removeDuplicates(
                conn, s, ftset, did=None)
            print msg
            if not a:
                m = 'Failed to remove duplicates scale:%g\n %s' % (s, msg)
                sys.stderr.write(m)
                message += m


    except:
        print message
        raise

    return message

def runScript():
    """
    The main entry point of the script, as called by the client via the scripting service, passing the required parameters. 
    """

    client = scripts.client(
        'OMERO.searcher Feature Calculation',
        'Calculate and link features',


        scripts.String('Data_Type', optional=False, grouping='1',
                       description='The data you want to work with.',
                       values=[rstring('Project'), rstring('Dataset'), rstring('Image')],
                       default='Dataset'),

        scripts.List(
            'IDs', optional=False, grouping='1',
            description='List of Dataset, Project or Image IDs').ofType(rlong(0)),


        scripts.String('Feature_set', optional=False, grouping='2',
                       description='SLF set',
                       values=[rstring('slf33'), rstring('slf34')],
                       default='slf33'),

        scripts.Bool('Readout_All_Channels', optional=False, grouping='3',
                     description='Which readout channel(s) to use',
                     default=True),

        scripts.Long(
            'Select_Readout_Channel', optional=False, grouping='3.1',
            description=('slf33/slf34 readout channel (starting from %d)' %
                         IDX_OFFSET),
            default=IDX_OFFSET),

        scripts.Long(
            'Select_Reference_Channel', optional=False, grouping='4',
            description=('slf34 reference channel (ignored for slf33), starting from %d' %
                         IDX_OFFSET),
            default=IDX_OFFSET + 1),


        scripts.Bool('Use_Middle_Z', optional=False, grouping='5',
                       description='Which Z-slice to use',
                       default=True),

        scripts.Long(
            'Select_Z', optional=False, grouping='5.1',
            description='Select Z index (starting from %d)' % IDX_OFFSET,
            default=-1),


        scripts.Bool('Use_Middle_T', optional=False, grouping='6',
                     description='Which timepoint to use',
                     default=True),

        scripts.Long(
            'Select_T', optional=False, grouping='6.1',
            description='Select timepoint (starting from %d)' % IDX_OFFSET,
            default=-1),


        scripts.Bool(
            'Enable_Advanced_Options', optional=False, grouping='7',
            description='Enable additional options for advanced users',
            default=False),

        scripts.Bool(
            'Recalculate_Existing_Features', optional=False, grouping='7.1',
            description='Recalculate features if already present',
            default=False),

        scripts.String(
            'Scale', optional=False, grouping='7.2',
            description='Scale',
            default=rstring('1.0')),

        scripts.Bool(
            'Disable_ContentDB_Update', optional=False, grouping='7.3',
            description=(
                'Do not update the main features ContentDB. '
                'This allows multiple feature calculation processes to run in '
                'parallel. '
                'You must run the Omero Searcher Rebuild ContentDB script '
                'yourself once all scripts have finished.'),
            default=False),


        version = '0.0.1',
        authors = ['Ivan E. Cao-Berg', 'Lane Center for Comp Bio'],
        institutions = ['Carnegie Mellon University'],
        contact = 'icaoberg@cmu.edu',
    )

    message = ''

    try:
        startTime = datetime.now()
        session = client.getSession()
        client.enableKeepAlive(60)
        scriptParams = {}

        # process the list of args above.
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)
        print '%s' % scriptParams

        # Run the script
        message += processImages(client, scriptParams) + '\n'
        print '\nMessage:\n%s\n' % message

        stopTime = datetime.now()
        print 'Duration: %s' % (stopTime - startTime)

        client.setOutput('Message', rstring(message))

    finally:
        client.closeSession()

if __name__ == '__main__':
    runScript()

