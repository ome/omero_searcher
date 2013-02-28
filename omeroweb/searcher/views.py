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

import sys
import copy
import re
import os
import calendar
import cStringIO
import datetime
import httplib
import Ice
import locale
import logging
import traceback

import shutil
import zipfile
import glob

from time import time
from thread import start_new_thread

from omero_version import omero_version
import omero, omero.scripts 
from omero.rtypes import *

from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore
from django.core import template_loader
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import render_to_response
from django.template import RequestContext as Context
from django.utils import simplejson
from django.views.defaults import page_not_found, server_error
from django.views import debug
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import smart_str
from django.core.servers.basehttp import FileWrapper

from webclient.webclient_gateway import OmeroWebGateway
from omeroweb.webclient.webclient_utils import string_to_dict

##from webclient_http import HttpJavascriptRedirect, HttpJavascriptResponse, HttpLoginRedirect

##from webclient_utils import _formatReport, _purgeCallback
from webclient.forms import ShareForm, BasketShareForm, ShareCommentForm, \
                    ContainerForm, ContainerNameForm, ContainerDescriptionForm, \
                    CommentAnnotationForm, TagAnnotationForm, \
                    UploadFileForm, UsersForm, ActiveGroupForm, HistoryTypeForm, \
                    MetadataFilterForm, MetadataDetectorForm, MetadataChannelForm, \
                    MetadataEnvironmentForm, MetadataObjectiveForm, MetadataObjectiveSettingsForm, MetadataStageLabelForm, \
                    MetadataLightSourceForm, MetadataDichroicForm, MetadataMicroscopeForm, \
                    TagListForm, FileListForm, TagFilterForm, \
                    MultiAnnotationForm, \
                    WellIndexForm

from webclient.controller import BaseController
##from controller.index import BaseIndex
from webclient.controller.basket import BaseBasket
##from controller.container import BaseContainer
##from controller.help import BaseHelp
##from controller.history import BaseCalendar
##from controller.impexp import BaseImpexp
##from controller.search import BaseSearch
##from controller.share import BaseShare
##
##from omeroweb.webadmin.forms import MyAccountForm, UploadPhotoForm, LoginForm, ChangePassword
##from omeroweb.webadmin.controller.experimenter import BaseExperimenter 
##from omeroweb.webadmin.controller.uploadfile import BaseUploadFile
##from omeroweb.webadmin.webadmin_utils import _checkVersion, _isServerOn, toBoolean, upgradeCheck

from omeroweb.webgateway.views import getBlitzConnection
from omeroweb.webgateway import views as webgateway_views

from omeroweb.feedback.views import handlerInternalError
from omeroweb.webclient.webclient_http import HttpJavascriptRedirect, HttpJavascriptResponse, HttpLoginRedirect




import settings


connectors = {}
share_connectors = {}


logger = logging.getLogger('searcher')

def index (request):
    conn = getBlitzConnection (request, useragent="OMERO.searcher")
#    if conn is None or not conn.isConnected():
#        return HttpResponseRedirect(reverse('searcher_login'))

    return render_to_response('searcher/index.html', {'client': conn})


################################################################################
# Blitz Gateway Connection

def getShareConnection (request, share_id):
    browsersession_key = request.session.session_key
    share_conn_key = "S:%s#%s#%s" % (browsersession_key, request.session.get('server'), share_id)
    share = getBlitzConnection(request, force_key=share_conn_key, useragent="OMERO.web")
    share.attachToShare(share_id)
    request.session['shares'][share_id] = share._sessionUuid
    request.session.modified = True    
    logger.debug('shared connection: %s : %s' % (share_id, share._sessionUuid))
    return share

################################################################################
# decorators

def _session_logout (request, server_id):
    webgateway_views._session_logout(request, server_id)

    try:
        if request.session.get('shares') is not None:
            for key in request.session.get('shares').iterkeys():
                session_key = "S:%s#%s#%s" % (request.session.session_key,server_id, key)
                webgateway_views._session_logout(request,server_id, force_key=session_key)
        for k in request.session.keys():
            if request.session.has_key(k):
                del request.session[k]
    except:
        logger.error(traceback.format_exc())


def isUserConnected (f):
    def wrapped (request, *args, **kwargs):
        #this check the connection exist, if not it will redirect to login page
        server = string_to_dict(request.REQUEST.get('path')).get('server',request.REQUEST.get('server', None))
        url = request.REQUEST.get('url')
        if url is None or len(url) == 0:
            if request.META.get('QUERY_STRING'):
                url = '%s?%s' % (request.META.get('PATH_INFO'), request.META.get('QUERY_STRING'))
            else:
                url = '%s' % (request.META.get('PATH_INFO'))
        
        conn = None
        try:
            conn = getBlitzConnection(request, useragent="OMERO.web")
        except Exception, x:
            logger.error(traceback.format_exc())
        
        if conn is None:
            # TODO: Should be changed to use HttpRequest.is_ajax()
            # http://docs.djangoproject.com/en/dev/ref/request-response/
            # Thu  6 Jan 2011 09:57:27 GMT -- callan at blackcat dot ca
            if request.is_ajax():
                return HttpResponseServerError(reverse("weblogin"))
            _session_logout(request, request.REQUEST.get('server', None))
            if server is not None:
                return HttpLoginRedirect(reverse("weblogin")+(("?url=%s&server=%s") % (url,server)))
            return HttpLoginRedirect(reverse("weblogin")+(("?url=%s") % url))
        
        conn_share = None
        share_id = kwargs.get('share_id', None)
        if share_id is not None:
            sh = conn.getShare(share_id)
            if sh is not None:
                try:
                    if sh.getOwner().id != conn.getEventContext().userId:
                        conn_share = getShareConnection(request, share_id)
                except Exception, x:
                    logger.error(traceback.format_exc())
        
        sessionHelper(request)
        kwargs["error"] = request.REQUEST.get('error')
        kwargs["conn"] = conn
        kwargs["conn_share"] = conn_share
        kwargs["url"] = url
        return f(request, *args, **kwargs)
    return wrapped

def sessionHelper(request):
    changes = False
    if request.session.get('callback') is None:
        request.session['callback'] = dict()
        changes = True
    if request.session.get('shares') is None:
        request.session['shares'] = dict()
        changes = True
    if request.session.get('imageInBasket') is None:
        request.session['imageInBasket'] = set()
        changes = True
    #if request.session.get('datasetInBasket') is None:
    #    request.session['datasetInBasket'] = set()
    if request.session.get('nav') is None:
        if request.session.get('server') is not None:
            blitz = settings.SERVER_LIST.get(pk=request.session.get('server'))
        elif request.session.get('host') is not None:
            blitz = settings.SERVER_LIST.get(host=request.session.get('host'))
        blitz = "%s:%s" % (blitz.host, blitz.port)
        request.session['nav']={"blitz": blitz, "menu": "mydata", "view": "tree", "basket": 0, "experimenter":None}
        changes = True
    if changes:
        request.session.modified = True
            
        
################################################################################
# views controll
###########################################################################
@isUserConnected
def load_template(request, menu, **kwargs):
    request.session.modified = True
        
    if menu == 'userdata':
        template = "webclient/data/containers.html"
    elif menu == 'usertags':
        template = "webclient/data/container_tags.html"
    else:
        template = "webclient/%s/%s.html" % (menu,menu)
    request.session['nav']['menu'] = menu
    
    request.session['nav']['error'] = request.REQUEST.get('error')
    
    conn = None
    try:
        conn = kwargs["conn"]
    except:
        logger.error(traceback.format_exc())
        return handlerInternalError("Connection is not available. Please contact your administrator.")
    
    url = None
    try:
        url = kwargs["url"]
    except:
        logger.error(traceback.format_exc())
    if url is None:
        url = reverse(viewname="load_template", args=[menu])
    
    #tree support
    init = {'initially_open':[], 'initially_select': None}
    for k,v in string_to_dict(request.REQUEST.get('path')).items():
        if k.lower() in ('project', 'dataset', 'image', 'screen', 'plate'):
            for i in v.split(","):
                if ":selected" in str(i) and init['initially_select'] is None:
                    init['initially_select'] = k+"-"+i.replace(":selected", "")
                else:
                    init['initially_open'].append(k+"-"+i)
                
    try:
        manager = BaseContainer(conn)
    except AttributeError, x:
        logger.error(traceback.format_exc())
        return handlerInternalError(x)
    
    form_users = None
    filter_user_id = None
    
    users = list(conn.listColleagues())
    users.sort(key=lambda x: x.getOmeName().lower())
    empty_label = "*%s (%s)" % (conn.getUser().getFullName(), conn.getUser().omeName)
    if len(users) > 0:
        if request.REQUEST.get('experimenter') is not None and len(request.REQUEST.get('experimenter'))>0: 
            form_users = UsersForm(initial={'users': users, 'empty_label':empty_label, 'menu':menu}, data=request.REQUEST.copy())
            if form_users.is_valid():
                filter_user_id = request.REQUEST.get('experimenter', None)
                request.session.get('nav')['experimenter'] = filter_user_id
                form_users = UsersForm(initial={'user':filter_user_id, 'users': users, 'empty_label':empty_label, 'menu':menu})
        else:
            if request.REQUEST.get('experimenter') == "":
                request.session.get('nav')['experimenter'] = None
            filter_user_id = request.session.get('nav')['experimenter'] is not None and request.session.get('nav')['experimenter'] or None
            if filter_user_id is not None:
                form_users = UsersForm(initial={'user':filter_user_id, 'users': users, 'empty_label':empty_label, 'menu':menu})
            else:
                form_users = UsersForm(initial={'users': users, 'empty_label':empty_label, 'menu':menu})
            
    else:
        form_users = UsersForm(initial={'users': users, 'empty_label':empty_label, 'menu':menu})
            
    form_active_group = ActiveGroupForm(initial={'activeGroup':manager.eContext['context'].groupId, 'mygroups': manager.eContext['allGroups'], 'url':url})
    
    context = {'nav':request.session['nav'], 'url':url, 'init':init, 'eContext':manager.eContext, 'form_active_group':form_active_group, 'form_users':form_users}
    
    t = template_loader.get_template(template)
    c = Context(request,context)
    logger.debug('TEMPLATE: '+template)
    return HttpResponse(t.render(c))

import featuresetInfo
@isUserConnected   
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

 





import omeroweb.searcher.searchContent as searchContent
@isUserConnected   
def contentsearch( request, iIds, dId = None, fset = None, numret = None, negId = None, **kwargs):
    # get connection
    conn = None
    try:
        conn = kwargs["conn"]        
    except:
        logger.error(traceback.format_exc())
        return handlerInternalError("Connection is not available. Please contact your administrator.")

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

@isUserConnected    
def featureCalculationConfig( request, object_type = None, object_ID = None, **kwargs):
    # get connection
    conn = None
    try:
        conn = kwargs["conn"]        
    except:
        logger.error(traceback.format_exc())
        return handlerInternalError("Connection is not available. Please contact your administrator.")

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


import pyslid.features
import pyslid.utilities
import pyslid.database.direct

import numpy
@isUserConnected  
def featureCalculation( request, object_type = None, object_ID = None, featureset = None, contentDB_config = None, **kwargs):
    # get connection
    conn = None
    try:
        conn = kwargs["conn"]        
    except:
        logger.error(traceback.format_exc())
        return handlerInternalError("Connection is not available. Please contact your administrator.")


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



