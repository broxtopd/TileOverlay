#!/usr/bin/python
#
# Top level script to either display web tiles or a local gdal-supported dataset in Google Earth.
# This script should be run using a web server.
#
###############################################################################
# Copyright (c) 2015, Patrick Broxton
# 
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the "Software"),
#  to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense,
#  and/or sell copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following conditions:
# 
#  The above copyright notice and this permission notice shall be included
#  in all copies or substantial portions of the Software.
# 
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#  THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
###############################################################################

import os, sys
import cgi
import subprocess
from random import randint
import re
import urllib
import kml_for_tiles
 
################################ MODIFY THESE ################################

# URL of this script (which generates the KML for displaying the imagery)
kmlscriptloc = 'http://localhost:8080/cgi-bin/generate_kml.py'
# URL of the dynamic tile generater script (if accessing a local GIS dataset or blending two datasources
tilescriptloc = 'http://localhost:8090/cgi-bin/generate_dynamic_tiles.py'
# URL of a transparent image (if a corresponding tile is missing
transparentpng = 'http://localhost:8080/static/transparent.png'

##############################################################################

# For Debugging Purposes (enter the text in the Link field of the network link into a web browser)
#print 'Content-Type: text/html\n'
print 'Content-Type: text/xml\n'
#print 'Content-Type: application/vnd.google-earth.kml+xml\n'

# -------------------------------------------------------------------------
def parse_custom_querystring(querystring, key_str, default_val ):
    """
    Function to parse a querystring where elements can contain ampersands (key string ends with a semicolon)
    Search for a semicolon followed by an ampersand to end the key_str (in case the string itself contains ampersands)   
    """      
    if key_str in querystring:
        spos = querystring.index(key_str)+len(key_str)+1
        if ';&' in querystring:
            epos = querystring.index(';&')
            epos = [m.start() for m in re.finditer(';&', querystring)]
            if type(epos) != int:
                epos = [i for i in epos if i >= spos]
                if len(epos) > 0:
                    epos = int(epos[0])
                else:
                    epos = 1
            if epos > spos:
                key_val = querystring[spos:epos]
            else:
                key_val = querystring[spos:]
        else:
            key_val = querystring[spos:]
            
    else:
        key_val = default_val;
    
    # Decode all of the key_string characters (in case they are passed in as encoded characters)
    key_val = urllib.unquote(key_val).encode('utf8')
    # key_val = key_val.replace('%20',' ')
    # key_val = key_val.replace('%7B','{')
    # key_val = key_val.replace('%7D','}')
    # For windows, decode the backslash as a forward slash
    key_val = key_val.replace('%5C','/')
    # If a semicolon is left in the key string (i.e. it comes at the end of the querysting), remove it
    key_val = key_val.replace(';','')
    # Fix a problem where one of the forward slashes is dropped
    if key_val.find('http:/') > -1:
        if key_val.find('http://') <= -1:
            key_val = key_val.replace('http:/','http://')
    return key_val

# -------------------------------------------------------------------------

# Get the entire query string as well as the parsed version, as in some cases, cgi fieldstorage is fine, but in others, we need a custom function (above) to read a key string (if it may contain ampersands) 
fs = cgi.FieldStorage()  
querystring = os.environ.get("QUERY_STRING", "No Query String")

# Get the URL and zoom (the profile just refers to how coordinates are handled within the script)
url = parse_custom_querystring(querystring,'url','')

if 'zoom=' in querystring:
    zoom = fs['zoom'].value
else:
    zoom = '1-16';

if 'ullr=' in querystring:
    ullr = fs['ullr'].value
else:
    ullr = '-180_90_180_-89.9'; 

profile = 'mercator'

# If already a web tile format ({$z},{$x},{$y} are defined), generate kml for the top level tiles for the region defined by ullr in the querystring (if applicable)
if ('{$z}' in url):
    webTiles = 1
        
    # Bypass and enter the kml generation script if being called recursively
    if 'zxy=' in querystring:
        zxy = fs['zxy'].value
        tile_kml = kml_for_tiles.KMLForTiles(kmlscriptloc,tilescriptloc,transparentpng,querystring,fs,zxy,webTiles)
        print tile_kml.generate_tiles()
    else:
    # Else if called for the first time, append all children to root kml, and return the result
        tminz, tmaxz = zoom.split('-')
        ulx, uly, lrx, lry = ullr.split('_')
        tminz = int(tminz)
            
        if profile == 'mercator':
            tile_math = kml_for_tiles.GlobalMercator()
            ominx, omaxy = tile_math.LatLonToMeters(float(uly),float(ulx))
            omaxx, ominy = tile_math.LatLonToMeters(float(lry),float(lrx))
            
            # Generate table with min max tile coordinates for all zoomlevels
            tminmax = list(range(0,32))
            for tz in range(0, 32):
                tminx, tminy = tile_math.MetersToTile( ominx, ominy, tz )
                tmaxx, tmaxy = tile_math.MetersToTile( omaxx, omaxy, tz )
                # crop tiles extending world limits (+-180,+-90)
                tminx, tminy = max(0, tminx), max(0, tminy)
                tmaxx, tmaxy = min(2**tz-1, tmaxx), min(2**tz-1, tmaxy)
                tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)
            
        children = []
        xmin, ymin, xmax, ymax = tminmax[tminz]
        for x in range(xmin, xmax+1):
            for y in range(ymin, ymax+1):
                children.append( [ x, y, tminz ] ) 
                
        tile_kml = kml_for_tiles.KMLForTiles(kmlscriptloc,tilescriptloc,transparentpng,querystring,fs,'0/0/0',webTiles)
        # Generate Root KML
        print tile_kml.generate_kml( None, None, None, children)

else:
# Else, open the raster data source, and figure out its extents and appropriate top level zoom
    from osgeo import gdal
    from gdalconst import *

    webTiles = 0
    checkStatus = False

    # Bypass and enter the kml generation script if being called recursively
    if 'zxy=' in querystring:
        zxy = fs['zxy'].value
        tile_kml = kml_for_tiles.KMLForTiles(kmlscriptloc,tilescriptloc,transparentpng,querystring,fs,zxy,webTiles)
        print tile_kml.generate_tiles()
    else:
        # Else if called for the first time, get the raster extents (warping if necessary), and then generate root kml structure as above
        gdal.AllRegister()
        
        import tempfile
        tempfilename = tempfile.mktemp('-TileOverlay.vrt')
        
        # In some cases, a special file should be used to open different maps with different zoom levels.  Here, only open the file for the largest zoom levels
        if url.find('.pyr') >= 0:
            file = open(url,'r')
            zoom, raster_url = file.readline().split(' ')
            raster_url = url.replace(os.path.basename(url),raster_url.strip())
            file.close()
        else:
            raster_url = url
        
        # Warp to WGS84 to ensure that dataset bounds are read correctly
        command = 'gdalwarp -t_srs "+proj=latlong +datum=wgs84 +nodefs" -of vrt "' + raster_url + '" ' + tempfilename
        subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb'))
        
        ds = gdal.Open(tempfilename, GA_ReadOnly)
        if ds is None:
            print 'Content-Type: text/html\n'
            print 'Could not open raster'
            sys.exit(1)
            
        tilesize = 256
        rows = ds.RasterYSize
        cols = ds.RasterXSize
        transform = ds.GetGeoTransform()
        ulx = transform[0]
        uly = transform[3]
        pixelWidth = transform[1]
        pixelHeight = transform[5]
        lrx = ulx + (cols * pixelWidth)
        lry = uly + (rows * pixelHeight)
        
        del ds
        os.unlink(tempfilename)

        uly = min(uly,89.9)
        lry = max(lry,-89.9)
        ulx = max(ulx,-180)
        lrx - min(lrx,180)

        ullr = str(ulx) + '_' + str(uly) + '_' + str(lrx) + '_' + str(lry)
            
        if profile == 'mercator':
            tile_math = kml_for_tiles.GlobalMercator()
            ominx, omaxy = tile_math.LatLonToMeters(float(uly),float(ulx))
            omaxx, ominy = tile_math.LatLonToMeters(float(lry),float(lrx))
            pixelWidth = (omaxx - ominx) / cols
            
            # Generate table with min max tile coordinates for all zoomlevels
            tminmax = list(range(0,32))
            for tz in range(0, 32):
                tminx, tminy = tile_math.MetersToTile( ominx, ominy, tz )
                tmaxx, tmaxy = tile_math.MetersToTile( omaxx, omaxy, tz )
                # crop tiles extending world limits (+-180,+-90)
                tminx, tminy = max(0, tminx), max(0, tminy)
                tmaxx, tmaxy = min(2**tz-1, tmaxx), min(2**tz-1, tmaxy)
                tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)
            
        tminz = tile_math.ZoomForPixelSize( pixelWidth * max( cols, rows) / float(tilesize) )
        
        if 'zoom=' in querystring:
            zoom = fs['zoom'].value
        else:
            zoom = str(tminz) + '-32'
        
        children = []
        xmin, ymin, xmax, ymax = tminmax[tminz]
        for x in range(xmin, xmax+1):
            for y in range(ymin, ymax+1):
                children.append( [ x, y, tminz ] ) 
                
        tile_kml = kml_for_tiles.KMLForTiles(kmlscriptloc,tilescriptloc,transparentpng,querystring,fs,'0/0/0',webTiles)
        # Generate Root KML
        print tile_kml.generate_kml( None, None, None, children)
