#    Copyright 2014 Philippe THIRION
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import socketserver
import re
import time
import logging

rx_register = re.compile("^REGISTER")
rx_invite = re.compile("^INVITE")
rx_ack = re.compile("^ACK")
rx_prack = re.compile("^PRACK")
rx_cancel = re.compile("^CANCEL")
rx_bye = re.compile("^BYE")
rx_options = re.compile("^OPTIONS")
rx_subscribe = re.compile("^SUBSCRIBE")
rx_publish = re.compile("^PUBLISH")
rx_notify = re.compile("^NOTIFY")
rx_info = re.compile("^INFO")
rx_message = re.compile("^MESSAGE")
rx_refer = re.compile("^REFER")
rx_update = re.compile("^UPDATE")
rx_from = re.compile("^From:")
rx_cfrom = re.compile("^f:")
rx_to = re.compile("^To:")
rx_cto = re.compile("^t:")
rx_tag = re.compile(";tag")
rx_contact = re.compile("^Contact:")
rx_ccontact = re.compile("^m:")
rx_uri = re.compile("sip:([^@]*)@([^;>$]*)")
rx_addr = re.compile("sip:([^ ;>$]*)")
rx_code = re.compile("^SIP/2.0 ([^ ]*)")
rx_request_uri = re.compile("^([^ ]*) sip:([^ ]*) SIP/2.0")
rx_route = re.compile("^Route:")
rx_contentlength = re.compile("^Content-Length:")
rx_ccontentlength = re.compile("^l:")
rx_via = re.compile("^Via:")
rx_cvia = re.compile("^v:")
rx_branch = re.compile(";branch=([^;]*)")
rx_rport = re.compile(";rport$|;rport;")
rx_contact_expires = re.compile("expires=([^;$]*)")
rx_expires = re.compile("^Expires: (.*)$")

# Global dictionary
record_route = ""
top_via = ""
registrar = {}
call_log = {}

# Responses
response200 = "200 Okej"
response400 = "400 Zla poziadavka"
response406 = "406 Neakceptovatelne"
response480 = "480 Momentalne nedostupne"
response500 = "500 Interna chyba servera"


def quotechars(chars):
    return ''.join(['.', c][c.isalnum()] for c in chars)


def getSocketInfo(uri):
    addr_port, socket, client_addr = registrar[uri]
    return socket, client_addr


class UDPHandler(socketserver.BaseRequestHandler):

    def changeRequestUri(self):
        # change request uri
        md = rx_request_uri.search(self.data[0])
        if md:
            method = md.group(1)
            uri = md.group(2)
            if uri in registrar:
                uri = "sip:%s" % registrar[uri][0]
                self.data[0] = "%s %s SIP/2.0" % (method, uri)

    def removeRouteHeader(self):
        # delete Route
        data = []
        for line in self.data:
            if not rx_route.search(line):
                data.append(line)
        return data

    def addTopVia(self):
        data = []
        for line in self.data:
            if rx_via.search(line) or rx_cvia.search(line):
                md = rx_branch.search(line)
                if md:
                    branch = md.group(1)
                    via = "%s;branch=%sm" % (top_via, branch)
                    data.append(via)
                # rport processing
                if rx_rport.search(line):
                    text = "received=%s;rport=%d" % self.client_address
                    via = line.replace("rport", text)
                else:
                    text = "received=%s" % self.client_address[0]
                    via = "%s;%s" % (line, text)
                data.append(via)
            else:
                data.append(line)
        return data

    def removeTopVia(self):
        data = []
        for line in self.data:
            if rx_via.search(line) or rx_cvia.search(line):
                if not line.startswith(top_via):
                    data.append(line)
            else:
                data.append(line)
        return data

    def getDestination(self):
        destination = ""
        for line in self.data:
            if rx_to.search(line) or rx_cto.search(line):
                md = rx_uri.search(line)
                if md:
                    destination = "%s@%s" % (md.group(1), md.group(2))
                break
        return destination

    def getOrigin(self):
        origin = ""
        for line in self.data:
            if rx_from.search(line) or rx_cfrom.search(line):
                md = rx_uri.search(line)
                if md:
                    origin = "%s@%s" % (md.group(1), md.group(2))
                break
        return origin

    def sendResponse(self, code):
        request_uri = "SIP/2.0 " + code
        self.data[0] = request_uri
        index = 0
        data = []
        for line in self.data:
            data.append(line)
            if rx_to.search(line) or rx_cto.search(line):
                if not rx_tag.search(line):
                    data[index] = "%s%s" % (line, ";tag=123456")
            if rx_via.search(line) or rx_cvia.search(line):
                # rport processing
                if rx_rport.search(line):
                    text = "received=%s;rport=%d" % self.client_address
                    data[index] = line.replace("rport", text)
                else:
                    text = "received=%s" % self.client_address[0]
                    data[index] = "%s;%s" % (line, text)
            if rx_contentlength.search(line):
                data[index] = "Content-Length: 0"
            if rx_ccontentlength.search(line):
                data[index] = "l: 0"
            index += 1
            if line == "":
                break

        data.append("")
        text = "\r\n".join(data).encode('utf-8')

        self.socket.sendto(text, self.client_address)

    def processRegister(self):
        fromm = ""
        contact = ""
        contact_expires = ""
        header_expires = ""
        expires = 0

        for line in self.data:
            if rx_to.search(line) or rx_cto.search(line):
                md = rx_uri.search(line)
                if md:
                    fromm = "%s@%s" % (md.group(1), md.group(2))
            if rx_contact.search(line) or rx_ccontact.search(line):
                md = rx_uri.search(line)
                if md:
                    contact = md.group(2)
                else:
                    md = rx_addr.search(line)
                    if md:
                        contact = md.group(1)
                md = rx_contact_expires.search(line)
                if md:
                    contact_expires = md.group(1)
            md = rx_expires.search(line)
            if md:
                header_expires = md.group(1)

        if len(contact_expires) > 0:
            expires = int(contact_expires)
        elif len(header_expires) > 0:
            expires = int(header_expires)

        if expires == 0:
            if fromm in registrar:
                del registrar[fromm]
                self.sendResponse(response200)
                return

        registrar[fromm] = [contact, self.socket, self.client_address]
        self.sendResponse(response200)

    def processInvite(self):
        origin = self.getOrigin()
        logging.info("Pouzivatel " + self.getOrigin() + " vola pouzivatelovi " + self.getDestination())

        if len(origin) == 0 or origin not in registrar:
            self.sendResponse(response400)
            return

        destination = self.getDestination()

        if len(destination) > 0:

            if destination in registrar:
                socket, cl_addr = getSocketInfo(destination)

                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                data.insert(1, record_route)

                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, cl_addr)
            else:
                self.sendResponse(response480)
        else:
            self.sendResponse(response500)

    def processAck(self):
        destination = self.getDestination()
        if len(destination) > 0:
            if destination in registrar:
                socket, claddr = getSocketInfo(destination)
                # self.changeRequestUri()
                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                # insert Record-Route
                data.insert(1, record_route)
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)

    def processNonInvite(self):

        origin = self.getOrigin()
        destination = self.getDestination()

        if len(origin) == 0 or origin not in registrar:
            self.sendResponse(response400)
            return

        logging.info('Pouzivatel ' + origin + " ukoncil hovor s pouzivatelom " + destination)

        if len(destination) > 0:
            if destination in registrar:
                socket, claddr = getSocketInfo(destination)
                # self.changeRequestUri()
                self.data = self.addTopVia()
                data = self.removeRouteHeader()
                # insert Record-Route
                data.insert(1, record_route)
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)
            else:
                self.sendResponse(response406)
        else:
            self.sendResponse(response500)

    def processCode(self):
        origin = self.getOrigin()
        if len(origin) > 0:
            if origin in registrar:
                socket, claddr = getSocketInfo(origin)
                self.data = self.removeRouteHeader()
                data = self.removeTopVia()
                text = "\r\n".join(data).encode('utf-8')
                socket.sendto(text, claddr)

        if self.data[0] == 'SIP/2.0 603 Decline':
            logging.info("Pozivatel: " + self.getDestination() + " odmietol hovor")
        elif self.data[0] == 'SIP/2.0 486 Busy here':
            logging.info("Pouzivatel " + self.getDestination() + " neprijal hovor")

    def processRequest(self):
        if len(self.data) > 0:
            request_uri = self.data[0]

            if rx_register.search(request_uri):
                self.processRegister()
            elif rx_invite.search(request_uri):
                self.processInvite()
            elif rx_ack.search(request_uri):
                self.processAck()
            elif rx_bye.search(request_uri):
                self.processNonInvite()
            elif rx_cancel.search(request_uri):
                self.processNonInvite()
            elif rx_options.search(request_uri):
                self.processNonInvite()
            elif rx_info.search(request_uri):
                self.processNonInvite()
            elif rx_message.search(request_uri):
                self.processNonInvite()
            elif rx_refer.search(request_uri):
                self.processNonInvite()
            elif rx_prack.search(request_uri):
                self.processNonInvite()
            elif rx_update.search(request_uri):
                self.processNonInvite()
            elif rx_subscribe.search(request_uri):
                self.sendResponse(response200)
            elif rx_publish.search(request_uri):
                self.sendResponse(response200)
            elif rx_notify.search(request_uri):
                self.sendResponse(response200)
            elif rx_code.search(request_uri):
                self.processCode()

    def handle(self):
        data = self.request[0].decode("utf-8")
        self.data = data.split("\r\n")
        self.socket = self.request[1]
        request_uri = self.data[0]

        # if valid request and code is received -> process request
        if rx_request_uri.search(request_uri) or rx_code.search(request_uri):
            self.processRequest()
