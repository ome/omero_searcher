import omero
from omero import scripts
from omero.rtypes import rstring
from datetime import datetime
import sys

import pyslid
from omeroweb.omero_searcher.omero_searcher_config import omero_contentdb_path
from omeroweb.omero_searcher.omero_searcher_config import enabled_featuresets
pyslid.database.direct.set_contentdb_path(omero_contentdb_path)


class CdbArgs:

    class Cdb1:
        def __init__(self, uid, scale):
            self.server = 'NA'
            self.uid = uid
            self.scale = scale
            self.iid = []
            self.px = []
            self.c = []
            self.z = []
            self.t = []
            self.feats = []

    def __init__(self):
        self.dbs = {}
        self.fid = None

    def get(self, uid, scale):
        k = (uid, scale)
        if k not in self.dbs:
            self.dbs[k] = self.Cdb1(uid, scale)
        return self.dbs[k]

    def add(self, uid, scale, fid, iid, px, c, z, t, feats):
        if not self.fid:
            self.fid = fid
        if self.fid != fid:
            raise Exception('Feature IDs for %d.%d.%d.%d.%d %e does not match existing IDs' %
                            (iid, px, c, z, t, scale))

        cdb = self.get(uid, scale)
        cdb.iid.append(iid)
        cdb.px.append(px)
        cdb.c.append(c)
        cdb.z.append(z)
        cdb.t.append(t)
        cdb.feats.append(feats)



def imageFeatures(conn, image, ftset, cdbs):
    """
    Read in features from a HDF5 table attached to an image, save to the
    ContentDB.
    """
    message = ''
    iid = image.getId()

    try:
        tab = pyslid.features.get(conn, 'vector', iid, set=ftset)
    except pyslid.utilities.PyslidException as e:
        m = 'No features found for image:%d\n' % iid
        sys.stderr.write(m)
        return m

    uid = image.getOwner().getId()
    fid = tab[0][5:]
    featsWithMeta = tab[1]
    n = len(featsWithMeta)

    # Iterate in reverse order, so that in case of duplicates the most
    # recent is kept
    featsWithMeta.reverse()
    uniq = set()

    for f in featsWithMeta:
        iden = f[:5]
        if iden in uniq:
            continue
        else:
            uniq.add(iden)

        px, c, z, t, scale = f[:5]
        feats = f[5:]
        cdbs.add(uid, scale, fid, iid, px, c, z, t, feats)

    sys.stdout.write(
        'Found %d feature rows including %d duplicates for image:%d\n' % (
            n, n - len(uniq), iid))
    return message


def saveToCdb(conn, ftset, cdbs):
    message = ''

    # Delete the old ContentDB
    r = pyslid.database.direct.deleteTableLink(conn, ftset, did=None)
    if not r:
        m = 'ERROR: Failed to delete old ContentDB\n'
        sys.stderr.write(m)
        message += m

    # Create the new global ContentDB
    for k in cdbs.dbs:
        m = 'Saving ContentDB user:%d scale:%e\n' % k
        sys.stdout.write(m)
        message += m

        cdb = cdbs.dbs[k]
        answer, m = pyslid.database.direct.updateDataset(
            conn, cdb.server, cdb.uid, cdb.scale,
            cdb.iid, cdb.px, cdb.c, cdb.z, cdb.t,
            cdbs.fid, cdb.feats, ftset, did=None)
        message += m + '\n'

        superids = ''.join('\t%d.%d.%d.%d.%d\n' % s for s in
                           zip(*(cdb.iid, cdb.px, cdb.c, cdb.z, cdb.t)))

        if answer:
            sys.stdout.write('Added ContentDB features (scale:%e) from:\n%s' % (
                    cdb.scale, superids))
        else:
            m = 'Failed to add ContentDB features (user:%d scale:%e) from:\n%s' % (
                cdb.uid, cdb.scale, superids)
            sys.stderr.write(m)
            message += m

    return message


def processImages(client, scriptParams):
    message = ''

    ftset = scriptParams['Feature_set']

    try:
        conn = omero.gateway.BlitzGateway(client_obj=client)

        cdbs = CdbArgs()

        # Get all images
        ims = conn.getObjects('Image', None)
        for im in ims:
            m = imageFeatures(conn, im, ftset, cdbs)
            message += m

        m = saveToCdb(conn, ftset, cdbs)
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
        'OMERO.searcher rebuild ContentDB',
        'Delete the ContentDB and rebuild from image feature tables',

        scripts.String('Feature_set', optional=False, grouping='1',
                       description='SLF set',
                       values=[rstring(f) for f in enabled_featuresets],
                       default=enabled_featuresets[0]),

        version = '0.0.1',
        authors = ['Murphy Lab'],
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

