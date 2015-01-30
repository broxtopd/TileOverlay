#!/usr/bin/python
#
# Script to dynamically create kml structure for displaying web tiles
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
#
# Portions of this script are modified from Klokan Petr Pridal's gdal2tiles.py
# script
#
import math
import urllib
import urllib2
from urlparse import urlparse
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

class KMLForTiles(object):

    # -------------------------------------------------------------------------
    def error(self, msg, details = "" ):
        """Print an error message and stop the processing"""

        if details:
            self.parser.error(msg + "\n\n" + details)
        else:
            self.parser.error(msg)

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
    def __init__(self,kmlscriptloc,tilescriptloc,transparentpng,querystring,fs,zxy,webTiles):
        """Constructor function - initialization"""
        
        self.tilesize = 256

        self.querystring = querystring
        self.kmlscriptloc = kmlscriptloc
        self.tilescriptloc = tilescriptloc
        self.transparentpng = transparentpng
        self.webTiles = webTiles
        self.zxy = zxy

        # Get the arguments from the query string
        
        self.url = self.parse_custom_querystring(querystring,'url','')
        
        if 'zoom=' in querystring:
            self.zoom = fs['zoom'].value
        else:
            self.zoom = '1-16';
            
        if 'checkStatus' in querystring:
            self.checkStatus = True
        else:
            self.checkStatus = False

        if 'ullr=' in querystring:
            self.ullr = fs['ullr'].value
        else:
            self.ullr = '-180_90_180_-89.9';
            
        self.profile = 'mercator';
            
        if 'bgurl=' in querystring:
            self.bgurl = fs['bgurl'].value
            self.bgurl = self.bgurl.replace('%20',' ')
            self.bgurl = self.bgurl.replace('%5C','/')
        else:
            self.bgurl = '';
                
        if 'shpfile=' in querystring:
            self.shpfile = fs['shpfile'].value
            self.shpfile = self.shpfile.replace('%20',' ')
            self.shpfile = self.shpfile.replace('%5C','/')
        else:
            self.shpfile = '';
        
        # In case of inverted y coordinate
        url = urllib.unquote(self.url).decode('utf8')
        if url.find('invY') > -1:
            self.invert_y = True
        else:
            self.invert_y = False

        # Get tile coordinates, zoom levels, and map bounds
        self.tz, self.tx, self.ty = self.zxy.split('/')
        self.minzoom, self.maxzoom = self.zoom.split('-')
        ulx, uly, lrx, lry = self.ullr.split('_')
        
        # Remove zxy from the query string (it will be added back in with updated values)
        zxy_strip = '&zxy=' + self.parse_custom_querystring(querystring,'zxy','')
        self.querystring = self.querystring.replace(zxy_strip,'')
        
        # Get geospatial information about the tile
        if self.profile == 'mercator':

            self.mercator = GlobalMercator() # from globalmaptiles.py

            self.ominx, self.omaxy = self.mercator.LatLonToMeters(float(uly),float(ulx))
            self.omaxx, self.ominy = self.mercator.LatLonToMeters(float(lry),float(lrx))

            # Function which generates SWNE in LatLong for given tile
            self.tileswne = self.mercator.TileLatLonBounds

            # Generate table with min max tile coordinates for all zoomlevels
            self.tminmax = list(range(0,32))
            for tz in range(0, 32):
                tminx, tminy = self.mercator.MetersToTile( self.ominx, self.ominy, tz )
                tmaxx, tmaxy = self.mercator.MetersToTile( self.omaxx, self.omaxy, tz )
                # crop tiles extending world limits (+-180,+-90)
                tminx, tminy = max(0, tminx), max(0, tminy)
                tmaxx, tmaxy = min(2**tz-1, tmaxx), min(2**tz-1, tmaxy)
                self.tminmax[tz] = (tminx, tminy, tmaxx, tmaxy)

    # -------------------------------------------------------------------------
    def generate_tiles(self):
        """
        Figure out which tiles are underneath the current tile
        """
        tz = int(self.tz)
        tx = int(self.tx)
        ty = int(self.ty)
        maxzoom = int(self.maxzoom)

        tminx, tminy, tmaxx, tmaxy = self.tminmax[tz]

        children = []
        # Read the tiles and write them to query window
        for y in range(2*ty,2*ty+2):
            for x in range(2*tx,2*tx+2):
                if tz < maxzoom:
                    minx, miny, maxx, maxy = self.tminmax[tz+1]
                    if x >= minx and x <= maxx and y >= miny and y <= maxy:
                        children.append( [x, y, tz+1] )
                        
        # Create a KML file for this tile.
        return self.generate_kml( tx, ty, tz, children )
        


    # -------------------------------------------------------------------------
    def generate_kml(self, tx, ty, tz, children = [], **args ):
        """
        Template for the KML. Returns filled string.
        """

        if self.invert_y:
            ty2 = ty
        else:
            if type(ty) is int:
                ty2 = (2**tz)-ty-1
            else:
                ty2 = ty
        
        href_str = self.kmlscriptloc
        querystring = self.querystring.replace('&', '&amp;')
        minzoom = int(self.minzoom)
        dynamictilescript = False
        
        if self.webTiles == 1:
            if self.bgurl != '' or self.shpfile != '':
                # if blending the 2 web tile sources, link to dynamic tile script
                args['icon_url'] = self.tilescriptloc + '?' + querystring + '&amp;zxy=' + self.zxy
                dynamictilescript = True
            else:
                # else, link to the address of the web tile (can also be from a local data source)
                icon_url = urllib.unquote(self.url).decode('utf8')
                icon_url = icon_url.replace('{$x}', str(tx))
                icon_url = icon_url.replace('{$y}', str(ty2))
                icon_url = icon_url.replace('{$invY}', str(ty2))
                icon_url = icon_url.replace('{$z}', str(tz))
        
                icon_url = icon_url.replace('&', '&amp;')
                # If specified, check if a tile exists, otherwise show a transparent png
                if self.checkStatus == True:
                    try:
                        f = urllib2.urlopen(urllib2.Request(icon_url.replace('&amp;', '&')))
                        args['icon_url'] = icon_url
                    except:
                        args['icon_url'] = self.transparentpng
                else:
                    args['icon_url'] = icon_url
        else:
            # If instead a local GIS data source, link to dynamic tile script
            args['icon_url'] = self.tilescriptloc + '?' + querystring + '&amp;zxy=' + self.zxy    
            dynamictilescript = True
        
        
        # Load Arguments for the KML string
        if 'tilesize' not in args:
            args['tilesize'] = self.tilesize
        if 'minlodpixels' not in args:
            args['minlodpixels'] = int( args['tilesize'] / 2 ) # / 2.56) # default 128
        if 'maxlodpixels' not in args:
            #args['maxlodpixels'] = int( args['tilesize'] * 8 ) # 1.7) # default 2048 (used to be -1)
            args['maxlodpixels'] = -1
        if children == []:
            args['maxlodpixels'] = -1
        if tz == minzoom:
            args['minlodpixels'] = -1
        if tx==None:
            tilekml = False
            args['title'] = 'Root'
        else:
            tilekml = True
            args['title'] = "%d/%d/%d.kml" % (tz, tx, ty)
            args['south'], args['west'], args['north'], args['east'] = self.tileswne(tx, ty, tz)
        if tx == 0:
            args['drawOrder'] = 2 * tz + 1
        elif tx != None:
            args['drawOrder'] = 2 * tz
        else:
            args['drawOrder'] = 0

        s = """<?xml version="1.0" encoding="utf-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        <name>%(title)s</name>
        <description></description>
        <Style>
          <ListStyle id="hideChildren">
            <listItemType>checkHideChildren</listItemType>
          </ListStyle>
        </Style>""" % args
        if tilekml:
            s += """
        <Region>
          <LatLonAltBox>
            <north>%(north).14f</north>
            <south>%(south).14f</south>
            <east>%(east).14f</east>
            <west>%(west).14f</west>
          </LatLonAltBox>
          <Lod>
            <minLodPixels>%(minlodpixels)d</minLodPixels>
            <maxLodPixels>%(maxlodpixels)d</maxLodPixels>
          </Lod>
        </Region>
        <GroundOverlay>
          <drawOrder>%(drawOrder)d</drawOrder>
          <Icon>
            <href>%(icon_url)s</href>
          </Icon>
          <LatLonBox>
            <north>%(north).14f</north>
            <south>%(south).14f</south>
            <east>%(east).14f</east>
            <west>%(west).14f</west>
          </LatLonBox>
        </GroundOverlay>
    """ % args

        # If the dynamic tiles script is not used, replace x,y,z by the required values
        # Otherwise the script will figure out the necessary values
        if dynamictilescript == False:
            s = s.replace('{$x}', str(tx))
            s = s.replace('{$y}', str(ty2))
            s = s.replace('{$inv_y}', str(ty2))
            s = s.replace('{$z}', str(tz))
        
        for cx, cy, cz in children:
            csouth, cwest, cnorth, ceast = self.tileswne(cx, cy, cz)
            s += """
        <NetworkLink>
          <name>%d/%d/%d</name>
          <Region>
            <LatLonAltBox>
              <north>%.14f</north>
              <south>%.14f</south>
              <east>%.14f</east>
              <west>%.14f</west>
            </LatLonAltBox>
            <Lod>
              <minLodPixels>%d</minLodPixels>
              <maxLodPixels>-1</maxLodPixels>
            </Lod>
          </Region>
          <Link>
            <href>%s?%s&amp;zxy=%d/%d/%d</href>
            <viewRefreshMode>onRegion</viewRefreshMode>
            <viewFormat/>
          </Link>
        </NetworkLink>
    """ % (cz, cx, cy, cnorth, csouth, ceast, cwest, args['minlodpixels'], href_str, querystring, cz, cx, cy)

        s += """      </Document>
    </kml>
    """
        return s
        