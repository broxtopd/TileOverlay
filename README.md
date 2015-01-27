# Display Tile Map Sources In Google Earth

This project is made up of two parts.  The first (referred to as the KML generator script) is a simple python script that, when run with a local web server (a simple python web server is provided), returns the kml structure that allows Google Earth to display many tile mapping services on the web.  The second (referred to as the dynamic tile generator script) includes routines to either blend downloaded web tiles and/or mix them with local GIS raster data sources (it must also be run using a local web server).  The local data sources do not need to be converted to tiles as this is done on the fly by the provided scripts (which currently make use of GDAL utility programs to do this).

To use these scripts, Google Earth and Python must be installed.  In addition, if using the dynamic tile generator script, GDAL >= 2.0.0, along with the GDAL python bindings must be installed.  However, if the dynamic tile generator script will not be used, then GDAL is not required.

## KML Generator Script

#### Set up

1) Copy the contents of the www folder to a local folder where you will be running the local web server.  

2) To ensure that the KML generator script (www/cgi-bin/generate_kml.py) will work, most systems require that the first line have #!/usr/bin/python (replace /usr/bin/python with the path to your python installation).  

3) If running the script on a different server port, both the scripts to run the server (www/threading_server8000.py) and running the KML generator script need to be modified to reflect this.  This simply involves changing the 8080 to a different number (>= 1024) on line 14 of threading_server8080.py and on lines 39 and 43 of generate_kml.py.  In generate_kml.py, the kmlscriptloc variable refers to the path of generate_kml.py, and the transparentpng variable refers to the address of a transparent image file that can be displayed if a particular web tile is not available (so GE does not display a red X).

4) CD to the directory that contains threading_server8080.py, then type "python threading_server8080.py". It will start up a simple web server that listens for requests.  It may be helpful to start this program using a shell script or a batch file to make it easy to start.

5) In Google Earth, add a network link, and in the link field, make a request to the kml_generator_script.  A couple of examples are given below (to Google Maps and USA Topo Maps from CalTopo.com):

Google Maps

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=http://mt1.google.com/vt/lyrs=m&x={$x}&y={$y}&z={$z};&zoom=0-20;</pre>

Google Terrain

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=http://mt1.google.com/vt/lyrs=p&x={$x}&y={$y}&z={$z};&zoom=0-16;</pre>

CalTopo's USGS DRGs

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=http://s3-us-west-1.amazonaws.com/caltopo/topo/{$z}/{$x}/{$y}.png;&zoom=5-16;&ullr=-130_80_-52_23;&checkStatus;</pre>

#### Usage

The above address is broken into several parts:

http://localhost:8000/cgi-bin/WebTileOverlay.py is the local address of the kml generator script, and does not change for different requests.

The query string (everything following the ?) can contain the following keys:

- url=? (required) - url of the web tile service with the z, y, and x, coordinates replaced with {$z},{$y}, and {$x}.  If the map source has a flipped y coordinate (TMS format), then {$inv_y} is used instead.  Note that because the address of some tile map servers (e.g. Google Maps) contain ampersands (which normally break up a query string), all url addresses must end in a semicolon.  Although it is not required that other fields end in a semicolon, it is best to end all fields in the query string with a semicolon to minimize confusion.

- zoom=? (optional) - zoom levels of the mapping service

- ullr=? (optional) - longitudes and latitudes of the upper left and lower right corners of the mapped area (so KML isn't generated needlessly for areas where there is no map).  LR must have a greater longitude than UL (i.e. it cannot cross the dateline) - non-global maps crossing the dateline must be handled with two network links for the western part and the eastern part separately 

- checkStatus (optional) - if included, this will tell the script to inquire whether a tile exists during kml generation so the returned kml does not have a broken link.  If the tile does not exist, then it will display a transparent image instead of a big red X denoting a broken link (useful if there are no tiles over, say, the ocean).  This option causes a very minor performance hit, but can make things look much better.

## Dynamic Tile Script

The dynamic tile script is not needed to simply display tiles from the web.  It will only be used under two conditions: 1) if the url does not point to a tile source (i.e. it does not contain {$z}), or 2) if the tiles are to be blended with other tiles or a local GIS data source.  There is no need to specify that the dynamic tile script should be used as the decision is made automatically.  All calls will still be made to the kml generator script, and the kml that is generated will only link to tiles that are generated by the dynamic tile generator script if necessary.

#### Set Up

1) Make sure that the python gdal bindings are installed and that the GDAL (>=2.0.0) utility programs are installed and on the path.  Specifically, the script makes use of gdalwarp with the -ovr flag (which will select the overview level whose resolution is the closest to the target resolution).  If this option were not used, displaying large geospatial datasets at lower zoom levels would be prohibitively slow.

2) As with the KML generator script, ensure that first line of the dynamic tile generator script (www/cgi-bin/generate_dynamic_tiles.py) refers to the local python installation.

3) If necessary, modify the tilescriptloc variable in the KML generator script (www/cgi-bin/generate_kml.py) with the appropriate port number (as well as threading_server8090.py) as per the instructions above.  It is suggested that kmlscriptloc and tilescriptloc use different ports so the KML generator script and the dynamic tile generator script do not interfere with each other.

4) CD to the directory that contains threading_server8090.py, then type "python threading_server8090.py" to start up the server to listen to requests.  Again, it may be helpful to put this call into a shell script or a batch file.

5) Display a file in google earth.  An example is given below.

- Download the data from https://dl.dropboxusercontent.com/u/1203002/GISData.zip
- Unzip the folder to a local directory
- Prepare the data (it is just a single band grayscale image, we need to add overview tiles to it).  On a command line in the directory where the GIS data is uncompressed and type: <pre>gdaladdo DEM.tif 2 4 8 16</pre>
- In Google Earth, add a network link with the address: <pre>http://localhost:8080/cgi-bin/generate_kml.py?url=PATH_TO_DATA_DIRECTORY/DEM.tif;&clrfile=PATH_TO_DATA_DIRECTORY/elevation.clr;</pre>
	
For large datasets, it is essential to build overview tiles so that displaying the map at lower zoom levels is not too slow.

If displaying a georeferenced image with 3-4 bands, then it is not necessary to use a colormap file.

#### Usage

In addition to simply displaying a GIS data source, the script can perform simple GIS related tasks, which are specified by additional options in the query string:

- url=? (required) - url of the local file to display or the web tile service

- zoom=? (optional) - zoom levels to generate kml for (local files can be overzoomed), but for web tiles, it is recommended to keep the same zoom levels as the mapping service

- ullr=? (optional) - longitudes and latitudes of the upper left and lower right corners of the mapped area.  This will not subset the map, but will only affect how the kml is generated.  Usually, this is not required because the script automatically determines the boundaries of the map source

- checkStatus (optional) - inquire whether a tile exists during kml generation (only use for web tiles)

- clrfile=? (optional) - address of the .clr file used to color a single banded raster image

- bgurl=? (optional) - url a local file or web tile service to be used as the blended image

- blend=? (optional) - specifies the degree that a datasource specified by the bgurl tag is blended with the datasource specified by the url tag.  A higher value gives greater weight to the bgurl datasource

- resample=? (optional) - GDAL resampling method (default = 'near')

- shpfile=? (optional) - shapefile used to make a raster transparent (default behavior: areas enclosed by a polygon are transparent)

- outsideMask (optional) - when included in the query string, causes area outside of polygon areas in shapefile transparent instead)

- cachedir=? (optional) - specifies a directory name to save generated tiles to (tiles will be created in <BaseDir>/dynamic_tules/<cachedir>)

#### A few more examples that use the more advanced features of the dynamic tile generator script.

Same as the above example, but use the oceans shapefile to make oceans transparent.

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=PATH_TO_DATA_DIRECTORY/DEM.tif;&clrfile=PATH_TO_DATA_DIRECTORY/elevation.clr;&shpfile=PATH_TO_DATA_DIRECTORY/ne_10m_ocean.shp;</pre>

Display the CalTopo topographic map blended with hillshade tiles from the web.

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=http:/s3-us-west-1.amazonaws.com/caltopo/topo/{$z}/{$x}/{$y}.png;&zoom=5-16;&ullr=-130_80_-52_23;&checkStatus;&bgurl=http://s3-us-west-1.amazonaws.com/ctrelief/relief/{$z}/{$x}/{$y}.png;&blend=0.3;</pre>

Display the DEM blended with the CalTopo shaded relief map over the US and using the oceans shapefile to make oceans transparent.

<pre>http://localhost:8080/cgi-bin/generate_kml.py?url=PATH_TO_DATA_DIRECTORY/DEM.tif;&clrfile=PATH_TO_DATA_DIRECTORY/elevation.clr;&bgurl=http://s3-us-west-1.amazonaws.com/ctrelief/relief/{$z}/{$x}/{$y}.png;&zoom=5-16;&ullr=-130_80_-52_23;&blend=0.3;&resample=bilinear;&shpfile=PATH_TO_DATA_DIRECTORY/ne_10m_ocean.shp;</pre>
