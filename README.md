This project is made up of two parts.  The first (referred to as the KML generator script) is a simple python script that, when run with a local web server (a simple python web server is provided), returns the kml structure required for Google Earth (GE) to display many tile mapping services on the web.  The second (referred to as the dynamic tile generator script) includes routines to either blend downloaded web tiles and/or mix them with local GIS raster data sources (it must also be run using a local web...(line truncated)...

To use these scripts, Google Earth and Python must be installed.  In addition, if using the dynamic tile generator script, GDAL >= 2.0.0, along with the GDAL python bindings must be installed.  However, if the dynamic tile generator script will not be used, then GDAL is not required.

See 'Instructions.txt' for further information.
