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


def extractFeatures(conn, image, scale, ftset, scaleSet,
                    channels, zselect, tselect):
    """
    Calculate features for one image, link to the image, save to the ContentDB.
    @param scaleSet a read write parameter, calculated scales should be
    appended to this set so that a single removeDuplicates call can be made at
    the end.
    """
    message = ''

    imageId = image.getId()

    # TODO: should be configurable (or process all c/z/t)
    # TODO: provide user option to only calculate if not already present
    # (pyslid.feature.has)
    pixels = 0
    if channels[0] < 1 or channels[0] > image.getSizeC():
        return message + 'Channel %d not found in Image id:%d\n' % (
            channels[0], imageId)
    if ftset == 'slf33':
        channels = (channels[0] - 1,)
    if ftset == 'slf34':
        if channels[1] < 1 or channels[1] > image.getSizeC():
            m = 'Channel %d not found in Image id:%d' % (channels[1], imageId)
            sys.stderr.write(m)
            return message + m + '\n'
        channels = (channels[0], channels[1])

    if zselect[0] == 'Middle':
        zslice = image.getSizeZ() / 2
    elif zselect[0] == 'Select Index':
        if zselect[1] < 1 or zselect[1] > image.getSizeZ():
            m = 'Z-slice %d not found in Image id:%d' % (zselect[1], imageId)
            sys.stderr.write(m)
            return message + m + '\n'
        zslice = zselect[1] - 1
    else:
        raise Exception('Unexpected zselect')

    if tselect[0] == 'Middle':
        timepoint = image.getSizeT() / 2
    elif tselect[0] == 'Select Index':
        if tselect[1] < 1 or tselect[1] > image.getSizeT():
            m = 'Timepoint %d not found in Image id:%d' % (tselect[1], imageId)
            sys.stderr.write(m)
            return message + m + '\n'
        timepoint = tselect[1] - 1
    else:
        raise Exception('Unexpected tselect')

    message += 'Calculating features ftset:%s scale:%e c:%s z:%d t:%d\n' % (
        ftset, scale, channels, zslice, timepoint)
    [fids, features, scalec] = pyslid.features.calculate(
        conn, imageId, scale, ftset, True, None,
        pixels, channels, zslice, timepoint, debug=True)

    if features is None:
      return message + 'Failed Image id:%d\n' % imageId

    # Create an individual OMERO.table for this image
    #print fids
    #print features
    answer = pyslid.features.link(conn, imageId, scale, fids, features, ftset)

    if answer:
        message += 'Extracted features from Image id:%d\n' % imageId
    else:
       return message + 'Failed to link features to Image id:%d\n' % imageId

    # Create the global contentDB
    # TODO: Implement this per-dataset level (already supported by PySLID)
    # TODO: Set server and usernames
    server = 'NA'
    username = 'NA'
    answer, m = pyslid.database.direct.update(
        conn, server, username, scale,
        imageId, pixels, channels[0], zslice, timepoint, fids, features, ftset)
    if answer:
        scaleSet.add(scale)
        return message
    return '%sFailed to update ContentDB with Image id:%d (%s)\n' (
        message, imageID, m)


def processImages(client, scriptParams):
    message = ''

    # for params with default values, we can get the value directly
    dataType = scriptParams['Data_Type']
    ids = scriptParams['IDs']
    ftset = scriptParams['Feature_set']
    scale = float(scriptParams['Scale'])

    channels = (scriptParams['Readout_Channel'],
                scriptParams['Reference_Channel'])

    zselect = (scriptParams['Z_Index'], scriptParams['Select_Z'])
    tselect = (scriptParams['Timepoint'], scriptParams['Select_T'])

    try:
        nimages = 0
        scaleSet = set()

        conn = omero.gateway.BlitzGateway(client_obj=client)

        # Get the objects
        objects, logMessage = script_utils.getObjects(conn, scriptParams)
        message += logMessage

        if not objects:
            return message

        # TODO: Consider wrapping each image calculation with a trry-catch
        # so that we can attempt to continue on error?

        if dataType == 'Image':
            for image in objects:
                message += 'Processing image id:%d\n' % image.getId()
                msg = extractFeatures(
                    conn, image, scale, ftset, scaleSet,
                    channels, zselect, tselect)
                message += msg + '\n'

        else:
            if dataType == 'Project':
                datasets = [proj.listChildren() for proj in objects]
                datasets = itertools.chain.from_iterable(datasets)
            else:
                datasets = objects

            for d in datasets:
                message += 'Processing dataset id:%d\n' % d.getId()
                for image in d.listChildren():
                    message += 'Processing image id:%d\n' % image.getId()
                    msg = extractFeatures(
                        conn, image, scale, ftset, scaleSet,
                        channels, zselect, tselect)
                    message += msg + '\n'

        # Finally tidy up by removing duplicates
        for s in scaleSet:
            message += 'Removing duplicates from scale:%g\n' % s
            a, msg = pyslid.database.direct.removeDuplicates(
                conn, s, ftset, did=None)
            if not a:
                message += 'Failed: '
            message += msg + '\n'


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

        scripts.Long(
            'Readout_Channel', optional=False, grouping='2',
            description='slf33/slf34 readout channel, starting from 1',
            default=1),

        scripts.Long(
            'Reference_Channel', optional=False, grouping='2',
            description='slf34 reference channel (ignored for slf33), starting from 1',
            default=2),


        scripts.String('Z_Index', optional=False, grouping='3',
                       description='Which Z-slice to use',
                       values=[rstring('Middle'), rstring('Select Index')],
                       default='Middle'),

        scripts.Long(
            'Select_Z', optional=False, grouping='3',
            description='Select Z index if not middle (starting from 1)',
            default=-1),


        scripts.String('Timepoint', optional=False, grouping='4',
                       description='Which timepoint to use',
                       values=[rstring('Middle'), rstring('Select Index')],
                       default='Middle'),

        scripts.Long(
            'Select_T', optional=False, grouping='4',
            description='Select timepoint if not middle (starting from 1)',
            default=-1),


        scripts.String(
            'Scale', optional=False, grouping='5',
            description='Scale',
            default=rstring('1.0')),


        version = '0.0.1',
        authors = ['Ivan E. Cao-Berg', 'Lane Center for Comp Bio'],
        institutions = ['Carnegie Mellon University'],
        contact = 'icaoberg@cmu.edu',
    )

    try:
        startTime = datetime.now()
        session = client.getSession()
        client.enableKeepAlive(60)
        scriptParams = {}

        # process the list of args above.
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)
        message = str(scriptParams) + '\n'

        # Run the script
        message += processImages(client, scriptParams) + '\n'

        stopTime = datetime.now()
        message += 'Duration: %s' % str(stopTime - startTime)

        print message
        client.setOutput('Message', rstring(message))

    finally:
        client.closeSession()

if __name__ == '__main__':
    runScript()

