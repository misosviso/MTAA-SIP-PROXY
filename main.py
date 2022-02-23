import socket
import sys
import time
import logging
import socketserver

import sipfullproxy

HOST = '0.0.0.0'
PORT = 5060

if __name__ == "__main__":

    logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', filename='proxy.log', level=logging.INFO, datefmt='%H:%M:%S')
    logging.info(time.strftime("%a, %d %b %Y %H:%M:%S ", time.localtime()))
    hostname = socket.gethostname()

    ip_address = socket.gethostbyname(hostname)

    if ip_address == "127.0.0.1":
        ip_address = sys.argv[1]

    sipfullproxy.record_route = "Record-Route: <sip:%s:%d;lr>" % (ip_address, PORT)
    sipfullproxy.top_via = "Via: SIP/2.0/UDP %s:%d" % (ip_address, PORT)

    logging.info("HOSTNAME: " + hostname)
    logging.info("IP Address: " + ip_address)

    server = socketserver.UDPServer((HOST, PORT), sipfullproxy.UDPHandler)
    server.serve_forever()
