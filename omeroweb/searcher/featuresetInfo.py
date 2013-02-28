#
# Copyright (C) 2012 Carnegie Melon University All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt #
# 
# Version: 1.0
#
class FEATURESET:
    name=''     # featureset name
    forEveryChannel=True # True if thise featureset is applicable for every channel
    channel=list() # if 'forEveryChannel' is False, then you can set this variable of channel indices about which channel is about this feature set


## ADMIN user needs to set up the following part
## FINALLY, 'SETS' variable needs to be filled.
SET1 = FEATURESET()
SET1.name = 'slf34'
SET1.forEveryChannel = False
SET1.channel = [0]

SET2 = FEATURESET()
SET2.name = 'slf33'
SET2.forEveryChannel = True
SET2.channel = [0]

SETS = []
SETS.append(SET1)
SETS.append(SET2)

import pyslid.features

def getInfo(conn, iid):
    class RESULT:
        featuersetName=''     # featureset name
        channels=list() # if 'forEveryChannel' is False, then you can set this variable about which channel is about this feature set
        sizeZ=0
        sizeT=0
        sizeC=0
        
    
    results = []

    
    try:
        for SET in SETS:
            result = RESULT()
            [answer, tag] = pyslid.features.has(conn, long(iid), SET.name)
            if answer:
                result.featuresetName = SET.name
                image = conn.getObject("Image",long(iid))
                if SET.forEveryChannel:
                    result.sizeZ = image.getSizeZ()
                    result.sizeT = image.getSizeT()
                    result.sizeC = image.getSizeC()
                    result.channels = [c.getName() for c in image.getChannels()]
                else:
                    result.sizeZ = image.getSizeZ()
                    result.sizeT = image.getSizeT()
                    result.sizeC = len(SET.channel)
                    tmp = image.getChannels()
                    tmp2=[]
                    for chan in SET.channel:
                        tmp2.append(str(tmp[chan].getName()))
                    result.channels = tmp2
                    
                results.append(result)

        return results

    except:
##        result = RESULT()
##        results.append(result)
        return []
