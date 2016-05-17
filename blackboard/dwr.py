import re
import json

import blackboard
from blackboard import logger, ParserError


def js_object_parse(s):
    return json.loads(s)


def get_script_session_id(session):
    try:
        return session._script_session_id
    except AttributeError:
        pass
    url = 'https://bb.au.dk/javascript/dwr/engine.js'
    # Bypass BlackBoardSession.get and go straight to requests.Session instead
    dwr_engine = session.session.get(url).text
    mo = re.search('dwr.engine._origScriptSessionId = "(.*)";', dwr_engine)
    if mo:
        orig_id = mo.group(1)
    else:
        logger.warning("Could not find _origScriptSessionId")
        orig_id = '8A22AEE4C7B3F9CA3A094735175A6B14'
    session._script_session_id = '%s42' % orig_id
    return session._script_session_id


def parse_js(code):
    '''
    Parse the server response from DWR.

    >>> results = parse_js("""
    ... throw 'allowScriptTagRemoting is false.';
    ... //#DWR-INSERT
    ... //#DWR-REPLY
    ... var s0={};var s1={};s0.date="24/11/15";s0.exempt=false;
    ... s0.groupAttemptId="_17773_1";s0.groupName="Hand In Group 10";
    ... s0.groupScore=0.0;s0.groupStatus=null;s0.id="_181378_1";
    ... s0.override=false;s0.score=0.0;s0.status=null;
    ... s1.date="04/01/16";s1.exempt=false;s1.groupAttemptId="_21510_1";
    ... s1.groupName="Hand In Group 10";s1.groupScore=1.0;
    ... s1.groupStatus=null;s1.id="_201418_1";s1.override=false;
    ... s1.score=1.0;s1.status=null;
    ... dwr.engine._remoteHandleCallback('16','1234',[s0,s1]);
    ... """)
    >>> results.keys()
    dict_keys([1234])
    >>> len(results[1234])
    2
    >>> results[1234][0]['id']
    '_181378_1'
    >>> results[1234][1]['groupScore']
    1.0
    >>> results[1234][1]['override']
    False
    >>> results[1234][1]['status'] is None
    True
    >>> parse_js("""
    ... throw 'allowScriptTagRemoting is false.';
    ... //#DWR-INSERT
    ... //#DWR-REPLY
    ... dwr.engine._remoteHandleCallback('16','1234',[]);
    ... """)
    {1234: []}
    >>> parse_js("""
    ... dwr.engine._remoteHandleException('42','5',{javaClassName:\\
    ... "java.lang.Throwable",message:"Error"});
    ... """)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    ValueError: DWR returned exceptions: [(42, 5, 'java.lang...', 'Error')]
    '''

    id = r'[a-zA-Z_][a-zA-Z0-9_]*'
    obj = r'(?:[^;\'"]|\'(?:[^\\\']|\\.)*\'|"(?:[^\\"]|\\.)*")*'
    patterns = [
        ('throw', "throw "+obj+";"),
        ('comment', '//(.*)'),
        ('var', 'var ('+id+')=('+obj+');'),
        ('setattr', '('+id+')\\.('+id+')=('+obj+');'),
        ('call', r"dwr\.engine\._remoteHandleCallback\(" +
                 r"'(\d+)','(\d+)',\[((?:"+id+r"(?:,"+id+r")*)?)\]\);"),
        ('exception', r"dwr\.engine\._remoteHandleException\(" +
                      r"'(\d+)','(\d+)',\{javaClassName:(" + obj +
                      r"),message:(" + obj + r")\}\);"),
    ]
    pattern = '|'.join('(?P<%s>%s)' % (k, v) for k, v in patterns)
    i = 0
    locals = {}
    results = []
    exceptions = []
    for mo in re.finditer(pattern, code):
        j = mo.start(0)
        skipped = code[i:j]
        i = mo.end(0)
        if skipped.strip():
            raise ValueError("Did not parse %r" % (skipped.strip()))

        key = mo.lastgroup
        groups = mo.groups()[mo.lastindex - 1:]
        if key == 'throw':
            pass
        elif key == 'comment':
            pass
        elif key == 'var':
            name = groups[1]
            value = js_object_parse(groups[2])
            locals[name] = value
        elif key == 'setattr':
            name = groups[1]
            key = groups[2]
            value = js_object_parse(groups[3])
            locals[name][key] = value
        elif key == 'call':
            batch_id = int(groups[1])
            call_id = int(groups[2])
            if groups[3]:
                data = [locals[n] for n in groups[3].split(',')]
            else:
                data = []
            results.append((batch_id, call_id, data))
        elif key == 'exception':
            batch_id = int(groups[1])
            call_id = int(groups[2])
            class_name = js_object_parse(groups[3])
            message = js_object_parse(groups[4])
            exceptions.append((batch_id, call_id, class_name, message))

    skipped = code[i:]
    if skipped.strip():
        raise ValueError("Did not parse %r" % (skipped.strip()))

    if exceptions:
        raise ValueError("DWR returned exceptions: %r" % (exceptions,))

    return {call_id: data for batch_id, call_id, data in results}


def dwr_get_attempts_info_single_request(session, attempts):
    session_id = session.get_cookie('JSESSIONID', '/webapps/gradebook')
    payload = dict(
        callCount=len(attempts),
        page='/webapps/gradebook/do/instructor/enterGradeCenter' +
             '?course_id=%s&cvid=fullGC' % session.course_id,
        httpSessionId=session_id,
        scriptSessionId=get_script_session_id(session),
        batchId=42)

    course_id_raw = session.course_id.split('_')[1]
    for i, (student_id, handin_id) in enumerate(attempts):
        call_data = dict(
            scriptName='GradebookDWRFacade',
            methodName='getAttemptsInfo',
            id=i,
            param0='number:%s' % course_id_raw,
            param1='string:%s' % student_id,
            param2='string:%s' % handin_id)
        payload.update(('c%d-%s' % (i, k), v) for k, v in call_data.items())

    url = ('https://bb.au.dk/webapps/gradebook/dwr/call/plaincall/' +
           'GradebookDWRFacade.getAttemptsInfo.dwr')
    response = session.post(url, payload)
    try:
        results = parse_js(response.text)
    except ValueError as exn:
        raise ParserError(exn.args[0], response)
    return [results[i] for i in range(len(attempts))]


def dwr_get_attempts_info(session, attempts, batch_size=20):
    results = []
    for i in range(0, len(attempts), batch_size):
        j = min(len(attempts), i + batch_size)
        l = blackboard.slowlog()
        results.extend(
            dwr_get_attempts_info_single_request(session, attempts[i:j]))
        l("Fetching %d attempt lists took %%.1f s" % (j - i))
    return results
