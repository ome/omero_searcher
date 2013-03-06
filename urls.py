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
import os.path

from django.conf.urls.defaults import *
from django.views.static import serve

from omeroweb.omero_searcher import views

urlpatterns = patterns('django.views.generic.simple',

    url( r'^$', views.index, name='searcher_index' ),

    # right plugin search form (equivalent to basket.html). IDs passed in query string: /?image=123&image=456 etc.
    url( r'^right_plugin_search_form/$', views.right_plugin_search_form, name='right_plugin_search_form' ),

    # main search page - submit initial search via POST from right_plugin
    url( r'^searchpage/$', views.searchpage, name="searchpage" ), 

    url( r'^contentsearch/$', views.contentsearch, name="contentsearch"), 
    url( r'^featureCalculationConfig/(?:(?P<object_type>[a-zA-Z0-9]+))/(?:(?P<object_ID>[0-9]+)/)?$', views.featureCalculationConfig, name="featureCalculationConfig"),  ## BK 
    url( r'^featureCalculation/(?:(?P<object_type>[a-zA-Z0-9]+))/(?:(?P<object_ID>[0-9]+))/(?:(?P<featureset>[a-zA-Z0-9]+))/(?:(?P<contentDB_config>[a-zA-Z0-9\-\,\.]+)/)?$', views.featureCalculation, name="featureCalculation"),  ## BK
##    url( r'^getSearchContentDBfromRemoteServer/?$', views.getSearchContentDBfromRemoteServer, name="getSearchContentDBfromRemoteServer"),  ## BK                       
)
