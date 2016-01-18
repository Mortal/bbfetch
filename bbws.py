# Copyright (C) 2015, Blackboard Inc.
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
#  -- Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
# 
#  -- Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
# 
#  -- Neither the name of Blackboard Inc. nor the names of its contributors 
#     may be used to endorse or promote products derived from this 
#     software without specific prior written permission.
#  
# THIS SOFTWARE IS PROVIDED BY BLACKBOARD INC ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL BLACKBOARD INC. BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
BBDN-Web-Service-Python-Sample-Code
    This project contains sample code for interacting with the Blackboard Learn SOAP Web Services in Python. This sample code was built with Python 2.7.9.

Project at a glance:
    Target: Blackboard Learn 9.1 SP 11 minimum
    Source Release: v1.0
    Release Date 2015-02-19
    Author: shurrey
    Tested on Blackboard Learn 9.1 April 2014 release
    
Requirements:
    Python 2.7.9
    SUDS: https://bitbucket.org/jurko/suds

Getting Started
    This section will describe how to build and use this sample code.
    
    Setting Up Your Development Environment

        You will first need to install Python 2.7.9. You can use tools like brew or ports to install, or runt he installation manually.

        In addition, you will need to install SUDS. I am using a branch of SUDS that is maintained (the original SUDS project has gone stagnant).
        
        You can download this library from here:
        https://bitbucket.org/jurko/suds
        
        Addionally, you can also install the library with pip:
        pip install suds-jurko
        
        NOTE: SUDS and the SUDS fork listed above are third-party libraries not associated with Blackboard in any way. Use at your own risk.

Configuring the Script
    This script is currently configured to use the Learn Developer Virtual Machine. You may use this with other systems, it will just require you to modify the following section in the main application loop. The only thing you should have to change is the server variable:

        # Set up the base URL for Web Service endpoints
        protocol = 'https'
        server = 'localhost:9877'
        service_path = 'webapps/ws/services'
        url_header = protocol + "://" + server + "/" + service_path + "/"

Developer Virtual Machine and SSL Certificate Checking
    If you decide to use the Blackboard Developer virtual machine, it is important to note that this VM contains a self-signed certificate, which will cause Python's urllib2 module to fail. Because the Blackboard Learn 9.1 April and newer releases require you to use SSL, you must make a change to Python's urllib2 module manually. THIS CHANGE WILL BYPASS SSL CERTIFICATE CHECKING, so be sure to undo this change when rolling out to production.

    To make this change, find the library urllib2. You can find it in the directory you installed Python. For me it is: .../python/2.7.9/Frameworks/Python.framework/Versions/2.7/lib/python2.7/urllib2.py

    Edit this file, and search for the class HTTPHandler. It will look like this:

        class HTTPHandler(AbstractHTTPHandler):
    
            def http_open(self, req):
                return self.do_open(httplib.HTTPConnection, req)
    
            http_request = AbstractHTTPHandler.do_request_
    
        if hasattr(httplib, 'HTTPS'):
            class HTTPSHandler(AbstractHTTPHandler):
    
                def __init__(self, debuglevel=0, context=None):
                    AbstractHTTPHandler.__init__(self, debuglevel)
                    self._context = context
    
                def https_open(self, req):
                    return self.do_open(httplib.HTTPSConnection, req,
                        context=self._context)
    
                https_request = AbstractHTTPHandler.do_request_
    Make it look like this:
    
        class HTTPHandler(AbstractHTTPHandler):
    
            def http_open(self, req):
                return self.do_open(httplib.HTTPConnection, req)
    
            http_request = AbstractHTTPHandler.do_request_
    
        if hasattr(httplib, 'HTTPS'):
            class HTTPSHandler(AbstractHTTPHandler):
    
                def __init__(self, debuglevel=0, context=None):
                    gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)   # Only for gangstars
                    AbstractHTTPHandler.__init__(self, debuglevel)
                    self._context = gcontext                        # Change context to gcontext
    
                def https_open(self, req):
                    return self.do_open(httplib.HTTPSConnection, req,
                        context=self._context)
    
                https_request = AbstractHTTPHandler.do_request_

Gradebook.WS WSDL and Learn October 2014
    There is a bug in the Blackboard Learn 9.1 October 2014 release with the WSDL for gradebook.ws. This will cause SUDS to fail when trying to ingest the WSDL.

    For more information and work-arounds for this bug, see the article here.
        https://blackboard.secure.force.com/btbb_articleview?id=kA370000000H5Fc

    If you follow workaround 1, simply change the initial gradebookWS call:
        url = url_header + 'Gradebook.WS?wsdl'
    with this:
        url = 'file:///Users/shurrey/wsdl/Gradebook.xml'
    
    Just be sure to replace my absolute path to the absolute path on your file system.

    If you follow workaround 2, the code should work as-is.
'''

import logging
import sys
import suds
import random

from suds.client import Client
from suds.xsd.doctor import ImportDoctor, Import
from suds.wsse import *    
from uuid import uuid1
from datetime import datetime

def generate_nonce(length=8):
    """Generate pseudorandom number."""
    return ''.join([str(random.randint(0, 9)) for i in range(length)])

def createHeaders(action, username, password, endpoint):
    """Create the soap headers section of the XML to send to Blackboard Learn Web Service Endpoints"""
    
    # Namespaces
    xsd_ns = ('xsd', 'http://www.w3.org/2001/XMLSchema')
    wsu_ns = ('wsu',"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd")
    wsa_ns = ('wsa', 'http://schemas.xmlsoap.org/ws/2004/03/addressing')
    
    # Set the action. This is a string passed to this funtion and corresponds to the method being called
    # For example, if calling Context.WS.initialize(), this should be set to 'initialize'
    wsa_action = Element('Action', ns=wsa_ns).setText(action)
    
    # Each method requires a unique identifier. We are using Python's built-in uuid generation tool.
    wsa_uuid = Element('MessageID', ns=wsa_ns).setText('uuid:' + str(uuid1()))
    
    # Setting the replyTo address == to the SOAP role anonymous
    wsa_address = Element('Address', ns=wsa_ns).setText('http://schemas.xmlsoap.org/ws/2004/03/addressing/role/anonymous')
    wsa_replyTo = Element('ReplyTo', ns=wsa_ns).insert(wsa_address)
    
    # Setting the To element to the endpoint being called
    wsa_to = Element('To', ns=wsa_ns).setText(url_header + endpoint)
    
    # Generate the WS_Security headers necessary to authenticate to Learn's Web Services
    # To create a session, ContextWS.initialize() must first be called with username session and password no session.
    # This will return a session Id, which then becomes the password for subsequent calls.
    security = createWSSecurityHeader(username, password)
    
    # Return the soapheaders that can be added to the soap call
    return([wsa_action, wsa_uuid, wsa_replyTo, wsa_to, security])
    
def createWSSecurityHeader(username,password):
    """ 
        Generate the WS-Security headers for making Blackboard Web Service calls.
        
        SUDS comes with a WSSE header generation tool out of the box, but it does not offer
        the flexibility needed to properly authenticate to the Blackboard SOAP-based services.
        Thus, we are creating the necessary headers ourselves.
    """
    
    # Namespaces
    wsse = ('wsse', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd')
    wsu = ('wsu', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd')
    

    # Create Security Element
    security = Element('Security', ns=wsse)
    security.set('SOAP-ENV:mustUnderstand', '1')
    
    # Create UsernameToken, Username/Pass Element
    usernametoken = Element('UsernameToken', ns=wsse)
    
    # Add the wsu namespace to the Username Token. This is necessary for the created date to be included.
    # Also add a Security Token UUID to uniquely identify this username Token. This uses Python's built-in uuid generation tool.
    usernametoken.set('xmlns:wsu', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd')
    usernametoken.set('wsu:Id', 'SecurityToken-' + str(uuid1()))
    
    # Add the username token to the security header. This will always be 'session'
    uname = Element('Username', ns=wsse).setText(username)
    # Add the password element and set the type to 'PasswordText'.
    # This will be nosession on the initialize() call, and the returned sessionID on subsequent calls.
    passwd = Element('Password', ns=wsse).setText(password)
    passwd.set('Type', 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText')
    # Add a nonce element to further uniquely identify this message.
    nonce = Element('Nonce', ns=wsse).setText(str(generate_nonce(24)))
    # Add the current time in UTC format.
    created = Element('Created', ns=wsu).setText(str(datetime.utcnow()))

    # Add Username, Password, Nonce, and Created elements to UsernameToken element.
    # Python inserts tags at the top, and Learn needs these in a specific order, so they are added in reverse order
    usernametoken.insert(created)
    usernametoken.insert(nonce)
    usernametoken.insert(passwd)
    usernametoken.insert(uname)

    # Insert the usernametoken into the wsse:security tag
    security.insert(usernametoken)
    
    # Create the timestamp in the wsu namespace. Set a unique id for this timestamp using Python's built-in user generation tool.
    timestamp = Element('Timestamp', ns=wsu)
    timestamp.set('wsu:Id', 'Timestamp-' + str(uuid1()))
    
    # Insert the timestamp into the wsse:security tag. This is done after usernametoken to insert before usernametoken in the subsequent XML
    security.insert(timestamp)
    
    # Return the security XML
    return security
    

if __name__ == '__main__':
    """
        This is the main class for the Blackboard Soap Web Services Python sample code.
        
        If I were to turn this into a production-level tool, much of this would be abstracted into more manageable chunks.
    """
    
    # If True, extra information will be printed to the console
    DEBUG = True;

    # Set up logging. logging level is set to DEBUG on the suds tools in order to show you what's happening along the way. 
    # It will give you SOAP messages and responses, which will help you develop your own tool.
    logging.basicConfig(level=logging.INFO)
    
    logging.getLogger('suds.client').setLevel(logging.DEBUG)
    logging.getLogger('suds.transport').setLevel(logging.DEBUG)
    logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
    logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)
    
    # Necessary system-setting for handling large complex WSDLs
    sys.setrecursionlimit(10000)
    
    # Set up the base URL for Web Service endpoints
    protocol = 'https'
    server = 'localhost:9877'
    service_path = 'webapps/ws/services'
    url_header = protocol + "://" + server + "/" + service_path + "/"
    
    # This is the pattern for the SUDS library to dynamically create your Web Service code.
    # There are caching capabilities so that you can avoid this overhead everytime your script runs.
    # I have included the code for each endpoint, although only the ones I need are uncommented.
    url = url_header + 'Context.WS?wsdl'
    contextWS = Client(url, autoblend=True)
    if DEBUG == True:
        print(contextWS)
    
    url = url_header + 'Announcement.WS?wsdl'
    announcementWS = Client(url, autoblend=True)
    if DEBUG == True:
        print(announcementWS)
    
#     url = url_header + 'Calendar.WS?wsdl'
#     calendarWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(calendarWS)
#     
#     url = url_header + 'Content.WS?wsdl'
#     contentWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(contextWS)
#     
#     url = url_header + 'Course.WS?wsdl'
#     courseWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(courseWS)
#     
#     url = url_header + 'CourseMembership.WS?wsdl'
#     courseMembershipWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(courseMembershipWS)
#     
#     # If on Blackboard Learn 9.1 April 2014 or earlier, or October 2014 with bug workaround #2 (see README.txt for details) 
#     url = url_header + 'Gradebook.WS?wsdl'
#     # Else if on October 2014 with bug workaround #1, replace my path with your absolute path on your filesystem.
#     # url = 'file:///Users/shurrey/wsdl/Gradebook.xml'
#     gradebookWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(gradebookWS)
#     
#     url = url_header + 'User.WS?wsdl'
#     userWS = Client(url, autoblend=True)
#     if DEBUG == True:
#        print(userWS)
#     
#     url = url_header + 'Util.WS?wsdl'
#     utilWS = Client(url,autoblend=True)
#     if DEBUG == True:
#        print(utilWS)
    
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('initialize', "session", "nosession", 'Context.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    contextWS.set_options(soapheaders=headers, port='Context.WSSOAP12port_https')
    
    # Initialize Context
    sessionId = contextWS.service.initialize()
    if DEBUG == True:
        print(sessionId)
    
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('login', 'session', sessionId, 'Context.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    contextWS.set_options(soapheaders=headers, port='Context.WSSOAP12port_https')
    
    # Login as User.
    loggedIn = contextWS.service.login("administrator", "password", "bb", "blackboard", "", 3600)
    if DEBUG == True:
        print(loggedIn)
    
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('getMyMemberships', 'session', sessionId, 'Context.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    contextWS.set_options(soapheaders=headers, port='Context.WSSOAP12port_https')
    
    # Get all memberships for current logged in user. This will return both Courses and Organizations.
    myMemberships = contextWS.service.getMyMemberships()
    if DEBUG == True:
        print(myMemberships)
    
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('initializeAnnouncementWS', 'session', sessionId, 'Announcement.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    announcementWS.set_options(soapheaders=headers, port='Announcement.WSSOAP12port_https')
    
    # Initialize the announcements Web Service
    annInit = announcementWS.service.initializeAnnouncementWS(False)
    if DEBUG == True:
        print(annInit)
    
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('getCourseAnnouncements', 'session', sessionId, 'Announcement.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    announcementWS.set_options(soapheaders=headers, port='Announcement.WSSOAP12port_https')
    
    # Loop through memberships returned from ContextWS.getMyMemberships()...
    for membership in myMemberships:
        if DEBUG == True:
            print(membership)
        
        # Grab the external id from the membership, in form (_XX_X)
        # This could be a course pk1 or an organization pk1
        externalId = membership.externalId
        if DEBUG == True:
            print(externalId)
            
        # Complex types (not int or char or string) must be generated using the client's factory method.
        # Once created, you can simply use variable.property to set the properties of the Type.
        annFilter = announcementWS.factory.create('ns4:AnnouncementAttributeFilter')
        annFilter.filterType = '2'
        annFilter.startDate = '0'
        annFilter.userId = ""
        
        if DEBUG == True:
            print(annFilter)
        
        # Call getCourseAnnouncements with the string representation of the external Id and the filter we created.
        announcements = announcementWS.service.getCourseAnnouncements(str(externalId),annFilter)
        if DEBUG == True:
            print(announcements)
        
    # Initialize headers and then call createHeaders to generate the soap headers with WSSE bits.
    headers = []
    headers = createHeaders('logout', 'session', sessionId, 'Context.WS')
    
    # Add Headers and WS-Security to client. Set port to default value, otherwise, you must add to service call
    contextWS.set_options(soapheaders=headers, port='Context.WSSOAP12port_https')
    
    # Log the user out to invalidate the session id. This prevents XSS
    loggedOut = contextWS.service.logout()
    if DEBUG == True:
        print(loggedOut)
    
    
    
    
