import socket
import sys
import time
import logging
import socketserver

import sipfullproxy

PORT = 5060

if __name__ == "__main__":

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))

    if len(sys.argv) < 2:
        ip_address = s.getsockname()[0]
    else:
        ip_address = sys.argv[1]

    logging.basicConfig(format='%(asctime)s:%(message)s', filename='calls.log', level=logging.INFO,
                        datefmt='%H:%M:%S')
    logging.info(time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime()))
    hostname = socket.gethostname()

    sipfullproxy.record_route = "Record-Route: <sip:%s:%d;lr>" % (ip_address, PORT)
    sipfullproxy.top_via = "Via: SIP/2.0/UDP %s:%d" % (ip_address, PORT)

    server = socketserver.UDPServer(('0.0.0.0', PORT), sipfullproxy.UDPHandler)
    server.serve_forever()
