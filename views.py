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

from omeroweb.webclient.decorators import login_required, render_response
from webclient.webclient_gateway import OmeroWebGateway

import omero
from omero.rtypes import rint

# import featuresetInfo     # TODO import currently failing

logger = logging.getLogger('searcher')


@login_required()
@render_response()
def index (request, conn=None, **kwargs):
    
    return {'template': 'searcher/index.html'}


@login_required()
@render_response()
def right_plugin_search_form (request, conn=None, **kwargs):
    """
    This generates a search form in the right panel with the currently selected images, allowing
    a user to initialize a content search.
    """
    context = {'template': 'searcher/right_plugin_search_form.html'}

    datasets = list(conn.getObjects("Dataset"))
    datasets.sort(key=lambda x: x.getName() and x.getName().lower())
    context['datasets'] = datasets

    imageIds =  request.REQUEST.getlist('image')
    if len(imageIds) > 0:
        context['images'] = list( conn.getObjects("Image", imageIds) )
    return context


@login_required()
@render_response()
def searchpage( request, iIds=None, dId = None, fset = None, numret = None, negId = None, conn=None, **kwargs):
    """
    The main OMERO.searcher page. We arrive here with an initial search from the right_plugin_search_form above.
    This shows a new search form in the left panel and loads results in the center (see contentsearch below).
    Subsequent searches from the left panel simply refresh the center results pane.
    """

    context = {'template': 'searcher/contentsearch/searchpage.html'}

    dId = request.POST.get("dataset_ID", None)
    if dId is not None:
        context['dataset'] = conn.getObject("Dataset", dId)
    context['fset'] = request.POST.get("featureset_Name")
    context['numret'] = request.POST.get("NumRetrieve")

    iIds = request.POST.getlist("allIds")
    imageIds = [int(i) for i in iIds]
    images = []
    for i in conn.getObjects("Image", imageIds):
        posNeg = request.POST.get("posNeg-%s" % i.id) == "pos"
        czt = request.POST.get("czt-%s" % i.id)
        images.append({'name':i.getName(),
            'id':i.getId(),
            'posNeg': posNeg,
            'czt': czt})
    context['images'] = images

    return context


# import omeroweb.searcher.searchContent as searchContent   TODO: import currently failing
@login_required()
@render_response()
def contentsearch( request, conn=None, **kwargs):

    #server_name=request.META['SERVER_NAME']
    #owner=request.session['username']

    dId = request.POST.get("dataset_ID", None)
    fset = request.POST.get("featureset_Name")
    numret = request.POST.get("NumRetrieve")

    iIds = request.POST.getlist("allIds")
    imageIds = [int(i) for i in iIds]
    imageIDs = []
    negimageIDs = []
    for i in imageIds:
        idCZT = "%s.%s" % (i, request.POST.get("czt-%s" % i))
        if request.POST.get("posNeg-%s" % i) == "pos":
            imageIDs.append(idCZT)
        else:
            negimageIDs.append(idCZT)

    parameterMap = {}
    parameterMap["posIDs"]=imageIDs
    parameterMap["Dataset_ID"]=dId
    parameterMap["Feature_Set_Name"]=fset
    parameterMap["negIDs"]=negimageIDs
    parameterMap["numret"]=numret

    print parameterMap

    # im_ids_sorted, MSG = searchContent.relevanceFeedback(conn, parameterMap, server_name,owner)

    im_ids_sorted = []

    # ------------ RANDOM IMAGES (replace this with search!) --------------
    f = omero.sys.Filter()
    f.limit = rint(numret)
    randomImages = conn.getQueryService().findAll("Image", f)
    for i in randomImages:
        im_ids_sorted.append("%s.0.0.0" % i.id.val)
    # ---------------------------------------------------------------------


    context = {'template': 'searcher/contentsearch/searchresult.html'}

    imgMap = {}
    imgIds = [int(i.split(".")[0]) for i in im_ids_sorted]
    imgs = conn.getObjects("Image", imgIds)     # not sorted!
    for i in imgs:
        imgMap[i.getId()] = i

    images = []
    for i in im_ids_sorted:
        iid = int(i.split(".")[0])
        if iid in imgMap:
            img = imgMap[iid]
            czt = i.split(".",1)[1]
            images.append({'name':img.getName(),
                'id':iid,
                'getPermsCss': img.getPermsCss(),
                'czt': czt})
    context['images'] = images

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



