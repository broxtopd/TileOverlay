import SocketServer
import BaseHTTPServer
import CGIHTTPServer
import hashlib
import os
import urllib2 

class ThreadingCGIServer(SocketServer.ThreadingMixIn,
                   BaseHTTPServer.HTTPServer):
    pass

import sys

server = ThreadingCGIServer(('', 8090), CGIHTTPServer.CGIHTTPRequestHandler)
#
try:
    while 1:
        sys.stdout.flush()
        server.handle_request()
except KeyboardInterrupt:
    print "Finished"