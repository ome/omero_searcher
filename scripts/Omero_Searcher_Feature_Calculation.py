from omero import scripts
from omero.util import script_utils
import omero.model
from omero.rtypes import rstring, rlong
from datetime import datetime
import itertools
#import sys, os
#os.environ['OMERO_CONTENTDB_PATH'] = os.path.join(
#    os.environ['HOME'], 'var', 'pyslid.data')
#sys.stderr.write(os.environ['OMERO_CONTENTDB_PATH'])
import pyslid


def extractFeatures(conn, image, scale, ftset):
    message = ''

    imageId = image.getId()

    # TODO: should be configurable (or process all c/z/t)
    # TODO: provide user option to only calculate if not already present
    # (pyslid.feature.has)
    pixels = 0
    channels = [0]
    zslice = 0
    timepoint = 0
    [fids, features, scale ] = pyslid.features.calculate(
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
    server = 'NA'
    username = 'NA'
    answer, m = pyslid.database.direct.update(
        conn, server, username, scale,
        imageId, pixels, channels[0], zslice, timepoint, fids, features, ftset)
    if answer:
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

    try:
        nimages = 0

        conn = omero.gateway.BlitzGateway(client_obj=client)

        # Get the objects
        objects, logMessage = script_utils.getObjects(conn, scriptParams)
        message += logMessage

        if not objects:
            return message

        if dataType == 'Image':
            for image in objects:
                message += 'Processing image id:%d\n' % image.getId()
                msg = extractFeatures(conn, image, scale, ftset)
                
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
                    msg = extractFeatures(conn, image, scale, ftset)
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

        scripts.String('Feature_set', optional=False, grouping='1',
                       description='SLF set',
                       values=[rstring('slf33'), rstring('slf34')],
                       default='slf33'),

        scripts.String(
            'Scale', optional=False, grouping='2',
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

