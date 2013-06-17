#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Carnegie Melon University All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt #
#
# Author: Baek Hwan Cho <bhcho(at)cmu(dot)ac(dot)uk>, 2011.
# 
# Version: 1.0
#

import logging
from collections import defaultdict

from omeroweb.webclient.decorators import login_required, render_response
from webclient.webclient_gateway import OmeroWebGateway

import omero
from omero.rtypes import rint

# import featuresetInfo     # TODO import currently failing

logger = logging.getLogger('searcher')

import pyslid
from omero_searcher_config import omero_contentdb_path
pyslid.database.direct.set_contentdb_path(omero_contentdb_path)
import ricerca


# Note some of these views can be called from either the standard OMERO.web
# pages or from an OMERO.searcher page, since it is possible to iteratively
# refine results.
#
# The standard web uses single image IDs whereas OMERO.searcher may need to
# handle multiple copies of the same image with different C/Z/T, so uses a
# superid: ImageID.PixelID.C.Z.T. We need to handle both cases.


def getIdCztPnFromSuperIds(superIds, reqvars):
    """
    Gets the list of image IDs, CZTs, and pos/neg from the request
    Each superID must be in the form ImageID.PixelID.C.Z.T where PixelID is
    currently ignored (set to 0)
    """
    idCztPn = {}
    for sid in superIds:
        iid, px, czt = sid.split('.', 2)
        assert(reqvars.get("posNeg-%s" % sid) in ["pos", "neg"])
        pn = reqvars.get("posNeg-%s" % sid) == "pos"
        iid = int(iid)
        logger.debug('%s %s %s', sid, reqvars.get("posNeg-%s" % sid), pn)
        if iid in idCztPn:
            idCztPn[iid].append((czt, pn))
        else:
            idCztPn[iid] = [(czt, pn)]
    return idCztPn


def getIdCztPnFromImageIds(imageIds, reqvars):
    """
    Gets the list of image IDs, CZTs, and pos/neg from the request
    IDs will be in the form of super IDs, but since the page contains fields
    to change the CZT these may not match the original superid, so we need
    to re-read them
    """
    idCztPn = {}
    for sid in imageIds:
        iid = sid.split('.')[0]
        c = reqvars.get("selected_c-%s" % sid)
        z = reqvars.get("selected_z-%s" % sid)
        t = reqvars.get("selected_t-%s" % sid)
        czt = '%s.%s.%s' % (c, z, t)
        assert(reqvars.get("posNeg-%s" % sid) in ["pos", "neg"])
        pn = reqvars.get("posNeg-%s" % sid) == "pos"
        iid = int(iid)
        logger.debug('%s %s %s', iid, reqvars.get("posNeg-%s" % sid), pn)
        if iid in idCztPn:
            idCztPn[iid].append((czt, pn))
        else:
            idCztPn[iid] = [(czt, pn)]
    return idCztPn


def getGroupMembers(conn, request):
    """
    Get a list of user-ids and names
    """

    gid = conn.SERVICE_OPTS.getOmeroGroup()
    if gid >= 0:
        group = conn.getObject('ExperimenterGroup', gid)
    else:
        logger.warn('Failed to get group from SERVICE_OPTS.getOmeroGroup, using getGroupFromContext')
        group = conn.getGroupFromContext()
    logger.debug('group: %s', group)
    users = dict((x.child.id.val, x.child.getOmeName().val)
                    for x in group.copyGroupExperimenterMap())
    return users


def getProjectsDatasets(conn):
    """
    Get a list of dataset-ids and project/dataset names
    """

    projects = dict((p.id, (p.name, {}))
                    for p in conn.getObjects('Project', None))
    orphanDatasets = {}
    for d in conn.getObjects('Dataset', None):
        if d.getParent():
            projects[d.getParent().id][1][d.id] = d.name
        else:
            orphanDatasets[d.id] = d.name

    return (projects, orphanDatasets)


def getImageDatasetMap(conn):
    """
    It should be quicker to build a one-off mapping of images to datasets
    than it is to call im.listParents() on every image
    """
    imDsMap = defaultdict(list)
    for d in conn.getObjects('Dataset', None):
        for i in d.listChildren():
            imDsMap[i.id].append(d.id)
    return imDsMap


def listAvailableCZTS(conn, imageId, ftset):
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


def hasCZTFeature(available, czt):
    """
    Checks the list returned by listAvailbleCZTS to see if a specific CZT
    is present.

    This only checks whether features are in the associated table.
    It does not check whether the ContentDB was updated with these features.
    See trac #10973
    """
    c, z, t = czt.split('.')
    for r in available:
        if (int(c), int(z), int(t)) == r[:3]:
            return True
    return False


@login_required()
@render_response()
def index (request, conn=None, **kwargs):
    
    return {'template': 'searcher/index.html'}


@login_required(setGroupContext=True)
@render_response()
def right_plugin_search_form (request, conn=None, **kwargs):
    """
    This generates a search form in the right panel with the currently selected images, allowing
    a user to initialize a content search.
    """
    context = {'template': 'searcher/right_plugin_search_form.html'}

    images = []

    superIds = request.REQUEST.getlist('imagesuperid')
    if len(superIds) > 0:
        logger.debug('superIds: %s', superIds)
        for sid in superIds:
            iid, px, c, z, t = map(int, sid.split('.'))
            im = conn.getObject("Image", iid)
            images.append({
                    'im': im,
                    'id': im.id,
                    'superid': sid,
                    'defC': c,
                    'defZ': z,
                    'defT': t,
                    })

    else:
        imageIds = request.REQUEST.getlist('image')
        logger.debug('imageIds: %s', imageIds)
        for im in conn.getObjects("Image", imageIds):
            c = 0
            z = im.getSizeZ() / 2
            t = im.getSizeT() / 2
            images.append({
                    'im': im,
                    'id': im.id,
                    'superid': '%d.0.%d.%d.%d' % (im.id, c, z, t),
                    'defC': c,
                    'defZ': z,
                    'defT': t,
                    })

    context['images'] = images

    users = getGroupMembers(conn, request)
    context['users'] = users

    projects, orphanDatasets = getProjectsDatasets(conn)
    context['projects'] = projects
    context['datasets'] = orphanDatasets

    logger.debug('Context:%s', context)
    return context


@login_required(setGroupContext=True)
@render_response()
def searchpage( request, iIds=None, dId = None, fset = None, numret = None, negId = None, conn=None, **kwargs):
    """
    The main OMERO.searcher page. We arrive here with an initial search from the right_plugin_search_form above.
    This shows a new search form in the left panel and loads results in the center (see contentsearch below).
    Subsequent searches from the left panel simply refresh the center results pane.
    """

    context = {'template': 'searcher/contentsearch/searchpage.html'}

    logger.debug('searchpage POST:%s', request.POST)

    dId = request.POST.get("dataset_ID", None)
    if dId is not None:
        context['dataset'] = conn.getObject("Dataset", dId)
    context['fset'] = request.POST.get("featureset_Name")
    context['numret'] = request.POST.get("NumRetrieve")

    limit_users = request.POST.getlist("limit_users")
    limit_users = [int(x) for x in limit_users]
    context['limit_users'] = limit_users

    limit_datasets = request.POST.getlist("limit_datasets")
    limit_datasets = [int(x) for x in limit_datasets]
    context['limit_datasets'] = limit_datasets

    users = getGroupMembers(conn, request)
    context['users'] = users

    projects, orphanDatasets = getProjectsDatasets(conn)
    context['projects'] = projects
    context['datasets'] = orphanDatasets

    superIds = request.POST.getlist("superIds")
    if superIds:
        logger.debug('Got superIDs: %s', superIds)
        idCztPn = getIdCztPnFromSuperIds(superIds, request.POST)
        imageIds = idCztPn.keys()
    else:
        allIds = request.POST.getlist("allIds")
        logger.debug('Got allIDs: %s', allIds)
        idCztPn = getIdCztPnFromImageIds(allIds, request.POST)
        imageIds = idCztPn.keys()

    images = []
    for i in conn.getObjects("Image", imageIds):
        available = listAvailableCZTS(conn, i.id, str(context['fset']))
        for czt, pn in idCztPn[i.id]:
            hasFeats = hasCZTFeature(available, czt)
            if not hasFeats:
                logger.debug('No features found for image: %d %s', i.id, czt)
            images.append({
                    'name': i.getName(),
                    'id': i.getId(),
                    'posNeg': pn,
                    'czt': czt,
                    'superid': '%d.0.%s' % (i.getId(), czt),
                    'hasFeats': hasFeats
                    })
            context['images'] = images

    return context


# import omeroweb.searcher.searchContent as searchContent   TODO: import currently failing
@login_required(setGroupContext=True)
@render_response()
def contentsearch( request, conn=None, **kwargs):

    #server_name=request.META['SERVER_NAME']
    #owner=request.session['username']

    logger.debug('contentsearch POST:%s', request.POST)

    dId = request.POST.get("dataset_ID", None)
    fset = request.POST.get("featureset_Name")
    numret = request.POST.get("NumRetrieve")
    numret = int(numret)

    limit_users = request.POST.getlist("limit_users")
    if len(limit_users) == 0:
        context = {
            'template': 'searcher/contentsearch/search_error.html',
            'message': 'No users selected'
            }
        return context

    limit_users = set(int(x) for x in limit_users)
    logger.debug('Got limit_users: %s', limit_users)

    limit_datasets = request.POST.getlist("limit_datasets")
    if len(limit_datasets) == 0:
        context = {
            'template': 'searcher/contentsearch/search_error.html',
            'message': 'No datasets selected'
            }
        return context

    limit_datasets = set(int(x) for x in limit_datasets)
    logger.debug('Got limit_datasets: %s', limit_datasets)

    # TODO: Optimise, this is slow
    imDsMap = getImageDatasetMap(conn)

    superIds = request.POST.getlist("superIds")
    logger.debug('Got superIDs: %s', superIds)
    idCztPn = getIdCztPnFromSuperIds(superIds, request.POST)
    imageIds = idCztPn.keys()

    ftset = request.POST.get("featureset_Name")
    image_refs_dict = {}
    for i in imageIds:
        available = listAvailableCZTS(conn, i, str(fset))
        for czt, pn in idCztPn[i]:
            hasFeats = hasCZTFeature(available, czt)
            if not hasFeats:
                logger.debug('No features found for image: %d %s', i, czt)
                continue

            pxId = '0'
            ipczt = "%s.%s.%s" % (i, pxId, czt)
            pn = 1 if pn else -1

            # TODO: Figure out which scale to choose out of multiple scales
            # instead of just choosing the last
            scale = available[-1][3]
            logger.debug('Using scale: %f from image: %d', scale, i)
            image_refs_dict[ipczt] = [(scale, ''), pn]
    logger.debug('contentsearch image_refs_dict:%s', image_refs_dict)

    cdb, s = pyslid.database.direct.retrieve(conn, ftset)

    if s != 'Good':
        context = {'template':
                       'searcher/contentsearch/search_error.html'}
        context['message'] = (
            'The ContentDB for feature-set %s could not be found. '
            'Have you calculated any features?') % ftset
        return context

    def processIds(cdbr):
        return ['.'.join(str(c) for c in cdbr[6:11]), cdbr[2], cdbr[1]]

    def processSearchSet(cdb, im_ref_dict, dscale):
        # TODO: this is called multiple times by Ricerca- we shouldn't need to
        # rebuild id_cdb_dict (mapping of superids to features) each time
        logger.debug('processSearchSet cdb.keys():%s', cdb.keys())
        id_cdb_dict = dict(
            ('.'.join(str(c) for c in r[6:11]), r) for r in cdb[dscale])
        goodset_pos = []

        logger.debug('id_cdb_dict.keys %s', id_cdb_dict.keys())
        for id in im_ref_dict:
            iid = long(id.split('.')[0])
            logger.debug('id %s iid %s', id, iid)
            feats = id_cdb_dict[id][11:]
            #logger.debug('feats %s', feats)
            goodset_pos.append([id, 1, feats])
            #logger.debug('%s', [id, 1, feats])

        #logger.debug('goodset_pos %s', goodset_pos)
        return goodset_pos

    # TODO:
    # Reminder: scale is currently partially hard coded until we work out
    # what it's meant to be and how it should be set
    # TODO:
    # If ContentDB contain duplicate entries for an image at the same scale
    # rankingWrapper() will return duplicate results

    logger.debug('contentsearch cdb.keys():%s', cdb.keys())
    if len(image_refs_dict) == 0:
        # No images had features
        context = {'template':
                       'searcher/contentsearch/search_error.html'}
        context['message'] = (
            'No features were found for the reference images. Please use the '
            'Omero Searcher Feature Calculation script to calculate them '
            'before running a search.')
        return context

    try:
        final_result, dscale = ricerca.content.rankingWrapper(
            cdb, image_refs_dict, processIds, processSearchSet)
        logger.debug('contentsearch final_results:%s dscale:%s',
                     final_result, dscale)
    except Exception as e:
        logger.error(str(e))
        raise

    im_ids_sorted = [r[0] for r in final_result]
    logger.debug('contentsearch im_ids_sorted:%s', im_ids_sorted)


    context = {'template': 'searcher/contentsearch/searchresult.html'}

    def filter_image(im):
        if im.getOwner().id not in limit_users:
            return False
        # http://stackoverflow.com/a/2197506
        return any(ld in limit_datasets for ld in imDsMap[im.id])

    def image_batch_load(conn, im_ids_sorted, numret):
        """
        We don't want to load all images, but since we'll filter out some we
        don't know how many to load, and it's also possible for images to
        have been deleted but remain in the contentDB.
        Read in chunks until we have the required number of images.
        """
        img_map = {}

        # We need to choose the batch size
        # Remember getObjects() returns objects in an unspecified order, so we
        # must iterate through the entire result and re-order
        batch_size = numret

        i = 0
        while i < len(im_ids_sorted):
            batch_sids = im_ids_sorted[i:i + batch_size]
            batch_ids = [int(id.split('.')[0]) for id in batch_sids]
            batch_ims = conn.getObjects('Image', batch_ids)
            i += batch_size

            img_map.update((im.id, im) for im in batch_ims if filter_image(im))
            if len(img_map) >= numret:
                break

        logger.debug('img_map:%s', img_map)
        return img_map


    imgMap = image_batch_load(conn, im_ids_sorted, numret)

    images = []
    ranki = 0
    for i in im_ids_sorted:
        iid = int(i.split(".")[0])
        if iid in imgMap:
            img = imgMap[iid]
            # id.px.c.z.t
            czt = i.split(".", 2)[2]
            ranki += 1
            images.append({'name':img.getName(),
                'id':iid,
                'getPermsCss': img.getPermsCss(),
                'ranki': ranki,
                'superid': i,
                'czt': czt})
        if ranki == numret:
            break
    context['images'] = images
    #logger.debug('contentsearch images:%s', images)

    return context


@login_required()
def featureCalculationConfig( request, object_type = None, object_ID = None, conn=None, **kwargs):

    ## for visualizing the results in the template html file from here
    objecttype = []
    objecttype.append(object_type)
    
    objectid = []
    objectid.append(long(object_ID))

    datasetids = []
    if object_type == 'dataset':
        datasetids.append(long(object_ID))
    elif object_type == 'image':
        # get the parent dataset ids
        img = conn.getObject('Image', long(object_ID))
        parent = img.getParent()
        ID = parent.getId()
        datasetids.append(long(ID))
        

    

    class PARAM:
        eContext = {'breadcrumb': list()}
        containers = {'Obj_Type':list(), 'Obj_ID':list(), 'Dataset_ID':list()}

    param = PARAM
    param.containers['Obj_Type'] = objecttype
    param.containers['Obj_ID'] = objectid
    param.containers['Dataset_ID'] = datasetids
    param.eContext['breadcrumb'] = ['Configuration for Feature & FALCON']
    
    menu = request.REQUEST.get("menu")
    if menu is not None:
        request.session['nav']['menu'] = menu
    else:
        menu = request.session['nav']['menu']
    try:
        url = reverse(viewname="load_template", args=[menu])
    except:
        url = reverse("webindex")

    context = {'nav':request.session['nav'], 'url':url, 'eContext':param.eContext, 'param':param}


    template = 'feature/feat_calc_config.html'

    t = template_loader.get_template(template)
    c = Context(request,context)
    return HttpResponse(t.render(c))


# TODO fix imports
#import pyslid.features
#import pyslid.utilities
#import pyslid.database.direct

import numpy

@login_required()
def featureCalculation( request, object_type = None, object_ID = None, featureset = None, contentDB_config = None, conn=None, **kwargs):

    class RESULT:
        iid=0
        uid=''
        ANSWER=''


    results = []    
    type_obj = str(object_type).lower()
    featset = str(featureset).lower()
    ID = long(object_ID)
    ContentDB = str(contentDB_config)



    field = True
    rid = []
    pixel = 0
    zslice = 0    #Currently, this code does NOT deal with 3D stack images yet.
    timepoint = 0 #Currently, this code does NOT deal with time-series images yet.
    threshold = None
    
    if type_obj == 'dataset':
        # get all images and caculate and link
        datasetWrapper = conn.getObject('Dataset', long(object_ID))
        L = datasetWrapper.getChildLinks()
        iids = []
        for imgWrapper in L:
            iids.append(imgWrapper.getId())
        iids.sort()
        
        for iid in iids:
            result = RESULT()
            result.iid=iid
            image = conn.getObject("Image", long(iid))
            result.uid = image.getOwnerOmeName()
            ANS, table = pyslid.features.has( conn, iid, featset )
            if not ANS:
                answer = False
                if str(featureset).lower() == "slf33": # slf33 need to caculate features for every channel
                    sizeC = image.getSizeC()
                    for channel in range(sizeC):
                        try:
                            [ids, feats] = pyslid.features.calculate(conn, long(iid), featset, field, rid, pixel, [channel], zslice, timepoint, threshold)
                            if len(feats) == 161: #slf33 should have 161 features
                                answer = pyslid.features.link(conn, long(iid), ids, feats,  featset, field, rid, pixel, channel,zslice, timepoint)
                        except:
                            answer = False
                else:
                    try:
                        [ids, feats] = pyslid.features.calculate( conn, long(iid), featset, field, rid, pixel, [0], zslice, timepoint, threshold)
                        if len(feats) >0:         
                            answer = pyslid.features.link( conn, long(iid), ids, feats, featset, field, rid, pixel, 0,zslice, timepoint )
                    except:
                        answer = False
                if answer:
                    result.ANSWER="Done"
                else:
                    result.ANSWER="FAILED"
                results.append(result)
            else:
                result.ANSWER="Feature file already exists"
                results.append(result)
            
    elif type_obj == 'image':
        # calculate/link on that image
        iid = long(object_ID)
        result = RESULT()
        result.iid=iid
        image = conn.getObject("Image", iid)
        result.uid = image.getOwnerOmeName()
        ANS, table = pyslid.features.has( conn, iid, featset )
        if not ANS:
            answer = False
            try:
                if str(featureset).lower() == "slf33": # slf33 need to caculate features for every channel
                    sizeC = image.getSizeC()
                    for channel in range(sizeC):
                        [ids, feats] = pyslid.features.calculate(conn, long(iid), featset, field, rid, pixel, [channel], zslice, timepoint, threshold)
                        if len(feats) == 161: #slf33 should have 161 features
                            answer = pyslid.features.link(conn, long(iid), ids, feats,  featset, field, rid, pixel, channel,zslice, timepoint)
                else:
                    [ids, feats] = pyslid.features.calculate( conn, long(iid), featset, )
                    if len(feats) >0:  
                        answer = pyslid.features.link( conn, long(iid), ids, feats, featset, field, rid )
            except:
                answer = False
                
            if answer:
                result.ANSWER="Done"
            else:
                result.ANSWER="FAILED"
            results.append(result)
        else:
            result.ANSWER="Feature file already exists"
            results.append(result)


    server_name=request.META['SERVER_NAME']
    owner=request.session['username']

    ## update contentDB
    
    results_contentDB = []
    result_content_entire=RESULT()
    result_content_specific=RESULT()


    tmp = ContentDB.split("-")
    if tmp[0] is "y":
        try:
            # update entire content DB

            # currently, this is possible only when a user selected One image
            iid = long(object_ID)
            [ids, feats] = pyslid.features.get( conn, 'vector', iid, featset)
    
            pixels = []
            channel = []
            zslice = []
            timepoint = []
            for i in range(len(feats)):
                pixels.append(feats[i][0])
                channel.append(feats[i][1])
                zslice.append(feats[i][2])
                timepoint.append(feats[i][3])
            feature_ids = ids[4:]
            
            if len(ids)==0:
                result_content_entire.ANSWER = "Update entire contentDB: FAILED (feature table error)"
            else:
                data, msg = pyslid.database.direct.retrieve(conn, featset) # INDEX, server, username, iid, pixels, channel, zslice, timepoint, features
                if len(data)==0:
                    # initialize DB
                    pyslid.database.direct.initialize(conn, feature_ids, featset)
                    for i in range(len(feats)):
                        pyslid.database.direct.update(conn, str(server_name), str(owner), iid, pixels[i], channel[i], zslice[i], timepoint[i], feature_ids, feats[i][4:], featset)
                    result_content_entire.ANSWER = "Update entire contentDB: Initialized and Updated"
                else:
                    # update DB
                    # check whether the contentDB already has this data
                    data2 = numpy.array(data)[:,3:8]
                    data2 = numpy.float64(data2)
                    
                    for j in range(len(feats)):
                        cdata = [iid, pixels[j], channel[j], zslice[j], timepoint[j]]
                        cdata2 = numpy.float64(cdata)
                        ind = numpy.where(data2 == cdata2, 1, -1)
                        ind2 = numpy.sum(ind, axis=1)
                        ind3=numpy.where(ind2==len(cdata2))[0]
                        if len(ind3)>0: # if the contentDB alrady includes it
                            result_content_entire.ANSWER = "Update entire contentDB: Failed. The contentDB already has it"
                        else:
                            pyslid.database.direct.update(conn, str(server_name), str(owner), iid, pixels[j], channel[j], zslice[j], timepoint[j], feature_ids, feats[j][4:], featset)
                            result_content_entire.ANSWER = "Update entire contentDB: Done"
        except:
            result_content_entire.ANSWER = "Update entire contentDB: FAILED"
    else:
        result_content_entire.ANSWER = "Update entire contentDB: Not executed"

    if tmp[1] is not "0":
        try:
            # update specific content DB
            did = long(tmp[1])
            iid = long(object_ID)
            
            [ids, feats] = pyslid.features.get( conn, 'vector', iid, featset)
    
            pixels = []
            channel = []
            zslice = []
            timepoint = []
            for i in range(len(feats)):
                pixels.append(feats[i][0])
                channel.append(feats[i][1])
                zslice.append(feats[i][2])
                timepoint.append(feats[i][3])
            feature_ids = ids[4:]
            if len(ids)==0:
                result_content_entire.ANSWER = "Update entire contentDB: FAILED (feature table error)"
            else:
                data, msg = pyslid.database.direct.retrieve(conn, featset, did) # INDEX, server, username, iid, pixels, channel, zslice, timepoint, features
                if len(data)==0:
                    # initialize DB
                    pyslid.database.direct.initialize(conn, feature_ids, featset, did)
                    for i in range(len(feats)):
                        pyslid.database.direct.update(conn, str(server_name), str(owner), iid, pixels[i], channel[i], zslice[i], timepoint[i], feature_ids, feats[i][4:], featset, did)
                    result_content_entire.ANSWER = "Update entire contentDB: Initialized and Updated"
                else:
                    # update DB
                    # check whether the contentDB already has this data
                    data2 = numpy.array(data)[:,3:8]
                    data2 = numpy.float64(data2)
                    for j in range(len(feats)):
                        cdata = [iid, pixels[j], channel[j], zslice[j], timepoint[j]]
                        cdata2 = numpy.float64(cdata)
                        ind = numpy.where(data2 == cdata2, 1, -1)
                        ind2 = numpy.sum(ind, axis=1)
                        ind3=numpy.where(ind2==len(cdata2))[0]
                        if len(ind3)>0: # if the contentDB alrady includes it
                            result_content_specific.ANSWER = "Update the contentDB for dataset "+str(did)+": Failed. The contentDB already has it"
                        else:
                            pyslid.database.direct.update(conn, str(server_name), str(owner), iid, pixels[j], channel[j], zslice[j], timepoint[j], feature_ids, feats[j][4:], featset, did)
                            result_content_specific.ANSWER = "Update the contentDB for dataset "+str(did)+": Done"
        except:
            result_content_specific.ANSWER = "Update the contentDB for dataset "+str(did)+": FAILED"
        
    else:
        result_content_specific.ANSWER = "Update the specific contentDB for the dataset : Not executed"

    results_contentDB.append(result_content_entire)
    results_contentDB.append(result_content_specific)
        
    # Initialize if needed
    # then search whether there is the same data in the contentDB
##    answer2 = FALCONfunctions.updateFALCONdbFileRedo(session,long(object_ID),str(server_name),str(owner),str(featureset.lower()))
##    answer3 = FALCONfunctions.updateFALCONdbFileRedo(session,'',str(server_name),str(owner),str(featureset.lower()))





    ## for visualizing the results in the template html file from here
    objecttype = []
    objecttype.append(object_type)
    
    objectid = []
    objectid.append(long(object_ID))

    Featureset = []
    Featureset.append(featureset)

    class PARAM:
        eContext = {'breadcrumb': list()}
        containers = {'Obj_Type':list(), 'Obj_ID':list(), 'Feature_Set':list(), 'Answers':list(), 'Answers_contentDB':list()}

    param = PARAM
    param.containers['Obj_Type'] = [type_obj]
    param.containers['Obj_ID'] = [long(object_ID)]
    param.containers['Feature_Set'] = featset
    param.containers['Answers'] = results
    param.containers['Answers_contentDB'] = results_contentDB
    param.eContext['breadcrumb'] = ['Feature & contentDB']


    
    menu = request.REQUEST.get("menu")
    if menu is not None:
        request.session['nav']['menu'] = menu
    else:
        menu = request.session['nav']['menu']
    try:
        url = reverse(viewname="load_template", args=[menu])
    except:
        url = reverse("webindex")

    context = {'nav':request.session['nav'], 'url':url, 'eContext':param.eContext, 'param':param}


    template = 'feature/feat_falcon.html'

    t = template_loader.get_template(template)
    c = Context(request,context)
    return HttpResponse(t.render(c))



