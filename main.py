import socket
import sys
import time
import logging
import socketserver

import sipfullproxy

HOST = '0.0.0.0'
PORT = 5060

if __name__ == "__main__":

    if len(sys.argv) < 2:
        logging.error("Please enter valid proxy ip address")

    else:
        logging.basicConfig(format='%(asctime)s:%(message)s', filename='calls.log', level=logging.INFO,
                            datefmt='%H:%M:%S')
        logging.info(time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime()))
        hostname = socket.gethostname()
        ip_address = sys.argv[1]
        sipfullproxy.record_route = "Record-Route: <sip:%s:%d;lr>" % (ip_address, PORT)
        sipfullproxy.top_via = "Via: SIP/2.0/UDP %s:%d" % (ip_address, PORT)

        server = socketserver.UDPServer((HOST, PORT), sipfullproxy.UDPHandler)
        server.serve_forever()
