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

from omeroweb.searcher import views

urlpatterns = patterns('django.views.generic.simple',

    url( r'^$', views.index, name='searcher_index' ),
    url( r'^contentsearch/(?P<iIds>[a-zA-Z0-9\-\,\.]+)/(?:(?P<dId>[0-9]+))/(?:(?P<fset>[a-zA-Z0-9]+))/(?:(?P<numret>[0-9]+))/(?:(?P<negId>[a-zA-Z0-9\-\,\.]+)/)?$', views.contentsearch ), 
    url( r'^featureCalculationConfig/(?:(?P<object_type>[a-zA-Z0-9]+))/(?:(?P<object_ID>[0-9]+)/)?$', views.featureCalculationConfig, name="featureCalculationConfig"),  ## BK 
    url( r'^featureCalculation/(?:(?P<object_type>[a-zA-Z0-9]+))/(?:(?P<object_ID>[0-9]+))/(?:(?P<featureset>[a-zA-Z0-9]+))/(?:(?P<contentDB_config>[a-zA-Z0-9\-\,\.]+)/)?$', views.featureCalculation, name="featureCalculation"),  ## BK
    url( r'^select_czt/(?:(?P<ImageID>[0-9]+))/?$', views.select_czt ),  
##    url( r'^getSearchContentDBfromRemoteServer/?$', views.getSearchContentDBfromRemoteServer, name="getSearchContentDBfromRemoteServer"),  ## BK                       
)
