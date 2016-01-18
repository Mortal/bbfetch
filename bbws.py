import sys
import random
import logging
from datetime import datetime

from uuid import uuid1
from suds.client import Client
from suds.wsse import Element


def generate_nonce(length=8):
    """Generate pseudorandom number."""
    return ''.join([str(random.randint(0, 9)) for i in range(length)])


def createHeaders(action, username, password, endpoint):
    """Create the soap headers section of the XML to send to Blackboard Learn
    Web Service Endpoints"""

    # Namespaces
    xsd_ns = ('xsd', 'http://www.w3.org/2001/XMLSchema')
    wsu_ns = (
        'wsu',
        "http://docs.oasis-open.org/wss/2004/01/" +
        "oasis-200401-wss-wssecurity-utility-1.0.xsd")
    wsa_ns = ('wsa', 'http://schemas.xmlsoap.org/ws/2004/03/addressing')

    # Set the action. This is a string passed to this funtion and corresponds
    # to the method being called
    # For example, if calling Context.WS.initialize(), this should be set to
    # 'initialize'
    wsa_action = Element('Action', ns=wsa_ns).setText(action)

    # Each method requires a unique identifier. We are using Python's built-in
    # uuid generation tool.
    wsa_uuid = Element('MessageID', ns=wsa_ns).setText('uuid:' + str(uuid1()))

    # Setting the replyTo address == to the SOAP role anonymous
    wsa_address = Element('Address', ns=wsa_ns).setText(
        'http://schemas.xmlsoap.org/ws/2004/03/addressing/role/anonymous')
    wsa_replyTo = Element('ReplyTo', ns=wsa_ns).insert(wsa_address)

    # Setting the To element to the endpoint being called
    wsa_to = Element('To', ns=wsa_ns).setText(url_header + endpoint)

    # Generate the WS_Security headers necessary to authenticate to Learn's Web
    # Services
    # To create a session, ContextWS.initialize() must first be called with
    # username session and password no session.
    # This will return a session Id, which then becomes the password for
    # subsequent calls.
    security = createWSSecurityHeader(username, password)

    # Return the soapheaders that can be added to the soap call
    return([wsa_action, wsa_uuid, wsa_replyTo, wsa_to, security])


def createWSSecurityHeader(username,password):
    """
    Generate the WS-Security headers for making Blackboard Web Service calls.

    SUDS comes with a WSSE header generation tool out of the box, but it does
    not offer the flexibility needed to properly authenticate to the Blackboard
    SOAP-based services.  Thus, we are creating the necessary headers
    ourselves.
    """

    # Namespaces
    wsse = ('wsse', 'http://docs.oasis-open.org/wss/2004/01/' +
                    'oasis-200401-wss-wssecurity-secext-1.0.xsd')
    wsu = ('wsu', 'http://docs.oasis-open.org/wss/2004/01/' +
                  'oasis-200401-wss-wssecurity-utility-1.0.xsd')


    # Create Security Element
    security = Element('Security', ns=wsse)
    security.set('SOAP-ENV:mustUnderstand', '1')

    # Create UsernameToken, Username/Pass Element
    usernametoken = Element('UsernameToken', ns=wsse)

    # Add the wsu namespace to the Username Token. This is necessary for the
    # created date to be included.
    # Also add a Security Token UUID to uniquely identify this username Token.
    # This uses Python's built-in uuid generation tool.
    usernametoken.set(
        'xmlns:wsu',
        'http://docs.oasis-open.org/wss/2004/01/' +
        'oasis-200401-wss-wssecurity-utility-1.0.xsd')
    usernametoken.set('wsu:Id', 'SecurityToken-' + str(uuid1()))

    # Add the username token to the security header. This will always be
    # 'session'
    uname = Element('Username', ns=wsse).setText(username)
    # Add the password element and set the type to 'PasswordText'.
    # This will be nosession on the initialize() call, and the returned
    # sessionID on subsequent calls.
    passwd = Element('Password', ns=wsse).setText(password)
    passwd.set(
        'Type',
        'http://docs.oasis-open.org/wss/2004/01/' +
        'oasis-200401-wss-username-token-profile-1.0#PasswordText')
    # Add a nonce element to further uniquely identify this message.
    nonce = Element('Nonce', ns=wsse).setText(str(generate_nonce(24)))
    # Add the current time in UTC format.
    created = Element('Created', ns=wsu).setText(str(datetime.utcnow()))

    # Add Username, Password, Nonce, and Created elements to UsernameToken
    # element.
    # Python inserts tags at the top, and Learn needs these in a specific
    # order, so they are added in reverse order
    usernametoken.insert(created)
    usernametoken.insert(nonce)
    usernametoken.insert(passwd)
    usernametoken.insert(uname)

    # Insert the usernametoken into the wsse:security tag
    security.insert(usernametoken)

    # Create the timestamp in the wsu namespace. Set a unique id for this
    # timestamp using Python's built-in user generation tool.
    timestamp = Element('Timestamp', ns=wsu)
    timestamp.set('wsu:Id', 'Timestamp-' + str(uuid1()))

    # Insert the timestamp into the wsse:security tag. This is done after
    # usernametoken to insert before usernametoken in the subsequent XML
    security.insert(timestamp)

    # Return the security XML
    return security


if __name__ == '__main__':
    """
    This is the main class for the Blackboard Soap Web Services Python sample
    code.

    If I were to turn this into a production-level tool, much of this would be
    abstracted into more manageable chunks.
    """

    # If True, extra information will be printed to the console
    DEBUG = True

    # Set up logging. logging level is set to DEBUG on the suds tools in order
    # to show you what's happening along the way.
    # It will give you SOAP messages and responses, which will help you develop
    # your own tool.
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

    # This is the pattern for the SUDS library to dynamically create your Web
    # Service code.  There are caching capabilities so that you can avoid this
    # overhead everytime your script runs.  I have included the code for each
    # endpoint, although only the ones I need are uncommented.
    url = url_header + 'Context.WS?wsdl'
    contextWS = Client(url, autoblend=True)
    if DEBUG:
        print(contextWS)

    url = url_header + 'Announcement.WS?wsdl'
    announcementWS = Client(url, autoblend=True)
    if DEBUG:
        print(announcementWS)

#     url = url_header + 'Calendar.WS?wsdl'
#     calendarWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(calendarWS)
#
#     url = url_header + 'Content.WS?wsdl'
#     contentWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(contextWS)
#
#     url = url_header + 'Course.WS?wsdl'
#     courseWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(courseWS)
#
#     url = url_header + 'CourseMembership.WS?wsdl'
#     courseMembershipWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(courseMembershipWS)
#
#     # If on Blackboard Learn 9.1 April 2014 or earlier, or October 2014 with
#     # bug workaround #2 (see README.txt for details)
#     url = url_header + 'Gradebook.WS?wsdl'
#     # Else if on October 2014 with bug workaround #1, replace my path with
#     # your absolute path on your filesystem.
#     # url = 'file:///Users/shurrey/wsdl/Gradebook.xml'
#     gradebookWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(gradebookWS)
#
#     url = url_header + 'User.WS?wsdl'
#     userWS = Client(url, autoblend=True)
#     if DEBUG:
#        print(userWS)
#
#     url = url_header + 'Util.WS?wsdl'
#     utilWS = Client(url,autoblend=True)
#     if DEBUG:
#        print(utilWS)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders('initialize', "session", "nosession", 'Context.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    contextWS.set_options(soapheaders=headers, port='Context.WSSOAP12port_https')

    # Initialize Context
    sessionId = contextWS.service.initialize()
    if DEBUG:
        print(sessionId)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders('login', 'session', sessionId, 'Context.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    contextWS.set_options(
        soapheaders=headers, port='Context.WSSOAP12port_https')

    # Login as User.
    loggedIn = contextWS.service.login(
        "administrator", "password", "bb", "blackboard", "", 3600)
    if DEBUG:
        print(loggedIn)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders(
        'getMyMemberships', 'session', sessionId, 'Context.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    contextWS.set_options(
        soapheaders=headers, port='Context.WSSOAP12port_https')

    # Get all memberships for current logged in user. This will return both
    # Courses and Organizations.
    myMemberships = contextWS.service.getMyMemberships()
    if DEBUG:
        print(myMemberships)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders(
        'initializeAnnouncementWS', 'session', sessionId, 'Announcement.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    announcementWS.set_options(
        soapheaders=headers, port='Announcement.WSSOAP12port_https')

    # Initialize the announcements Web Service
    annInit = announcementWS.service.initializeAnnouncementWS(False)
    if DEBUG:
        print(annInit)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders(
        'getCourseAnnouncements', 'session', sessionId, 'Announcement.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    announcementWS.set_options(
        soapheaders=headers, port='Announcement.WSSOAP12port_https')

    # Loop through memberships returned from ContextWS.getMyMemberships()...
    for membership in myMemberships:
        if DEBUG:
            print(membership)

        # Grab the external id from the membership, in form (_XX_X)
        # This could be a course pk1 or an organization pk1
        externalId = membership.externalId
        if DEBUG:
            print(externalId)

        # Complex types (not int or char or string) must be generated using the
        # client's factory method.
        # Once created, you can simply use variable.property to set the
        # properties of the Type.
        annFilter = announcementWS.factory.create(
            'ns4:AnnouncementAttributeFilter')
        annFilter.filterType = '2'
        annFilter.startDate = '0'
        annFilter.userId = ""

        if DEBUG:
            print(annFilter)

        # Call getCourseAnnouncements with the string representation of the
        # external Id and the filter we created.
        announcements = announcementWS.service.getCourseAnnouncements(
            str(externalId), annFilter)
        if DEBUG:
            print(announcements)

    # Initialize headers and then call createHeaders to generate the soap
    # headers with WSSE bits.
    headers = []
    headers = createHeaders('logout', 'session', sessionId, 'Context.WS')

    # Add Headers and WS-Security to client. Set port to default value,
    # otherwise, you must add to service call
    contextWS.set_options(
        soapheaders=headers, port='Context.WSSOAP12port_https')

    # Log the user out to invalidate the session id. This prevents XSS
    loggedOut = contextWS.service.logout()
    if DEBUG:
        print(loggedOut)
