import omero
from omero import scripts
from omero.util import script_utils
from omero.rtypes import rstring, rlong
from datetime import datetime
import itertools
import sys

import pyslid
from omeroweb.omero_searcher.omero_searcher_config import omero_contentdb_path
pyslid.database.direct.set_contentdb_path(omero_contentdb_path)



def deleteImageFeatures(conn, cli, image, ftset, field=True):
    """
    Delete any OMERO.searcher feature tables attached to an image
    """
    message = ''
    iid = image.getId()

    query = ('select iml from ImageAnnotationLink as iml join '
             'fetch iml.child as fileAnn join '
             'fetch fileAnn.file join '
             'iml.parent as img where '
             'img.id = :iid and fileAnn.file.name = :filename')

    if field:
       filename = 'iid-' + str(iid) + '_feature-' + ftset + '_field.h5';
    else:
       filename = 'iid-' + str(iid) + '_feature-' + ftset + '_roi.h5';
    params = omero.sys.ParametersI()
    params.addLong('iid', iid);
    params.addString('filename', filename);

    qs = conn.getQueryService()
    imAnns = qs.findAllByQuery(query, params)

    if not imAnns:
        return message

    ds = conn.getDeleteService();
    dcs = []
    for imAnn in imAnns:
        fileAnn = imAnn.getChild()
        dcs.append(omero.api.delete.DeleteCommand(
                "/Annotation", fileAnn.id.val, None))

    delHandle = ds.queueDelete(dcs)
    cb = omero.callbacks.DeleteCallbackI(cli, delHandle)

    try:
        try:
            cb.loop(10 * len(dcs), 500)
        except omero.LockTimeout:
            m = 'Not finished in %d seconds. Cancelling...' % (len(dcs) * 5)
            sys.stderr.write(m)
            message += m
            if not delHandle.cancel():
                m = 'ERROR: Failed to cancel\n'
                sys.stderr.write(m)
                message += m

        reports = delHandle.report()
        for r in reports:
            m = 'Delete report: error:%s warning:%s, deleted:%s\n' % (
                r.error, r.warning, r.actualDeletes)
            message  += m

    finally:
        #cb.close()
        pass

    return message


def processImages(client, scriptParams):
    message = ''

    dataType = scriptParams['Data_Type']
    ids = scriptParams['IDs']
    ftset = scriptParams['Feature_set']

    try:
        conn = omero.gateway.BlitzGateway(client_obj=client)

        # Get the objects
        objects, logMessage = script_utils.getObjects(conn, scriptParams)
        message += logMessage

        if not objects:
            return message

        if dataType == 'Image':
            for image in objects:
                message += 'Processing image id:%d\n' % image.getId()
                m = deleteImageFeatures(conn, client, image, ftset, field=True)
                message += m

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
                    m = deleteImageFeatures(
                        conn, client, image, ftset, field=True)
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
        'OMERO.searcher delete individual image feature tables',
        'Delete the image feature tables belonging to each image. '
        'Note this does not delete the entries from the ContentDB',

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

        version = '0.0.1',
        authors = ['Marvin the Paranoid Android'],
        institutions = ['Heart of Gold'],
        contact = 'spli@dundee.ac.uk',
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

