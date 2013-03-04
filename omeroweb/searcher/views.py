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

    iIds = request.POST.getlist("allIds")
    imageIds = [int(i) for i in iIds]
    context["images"] = conn.getObjects("Image", imageIds)
    dId = request.POST.get("dataset_ID", None)
    if dId is not None:
        context['dataset'] = conn.getObject("Dataset", dId)
    context['fset'] = request.POST.get("featureset_Name")
    context['numret'] = request.POST.get("NumRetrieve")

    # TODO: pass these other parameters to context too!
    negId = []
    czts = []
    for i in iIds:
        if request.POST.get("posNeg-%s" % i) == "neg":
            negId.append(i)
        czts.append(request.POST.get("czt-%s" % i))

    return context


@login_required()
def select_czt( request, ImageID = None, **kwargs):
    # get connection
    conn = None
    try:
        conn = kwargs["conn"]        
    except:
        logger.error(traceback.format_exc())
        return handlerInternalError("Connection is not available. Please contact your administrator.")

    iid = long(ImageID)
    Results = featuresetInfo.getInfo(conn, iid)

    
    
    image = conn.getObject("Image",iid)
    sizeZ = image.getSizeZ()
    sizeT = image.getSizeT()
    sizeC = image.getSizeC()
    names = [c.getName() for c in image.getChannels()]

    
    return render_to_response('searcher/contentsearch/select_czt.html',{'sizeC': sizeC, 'sizeZ': sizeZ, 'sizeT': sizeT, 'channelnames': names, 'results':Results})

 





# import omeroweb.searcher.searchContent as searchContent   TODO: import currently failing
@login_required()
def contentsearch( request, iIds, dId = None, fset = None, numret = None, negId = None, conn=None, **kwargs):

    server_name=request.META['SERVER_NAME']
    owner=request.session['username']

    session = conn.c.sf;

    imageIDs = []
    if iIds:
        img_tuple = iIds.split(",")
        for img in img_tuple:
            if img !="":
                imageIDs.append(str(img))
   

    negimageIDs = []
    if negId:
        img_tuple = negId.split(",")
        for img in img_tuple:
            if img !="":
                negimageIDs.append(str(img))

    for itm in negimageIDs:        
        if itm in imageIDs:
            imageIDs.remove(itm)


    datasetID = []
    if dId != None:
        dID = long(dId)
        datasetID.append(dID)
    else:
        datasetID.append(long(0))
    
    if fset == None:
        fset = "SLF33"
    
    NumRetrieve = []    
    if numret ==None:
        NumRetrieve.append(long(10))
    else:
        NumRetrieve.append(long(numret)) 
    
    parameterMap = {}
    parameterMap["posIDs"]=imageIDs
    parameterMap["Dataset_ID"]=datasetID
    parameterMap["Feature_Set_Name"]=fset
    parameterMap["negIDs"]=negimageIDs
    parameterMap["numret"]=NumRetrieve

    im_ids_sorted, MSG = searchContent.relevanceFeedback(conn, parameterMap, server_name,owner)

#    im_ids_sorted = imageIDs
#    MSG=''
    im_list = list()
    rank = 1
    for line in im_ids_sorted:
        id_tuple = line[0].split('.')
        ID = long(id_tuple[0])
        im = conn.getObject("Image",ID)
        if im is not None:
            im.pid = long(id_tuple[1])
            im.cid = long(id_tuple[2])
            im.zid = long(id_tuple[3])
            im.tid = long(id_tuple[4])
            im.server_name = str(line[1])
            im.owner_ome_name = str(line[2])
            im.rank = rank
            rank = rank + 1
            if im is not None:
                im_list.append(im)

    im_ids = [im.id for im in im_list]
    im_annotation_counter = conn.getCollectionCount("Image", "annotationLinks", im_ids)
    
    im_list_with_counters = list()
    for im in im_list:
        im.annotation_counter = im_annotation_counter.get(im.id)
        im_list_with_counters.append(im)
        
    class MANAGER:
        c_size = 0
        eContext = {'breadcrumb': list()} 
        containers = {'projects': list(), 'datasets': list(), 'images': list(), 'screens': list(), 'plates': list()}
        errorMsg = ""

    manager = MANAGER
    manager.c_size = len(im_list_with_counters)
    manager.containers['images']= im_list_with_counters
    manager.errorMsg = MSG

    manager.eContext['breadcrumb'] = ['Search']
    


    class PARAM:
        containers = {'selected_imgs':list(), 'dataset_ID':list(), 'featureset_name':list(), 'selected_imgs_pos':list(), 'selected_imgs_neg':list(), 'numretreive':list()}

#    negimageIDs : list of negative ids
    im_list2 = list()
    im_list_pos = list()
    im_list_neg = list()
    for ID in parameterMap["posIDs"]:
        id_tuple = ID.split('.')
        iid=id_tuple[0]
        flag = False
        im = conn.getObject("Image",iid)
        im.pid = id_tuple[1]
        im.cid = id_tuple[2]
        im.zid = id_tuple[3]
        im.tid = id_tuple[4]
        im_list2.append(im)
        im_list_pos.append(im)

    for ID in parameterMap["negIDs"]:
        id_tuple = ID.split('.')
        iid=id_tuple[0]
        flag = False
        im = conn.getObject("Image",iid)
        im.pid = id_tuple[1]
        im.cid = id_tuple[2]
        im.zid = id_tuple[3]
        im.tid = id_tuple[4]
        im_list2.append(im)
        im_list_neg.append(im)
            

    im_ids = [im.id for im in im_list2]
    im_annotation_counter2 = conn.getCollectionCount("Image", "annotationLinks", im_ids)
    im_list_with_counters2 = list()
    for im in im_list2:
        im.annotation_counter = im_annotation_counter2.get(im.id)
        im_list_with_counters2.append(im)

    im_ids = [im.id for im in im_list_pos]
    im_annotation_counter_pos = conn.getCollectionCount("Image", "annotationLinks", im_ids)
    im_list_with_counters_pos = list()
    for im in im_list_pos:
        im.annotation_counter = im_annotation_counter_pos.get(im.id)
        im_list_with_counters_pos.append(im)

    im_ids = [im.id for im in im_list_neg]
    im_annotation_counter_neg = conn.getCollectionCount("Image", "annotationLinks", im_ids)
    im_list_with_counters_neg = list()
    for im in im_list_neg:
        im.annotation_counter = im_annotation_counter_neg.get(im.id)
        im_list_with_counters_neg.append(im)    


    param = PARAM
    param.containers['selected_imgs'] = im_list_with_counters2
    param.containers['selected_imgs_pos'] = im_list_with_counters_pos
    param.containers['selected_imgs_neg'] = im_list_with_counters_neg
    param.containers['dataset_ID'] = parameterMap["Dataset_ID"]
    param.containers['featureset_name'] = parameterMap["Feature_Set_Name"]
    param.containers['numretreive'] = NumRetrieve
    
    menu = request.REQUEST.get("menu")
    if menu is not None:
        request.session['nav']['menu'] = menu
    else:
        menu = request.session['nav']['menu']
    try:
        url = reverse(viewname="load_template", args=[menu])
    except:
        url = reverse("webindex")
    str_sorted = ''.join(str(im_ids_sorted))
    context = {'nav':request.session['nav'], 'url':url, 'eContext':manager.eContext, 'manager':manager, 'output_IDs':str_sorted, 'param':param}
    
    template = 'searcher/contentsearch/searchresult.html'

    t = template_loader.get_template(template)
    c = Context(request,context)
    try:
        return HttpResponse(t.render(c))
    except:
        logger.error(traceback.format_exc())
        return None

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



