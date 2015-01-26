#!/usr/bin/python
#
# Script to dynamically generate web tiles, either blending existing tiles, 
# generating from a local data source, or blending the two.
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

from osgeo import gdal, gdalnumeric, ogr
from gdalconst import *
import osr
import math
import subprocess
from PIL import Image
import cStringIO
import cgi
import os, sys
import urllib
import time
import re

###############################################################################

__doc__globalmaptiles = """
globalmaptiles.py

Global Map Tiles as defined in Tile Map Service (TMS) Profiles
==============================================================

Functions necessary for generation of global tiles used on the web.
It contains classes implementing coordinate conversions for:

  - GlobalMercator (based on EPSG:900913 = EPSG:3785)
       for Google Maps, Yahoo Maps, Bing Maps compatible tiles
  - GlobalGeodetic (based on EPSG:4326)
       for OpenLayers Base Map and Google Earth compatible tiles

More info at:

http://wiki.osgeo.org/wiki/Tile_Map_Service_Specification
http://wiki.osgeo.org/wiki/WMS_Tiling_Client_Recommendation
http://msdn.microsoft.com/en-us/library/bb259689.aspx
http://code.google.com/apis/maps/documentation/overlays.html#Google_Maps_Coordinates

Created by Klokan Petr Pridal on 2008-07-03.
Google Summer of Code 2008, project KMLForTiles for OSGEO.

In case you use this class in your product, translate it to another language
or find it usefull for your project please let me know.
My email: klokan at klokan dot cz.
I would like to know where it was used.

Class is available under the open-source GDAL license (www.gdal.org).
"""

MAXZOOMLEVEL = 32

class GlobalMercator(object):
    """
    TMS Global Mercator Profile
    ---------------------------

  Functions necessary for generation of tiles in Spherical Mercator projection,
  EPSG:900913 (EPSG:gOOglE, Google Maps Global Mercator), EPSG:3785, OSGEO:41001.

  Such tiles are compatible with Google Maps, Bing Maps, Yahoo Maps,
  UK Ordnance Survey OpenSpace API, ...
  and you can overlay them on top of base maps of those web mapping applications.

    Pixel and tile coordinates are in TMS notation (origin [0,0] in bottom-left).

    What coordinate conversions do we need for TMS Global Mercator tiles::

         LatLon      <->       Meters      <->     Pixels    <->       Tile

     WGS84 coordinates   Spherical Mercator  Pixels in pyramid  Tiles in pyramid
         lat/lon            XY in metres     XY pixels Z zoom      XYZ from TMS
        EPSG:4326           EPSG:900913
         .----.              ---------               --                TMS
        /      \     <->     |       |     <->     /----/    <->      Google
        \      /             |       |           /--------/          QuadTree
         -----               ---------         /------------/
       KML, public         WebMapService         Web Clients      TileMapService

    What is the coordinate extent of Earth in EPSG:900913?

      [-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244]
      Constant 20037508.342789244 comes from the circumference of the Earth in meters,
      which is 40 thousand kilometers, the coordinate origin is in the middle of extent.
      In fact you can calculate the constant as: 2 * math.pi * 6378137 / 2.0
      $ echo 180 85 | gdaltransform -s_srs EPSG:4326 -t_srs EPSG:900913
      Polar areas with abs(latitude) bigger then 85.05112878 are clipped off.

    What are zoom level constants (pixels/meter) for pyramid with EPSG:900913?

      whole region is on top of pyramid (zoom=0) covered by 256x256 pixels tile,
      every lower zoom level resolution is always divided by two
      initialResolution = 20037508.342789244 * 2 / 256 = 156543.03392804062

    What is the difference between TMS and Google Maps/QuadTree tile name convention?

      The tile raster itself is the same (equal extent, projection, pixel size),
      there is just different identification of the same raster tile.
      Tiles in TMS are counted from [0,0] in the bottom-left corner, id is XYZ.
      Google placed the origin [0,0] to the top-left corner, reference is XYZ.
      Microsoft is referencing tiles by a QuadTree name, defined on the website:
      http://msdn2.microsoft.com/en-us/library/bb259689.aspx

    The lat/lon coordinates are using WGS84 datum, yeh?

      Yes, all lat/lon we are mentioning should use WGS84 Geodetic Datum.
      Well, the web clients like Google Maps are projecting those coordinates by
      Spherical Mercator, so in fact lat/lon coordinates on sphere are treated as if
      the were on the WGS84 ellipsoid.

      From MSDN documentation:
      To simplify the calculations, we use the spherical form of projection, not
      the ellipsoidal form. Since the projection is used only for map display,
      and not for displaying numeric coordinates, we don't need the extra precision
      of an ellipsoidal projection. The spherical projection causes approximately
      0.33 percent scale distortion in the Y direction, which is not visually noticable.

    How do I create a raster in EPSG:900913 and convert coordinates with PROJ.4?

      You can use standard GIS tools like gdalwarp, cs2cs or gdaltransform.
      All of the tools supports -t_srs 'epsg:900913'.

      For other GIS programs check the exact definition of the projection:
      More info at http://spatialreference.org/ref/user/google-projection/
      The same projection is degined as EPSG:3785. WKT definition is in the official
      EPSG database.

      Proj4 Text:
        +proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0
        +k=1.0 +units=m +nadgrids=@null +no_defs

      Human readable WKT format of EPGS:900913:
         PROJCS["Google Maps Global Mercator",
             GEOGCS["WGS 84",
                 DATUM["WGS_1984",
                     SPHEROID["WGS 84",6378137,298.257223563,
                         AUTHORITY["EPSG","7030"]],
                     AUTHORITY["EPSG","6326"]],
                 PRIMEM["Greenwich",0],
                 UNIT["degree",0.0174532925199433],
                 AUTHORITY["EPSG","4326"]],
             PROJECTION["Mercator_1SP"],
             PARAMETER["central_meridian",0],
             PARAMETER["scale_factor",1],
             PARAMETER["false_easting",0],
             PARAMETER["false_northing",0],
             UNIT["metre",1,
                 AUTHORITY["EPSG","9001"]]]
    """

    def __init__(self, tileSize=256):
        "Initialize the TMS Global Mercator pyramid"
        self.tileSize = tileSize
        self.initialResolution = 2 * math.pi * 6378137 / self.tileSize
        # 156543.03392804062 for tileSize 256 pixels
        self.originShift = 2 * math.pi * 6378137 / 2.0
        # 20037508.342789244

    def LatLonToMeters(self, lat, lon ):
        "Converts given lat/lon in WGS84 Datum to XY in Spherical Mercator EPSG:900913"

        mx = lon * self.originShift / 180.0
        my = math.log( math.tan((90 + lat) * math.pi / 360.0 )) / (math.pi / 180.0)

        my = my * self.originShift / 180.0
        return mx, my

    def MetersToLatLon(self, mx, my ):
        "Converts XY point from Spherical Mercator EPSG:900913 to lat/lon in WGS84 Datum"

        lon = (mx / self.originShift) * 180.0
        lat = (my / self.originShift) * 180.0

        lat = 180 / math.pi * (2 * math.atan( math.exp( lat * math.pi / 180.0)) - math.pi / 2.0)
        return lat, lon

    def PixelsToMeters(self, px, py, zoom):
        "Converts pixel coordinates in given zoom level of pyramid to EPSG:900913"

        res = self.Resolution( zoom )
        mx = px * res - self.originShift
        my = py * res - self.originShift
        return mx, my

    def MetersToPixels(self, mx, my, zoom):
        "Converts EPSG:900913 to pyramid pixel coordinates in given zoom level"

        res = self.Resolution( zoom )
        px = (mx + self.originShift) / res
        py = (my + self.originShift) / res
        return px, py

    def PixelsToTile(self, px, py):
        "Returns a tile covering region in given pixel coordinates"

        tx = int( math.ceil( px / float(self.tileSize) ) - 1 )
        ty = int( math.ceil( py / float(self.tileSize) ) - 1 )
        return tx, ty

    def PixelsToRaster(self, px, py, zoom):
        "Move the origin of pixel coordinates to top-left corner"

        mapSize = self.tileSize << zoom
        return px, mapSize - py

    def MetersToTile(self, mx, my, zoom):
        "Returns tile for given mercator coordinates"

        px, py = self.MetersToPixels( mx, my, zoom)
        return self.PixelsToTile( px, py)

    def TileBounds(self, tx, ty, zoom):
        "Returns bounds of the given tile in EPSG:900913 coordinates"

        minx, miny = self.PixelsToMeters( tx*self.tileSize, ty*self.tileSize, zoom )
        maxx, maxy = self.PixelsToMeters( (tx+1)*self.tileSize, (ty+1)*self.tileSize, zoom )
        return ( minx, miny, maxx, maxy )

    def TileLatLonBounds(self, tx, ty, zoom ):
        "Returns bounds of the given tile in latutude/longitude using WGS84 datum"

        bounds = self.TileBounds( tx, ty, zoom)
        minLat, minLon = self.MetersToLatLon(bounds[0], bounds[1])
        maxLat, maxLon = self.MetersToLatLon(bounds[2], bounds[3])

        return ( minLat, minLon, maxLat, maxLon )

    def Resolution(self, zoom ):
        "Resolution (meters/pixel) for given zoom level (measured at Equator)"

        # return (2 * math.pi * 6378137) / (self.tileSize * 2**zoom)
        return self.initialResolution / (2**zoom)

    def ZoomForPixelSize(self, pixelSize ):
        "Maximal scaledown zoom of the pyramid closest to the pixelSize."

        for i in range(MAXZOOMLEVEL):
            if pixelSize > self.Resolution(i):
                if i!=0:
                    return i-1
                else:
                    return 0 # We don't want to scale up

    def GoogleTile(self, tx, ty, zoom):
        "Converts TMS tile coordinates to Google Tile coordinates"

        # coordinate origin is moved from bottom-left to top-left corner of the extent
        return tx, (2**zoom - 1) - ty

    def QuadTree(self, tx, ty, zoom ):
        "Converts TMS tile coordinates to Microsoft QuadTree"

        quadKey = ""
        ty = (2**zoom - 1) - ty
        for i in range(zoom, 0, -1):
            digit = 0
            mask = 1 << (i-1)
            if (tx & mask) != 0:
                digit += 1
            if (ty & mask) != 0:
                digit += 2
            quadKey += str(digit)

        return quadKey

###############################################################################

class GenerateDynamicTiles(object):

    # -------------------------------------------------------------------------
    def error(self, msg, details = "" ):
        """Print an error message and stop the processing"""

        if details:
            self.parser.error(msg + "\n\n" + details)
        else:
            self.parser.error(msg)
      
    # -------------------------------------------------------------------------
    def imageToArray(self,i):
        """
        Converts a Python Imaging Library array to a 
        gdalnumeric image.
        """
        a=gdalnumeric.fromstring(i.tostring(),'b')
        a.shape=i.im.size[1], i.im.size[0]
        return a

    # -------------------------------------------------------------------------
    def arrayToImage(self,a):
        """
        Converts a gdalnumeric array to a 
        Python Imaging Library Image.
        """
        i=Image.fromstring('L',(a.shape[1],a.shape[0]),
            (a.astype('b')).tostring())
        return i

    # -------------------------------------------------------------------------
    def parse_custom_querystring(self, querystring, key_str, default_val ):
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

    def __init__(self,querystring,fs):
        """Constructor function - initialization"""

        self.tilesize = 256
        self.tileext = 'png'
        
        # Get the arguments from the query string
        self.url = self.parse_custom_querystring(querystring,'url','')
        self.clrfile = self.parse_custom_querystring(querystring,'clrfile','')
        self.bgurl = self.parse_custom_querystring(querystring,'bgurl','')
        self.shpfile = self.parse_custom_querystring(querystring,'shpfile','')
            
        if 'zxy=' in querystring:
            self.zxy = fs['zxy'].value
        else:
            self.zxy = '0/0/0'
         
        if 'cachedir' in querystring:
            self.cachedir = fs['cachedir'].value
        else:
            self.cachedir = ''
            
        if 'resample' in querystring:
            self.resample = fs['resample'].value
        else:
            self.resample = 'near'
            
        if 'blend' in querystring:
            self.blend = fs['blend'].value
        else:
            self.blend = '0.5'
             
        if 'outsideMask' in querystring:
            self.outsideMask = True
        else:
            self.outsideMask = False
        
        self.profile = 'mercator'
        
        self.tz, self.tx, self.ty = self.zxy.split('/')
        
        if self.url.find('invY') > -1:
            self.invert_y = True
        else:
            self.invert_y = False
            
        # Get geospatial information about the tile
        if self.profile == 'mercator':

            self.mercator = GlobalMercator() # from globalmaptiles.py
            
            # Function which generates SWNE in LatLong for given tile
            self.tileswne = self.mercator.TileLatLonBounds
            
    # -------------------------------------------------------------------------
    def generate_tiles(self):
        """
        Function to generate the dynamic tiles (either merging multiple web tile 
        sources and/or extracting data from a local GIS data source
        """ 
        tz = int(self.tz)
        tx = int(self.tx)
        ty = int(self.ty)
        
        # For Debugging Purposes (enter the text in the Link field of the network link into a web browser)
        #print 'Content-Type: text/html\n'
        
        # In case of inverted y coordinate
        if self.invert_y:
            ty2 = ty
        else:
            if type(ty) is int:
                ty2 = (2**tz)-ty-1
            else:
                ty2 = ty
 
        # Tile name used if tile is cached
        tilefilename = os.path.join('dynamic_tiles',self.cachedir, str(tz), str(tx), "%s.%s" % (ty, self.tileext))
        
        if not os.path.exists(tilefilename):
            south, west, north, east = self.tileswne(tx, ty, tz)

            # Generate the temp file names (only required temporary files for the requested configuration will be created)
            import tempfile
            tempfilename_web = tempfile.mktemp('-generate_dynamic_tiles_web.tif')
            tempfilename_shp = tempfile.mktemp('-generate_dynamic_tiles.shp')
            tempfilename = tempfile.mktemp('-generate_dynamic_tiles.tif')
            tempfilename2 = tempfile.mktemp('-generate_dynamic_tiles2.tif')
            tempfilename3 = tempfile.mktemp('-generate_dynamic_tiles3.tif')
            
            raster_url = self.url
            
            if raster_url.find('{$z}') <= -1:
                if raster_url.find('.pyr') >= 0:
                    file = open(raster_url,'r')
                    done = False
                    while done == False:
                        zoom, fname = file.readline().split(' ')
                        if tz <= int(zoom):
                            done = True
                    
                    raster_url = raster_url.replace(os.path.basename(raster_url),fname.strip())
                    file.close()
                
                command = 'gdalwarp -r ' + self.resample + ' -dstalpha -ovr AUTO -overwrite -t_srs "+proj=latlong +datum=wgs84 +nodefs" -ts ' + str(self.tilesize) + ' ' + str(self.tilesize) + ' -te ' + str(west) + ' ' + str(south) + ' ' + str(east) + ' ' + str(north) + ' "' + raster_url + '" ' + tempfilename
                subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb'))
            else:
                raster_url = raster_url.replace('{$x}', str(tx))
                raster_url = raster_url.replace('{$y}', str(ty2))
                raster_url = raster_url.replace('{$invY}', str(ty2))
                raster_url = raster_url.replace('{$z}', str(tz))
                urllib.urlretrieve(raster_url,tempfilename_web)
                im = Image.open(tempfilename_web).convert('RGBA')
                im.save(tempfilename_web, "PNG")
                command = 'gdal_translate -a_srs "+proj=latlong +datum=wgs84 +nodefs" -a_ullr ' + str(west) + ' ' + str(north) + ' ' + str(east) + ' ' + str(south) + ' "' + tempfilename_web + '" ' + tempfilename
                subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb')) 
               
            if self.clrfile != '':
                mask_i = gdalnumeric.LoadFile(tempfilename)
                mask_i = (mask_i[1,:,:] != 0)
                command = 'gdaldem color-relief -alpha ' + tempfilename + ' "' + self.clrfile + '" ' + tempfilename2
                subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb'))
            else:
                tempfilename2 = tempfilename
                mask_i = gdalnumeric.LoadFile(tempfilename2)
                mask_i = (mask_i[3,:,:] != 0)
                
            if self.shpfile != '':
                shapefilename = self.shpfile
                path, file = os.path.split(shapefilename)
                layername = file.replace('.shp','')
                command = 'gdal_rasterize -b 4 -burn 0 -l ' + layername + ' "' + shapefilename + '" ' + tempfilename2
                subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb'))
                
            if self.bgurl != '':
            
                bgurl_url = self.bgurl
                
                if bgurl_url.find('{$z}') <= -1:
                    if bgurl_url.find('.pyr') >= 0:
                        file = open(bgurl_url,'r')
                        done = False
                        while done == False:
                            zoom, fname = file.readline().split(' ')
                            if tz <= int(zoom):
                                done = True
                            
                        bgurl_url = bgurl_url.replace(os.path.basename(bgurl_url),fname.strip())
                        file.close()
                    
                    command = 'gdalwarp  -r ' + self.resample + ' -ovr AUTO -overwrite -t_srs "+proj=latlong +datum=wgs84 +nodefs" -ts ' + str(self.tilesize) + ' ' + str(self.tilesize) + ' -te ' + str(west) + ' ' + str(south) + ' ' + str(east) + ' ' + str(north) + ' "' + bgurl_url + '" ' + tempfilename3
                    subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb'))
                else:
                    bgurl_url = bgurl_url.replace('{$x}', str(tx))
                    bgurl_url = bgurl_url.replace('{$y}', str(ty2))
                    bgurl_url = bgurl_url.replace('{$invY}', str(ty2))
                    bgurl_url = bgurl_url.replace('{$z}', str(tz))
                        
                    urllib.urlretrieve(bgurl_url,tempfilename_web)
                    im = Image.open(tempfilename_web).convert('RGBA')
                    im.save(tempfilename_web, "PNG")
                    command = 'gdal_translate -a_srs "+proj=latlong +datum=wgs84 +nodefs" -a_ullr ' + str(west) + ' ' + str(north) + ' ' + str(east) + ' ' + str(south) + ' "' + tempfilename_web + '" ' + tempfilename3
                    subprocess.call(command, shell=True, stdout=open(os.devnull, 'wb')) 
            
                dem_image = Image.open(tempfilename2).convert('RGBA')
                shaded_relief = Image.open(tempfilename3).convert('RGBA')
                
                im = Image.blend(dem_image, shaded_relief, float(self.blend))
            else:
                im = Image.open(tempfilename2)
            
            r,g,b,a2 = im.split()
            mask = gdalnumeric.LoadFile(tempfilename2)
            mask = mask[3,:,:]
            if self.outsideMask == True:
                mask = mask_i * (mask == 0) * 255
            else:
                mask = mask_i * (mask != 0) * 255
            a = self.arrayToImage(mask)
            im = Image.merge("RGBA", (r,g,b,a))

            #print "%.8f" % (time.time()-start)            

            # If specified, save a copy of the cached image
            if self.cachedir != '':
                if not os.path.exists(os.path.dirname(tilefilename)):
                   os.makedirs(os.path.dirname(tilefilename))
                im.save(tilefilename, "PNG")
            
            # and return the image
            f = cStringIO.StringIO()
            im.save(f, "PNG")
            f.seek(0)
            print "Content-type: image/png\n"
            print f.read()
            
            # Remove temporary files
            if os.path.isfile(tempfilename):
                os.unlink(tempfilename)
            if os.path.isfile(tempfilename2):
                os.unlink(tempfilename2)
            if os.path.isfile(tempfilename3):
                os.unlink(tempfilename3)
            if os.path.isfile(tempfilename_web):
                os.unlink(tempfilename_web) 
            if os.path.isfile(tempfilename_shp):
                os.unlink(tempfilename_shp)  
            #print "%.8f" % (time.time()-start)
        else:
        # else return the cached file
            im = Image.open(tilefilename)
            f = cStringIO.StringIO()
            im.save(f, "PNG")
            f.seek(0)
            print "Content-type: image/png\n"
            print f.read()
            
###############################################################################

if __name__=='__main__':

    fs = cgi.FieldStorage()  
    querystring = os.environ.get("QUERY_STRING", "No Query String in url")

    dynamic_tiles = GenerateDynamicTiles(querystring,fs)
    dynamic_tiles.generate_tiles()
   
    
