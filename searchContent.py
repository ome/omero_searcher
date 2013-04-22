# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Carnegie Mellon University All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt #
# 
# Version: 1.0
#
"""
@author Jennifer Bakal
"""

import numpy
import re
from numpy import zeros

import omero
import omero.scripts as scripts
import omero.constants
from omero.rtypes import *
import omero_api_Gateway_ice    # see http://tinyurl.com/icebuserror
import omero.util.script_utils as scriptUtil
from omero.config import ConfigXml

import mahotas,pyslic
import os
import pyslid.features
import pyslid.utilities
import pyslid.database.direct
import ricerca.content

from omero_searcher_config import omero_contentdb_path
pyslid.database.direct.set_contentdb_path(omero_contentdb_path)

import logging
logger = logging.getLogger('searchContent')

try:
    import cPickle as pickle
except:
    import pickle

def printToFile(printfile, str):
    f3=open(printfile,'a')
    print >>f3,str
    f3.close()


def combinePosandNeg(pos_sorted,neg_sorted):
    #reverse negative list before averaging 
    neg_sorted.reverse()

    img_avg=[]
    rank=range(len(pos_sorted))
    pos_sort_rank=zip(pos_sorted,rank)
    neg_sort_rank=zip(neg_sorted,rank)
    pos_sort_rank.sort(key=lambda img:img[0])
    neg_sort_rank.sort(key=lambda img:img[0])
    for j in range(len(pos_sort_rank)):
        if pos_sort_rank[j][0]==neg_sort_rank[j][0]:
            img_rank=(pos_sort_rank[j][0],float(pos_sort_rank[j][1]+neg_sort_rank[j][1])/2)
            img_avg.append(img_rank)

    #sort by rank  
    img_avg.sort(key=lambda img:img[1])

    avg_sorted=[]
    for img in img_avg:
        avg_sorted.append(img[0])

    return avg_sorted

def processIDs(cdb_row):
    info=cdb_row[6:11]
    ID = ''.join([str(tmp)+'.' for tmp in info])[:-1]
    return ID

def processTestSetTwo(contentDB, image_refs_dict):
    goodset = [['78615.0.0.0.0',0,[0,0,0,0,0,0,0,0,0]]]
    return goodset
             
def processTestSet(contentDB,image_refs_dict,dscale):
    #create dict with iids as keys and contentDB feature vector as value 
    iid_contentDB_dict={}
    for key in contentDB[dscale]:
        iid_contentDB_dict[key[6]]=key

    goodSet_pos = []
    for ID in image_refs_dict:
        items = ID.split('.')
        iid = long(items[0])
        pixels = long(items[1])
        channel = long(items[2])
        zslice = long(items[3])
        timepoint = long(items[4])
        rid=[]
        field=True


        feats=iid_contentDB_dict[iid][11:]
        if len(feats) ==0:
            MSG.append("feature table for "+str(iid)+"_"+featureset+" is not available: Please try with other featureset, channel, depth, or images")
            MSG.append("No retrieved result")
            return [], MSG
        else:
            goodSet_pos.append([ID, 1, feats])

    return goodSet_pos


def rankingWrapper(contentDB, image_refs_dict):
    #determine resolution to use
    keys = contentDB.keys()
    keys.remove('info')
    keys.sort()
    dscale = keys[0]

    scale = max([imgref[0] for imgref in image_refs_dict.values()])

    #find the closest scale in the dictionary to the scale of the local images
    for key in keys:
        if abs(key - scale) < abs(dscale - scale):
            dscale = key

    if not contentDB.has_key( dscale ):
       sys.exit("System error - scale not found in content database.")
    else:
       data=contentDB[dscale]

    dataset=[]
    for cdb_row in data:
        ID=processIDs(cdb_row)
        feat_vec = list(cdb_row[11:])
        dataset.append([ID,0,feat_vec])

    test_set=processTestSet(contentDB, image_refs_dict, dscale)

    alpha = -5

    #RANKING IMAGES USING RICERCA                                                                                                            
    print "Ranking images"
    normalization = 'zscore'
    [sorted_iids,sorted_scores] = ricerca.content.ranking( alpha, dataset, test_set, normalization )

    return [sorted_iids, sorted_scores, dscale]

    

def relevanceFeedback(conn, parameterMap, server, owner):
    
    def samplesToImageDict(samples):
        image_dict={}
        if len(samples)>0:
            for ID in samples:
                items=ID.split('.')
                iid=long(items[0])
                scale=pyslid.features.getScales(conn,iid,featureset,True)[0]
                image_dict[ID]=(scale,'')

        return image_dict

    MSG = []
    featureset = str(parameterMap["Feature_Set_Name"]).lower()
    # get the images IDs from list (in order) or dataset (sorted by name)
    pos_samples = parameterMap["posIDs"]

    # at this point, pos_samples includes both positive and negative IDs
    # separate the positive and negative IDs
    neg_samples = parameterMap["negIDs"]

    numRetrieve=parameterMap["numret"]
    numRetrieve=numRetrieve[0]

    pos_image_dict=samplesToImageDict(pos_samples)
    neg_image_dict=samplesToImageDict(neg_samples)

    start_did=parameterMap["Dataset_ID"]
    start_did=start_did[0]
    if start_did==0:
        did=None
    else:
        did=long(start_did)

    #get contentDB
    contentDB, message = pyslid.database.direct.retrieve(conn, featureset, did)
    if len(contentDB) == 0:
        MSG.append("contentDB for "+featureset+" is not available")

    if pos_image_dict:
        try:
            [sorted_iids_pos, sorted_scores_pos, dscale] = rankingWrapper(contentDB, pos_image_dict)
        except:
            MSG.append('ranking failed')

    if neg_image_dict:
        try:
            [sorted_iids_neg, sorted_scores_neg, dscale] = rankingWrapper(contentDB, neg_image_dict)
        except:
            MSG.append('ranking failed')

    final_result = []
    if pos_image_dict:
        if neg_image_dict: #there are both positive and negative samples
            avg_sorted = combinePosandNeg(sorted_iids_pos,sorted_iids_neg)
            final_result = avg_sorted[:min(numRetrieve,len(avg_sorted))]      
        else:                  #there are only positive samples
            final_result = sorted_iids_pos[:min(numRetrieve,len(sorted_iids_pos))]
    elif neg_image_dict:                      #there are only negative samples
        sorted_iids_neg.reverse()   #neg_sorted originally shows most like negative
        final_result = sorted_iids_neg[:min(numRetrieve,len(sorted_iids_neg))]

    final_result_refined = []
    for itm in final_result:
        ID_itm = itm.split('.')[-5:]
        IDs = ''.join([str(tmp)+'.' for tmp in ID_itm])[:-1]
        usr = 'demo_nm'
        server = 'omepslid2.compbio.cs.cmu.edu'
        final_result_refined.append([IDs, server, usr])

    if len(final_result_refined) == 0:
        MSG.append("No retrieved result")
    return final_result_refined, MSG
