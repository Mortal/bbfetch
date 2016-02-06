import re
import json
import time
import numbers

import groups
import blackboard
from blackboard import logger


def get_handin_attempt_counts(session, handin_id):
    url = ('https://bb.au.dk/webapps/gradebook/do/instructor/' +
           'getJSONUniqueAttemptData?course_id=%s' % session.course_id +
           '&itemId=%s' % handin_id)
    o = session.get(url).json()
    assert set(o.keys()) == set(['totalStudentsOrGroups', 'needsGradingCount',
                                 'numberOfUniqueAttempts'])
    return o


def parse_js(code):
    '''
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
    ]
    pattern = '|'.join('(?P<%s>%s)' % (k, v) for k, v in patterns)
    i = 0
    locals = {}
    results = []
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
            value = json.loads(groups[2])
            locals[name] = value
        elif key == 'setattr':
            name = groups[1]
            key = groups[2]
            value = json.loads(groups[3])
            locals[name][key] = value
        elif key == 'call':
            batch_id = int(groups[1])
            call_id = int(groups[2])
            if groups[3]:
                data = [locals[n] for n in groups[3].split(',')]
            else:
                data = []
            results.append((batch_id, call_id, data))

    skipped = code[i:]
    if skipped.strip():
        raise ValueError("Did not parse %r" % (skipped.strip()))

    return {call_id: data for batch_id, call_id, data in results}


def dwr_get_attempts_info_single_request(session, attempts):
    session_id = session.get_cookie('JSESSIONID', '/webapps/gradebook')
    payload = dict(
        callCount=len(attempts),
        page='/webapps/gradebook/do/instructor/enterGradeCenter' +
             '?course_id=%s&cvid=fullGC' % session.course_id,
        httpSessionId=session_id,
        scriptSessionId=session.get_script_session_id(),
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
    with open('dwr_get_attempts_info.txt', 'wb') as fp:
        fp.write(response.content)
    results = parse_js(response.text)
    with open('dwr_get_attempts_info.json', 'w') as fp:
        json.dump(results, fp, indent=2)
    return [results[i] for i in range(len(attempts))]


def dwr_get_attempts_info(session, attempts, batch_size=20):
    results = []
    for i in range(0, len(attempts), 20):
        j = min(len(attempts), i + 20)
        results.extend(
            dwr_get_attempts_info_single_request(session, attempts[i:j]))
    return results


class Gradebook:
    def __init__(self, session, filename):
        self.session = session
        self.filename = filename
        try:
            self.load_file()
        except FileNotFoundError:
            self.assignment_ids = self.students = self.fetch_time = None
            self.refresh()
            self.save_file()

    def load_file(self):
        with open(self.filename) as fp:
            o = json.load(fp)
        self.students = o['students']
        self.fetch_time = o['fetch_time']
        self.assignment_ids = o['assignment_ids']

    def refresh(self):
        self.fetch_time = time.time()
        prev = self.students
        self.assignment_ids, self.students = self.fetch_overview()
        if prev is not None:
            self.copy_student_data(prev)
        else:
            self.fetch_groups()
        self.refresh_attempts()

    def save_file(self):
        with open(self.filename, 'w') as fp:
            json.dump({'students': self.students,
                       'assignment_ids': self.assignment_ids,
                       'fetch_time': self.fetch_time}, fp)

    def print_gradebook(self):
        def get_name(student):
            return '%s %s' % (student['first_name'], student['last_name'])

        user_ids = sorted(self.students.keys(),
                          key=lambda u: get_name(self.students[u]))
        for user_id in user_ids:
            u = self.students[user_id]
            name = get_name(u)
            if not u['available']:
                name = '(%s)' % name
            cells = []
            group = ''
            for group_name, group_id in (u['groups'] or []):
                prefix = 'Hand In Group '
                if group_name.startswith(prefix):
                    group = group_name[len(prefix):]
            for aid in self.assignment_ids:
                try:
                    a = u['assignments'][aid]
                except KeyError:
                    cells.append(' --  ')
                    continue
                if a['needs_grading']:
                    ng = '!'
                else:
                    ng = ' '
                score = a['score']
                if isinstance(score, numbers.Real):
                    score = '%g' % score
                cells.append('%s%-4s' % (ng, score))
            print('%-14s %-30s | %-5s | %s' %
                  (u['username'], name, group, ' | '.join(cells)))

    def fetch_groups(self):
        user_groups = groups.get_groups(self.session)
        usernames = {
            u['username']: user_id for user_id, u in self.students.items()}
        for u in user_groups:
            try:
                user_id = usernames[u['username']]
            except KeyError:
                logger.warn(
                    "Username %s in group list does not exist in gradebook",
                    u['username'])
                continue
            s = self.students[user_id]
            s['groups'] = u['groups']

    def fetch_overview(self):
        url = (
            'https://bb.au.dk/webapps/gradebook/do/instructor/getJSONData' +
            '?course_id=%s' % self.session.course_id)
        response = self.session.get(url)
        try:
            o = response.json()
        except json.decoder.JSONDecodeError:
            print(url)
            print(response.text)
            raise

        columns = o['colDefs']
        # column_dict = {c['id']: c for c in columns}
        assignment_ids = [c['id'] for c in columns
                          if c.get('src') == 'resource/x-bb-assignment']

        # column_ids = [c['id'] for c in columns]
        # is_assignment = [c['src'] == 'resource/x-bb-assignment' for c in columns]
        # column_names = [c['name'] for c in columns]

        # for i in assignment_ids:
        #     o = self.session.get(
        #         'https://bb.au.dk/webapps/gradebook/do/instructor/' +
        #         'getAttemptNavData?course_id=%s' % self.session.course_id +
        #         '&itemId=%s' % i).json()
        #     groups = []
        #     for group in o['options']:
        #         groups.append((group['value'], group['label']))

        #     group_attempts = []
        #     for group_id, name in groups:
        #         o = self.session.get(
        #             'https://bb.au.dk/webapps/gradebook/do/instructor/' +
        #             'getAttemptNavData?course_id=%s' % self.session.course_id +
        #             '&itemId=%s' % i +
        #             '&userId=%s' % group_id).json()
        #         for a in o['options']:
        #             group_attempts.append((group_id, a['value'], name, o['label']))

        users = {}
        for row in o['rows']:
            user_id = row[0]['uid']
            user_available = row[0]['avail']

            user_cells = {cell['c']: cell for cell in row if 'c' in cell}
            user_data = {cell['c']: cell['v'] for cell in row if 'v' in cell}

            user_assignments = {}

            for a in assignment_ids:
                try:
                    cell = user_cells[a]
                except KeyError:
                    continue
                needs_grading = bool(cell.get('ng'))
                user_assignments[a] = {
                    'score': cell['v'],
                    'needs_grading': needs_grading,
                    'attempts': None,
                }

            users[user_id] = dict(
                first_name=user_data['FN'],
                last_name=user_data['LN'],
                username=user_data['UN'],
                student_number=user_data['SI'],
                last_access=user_data['LA'],
                id=user_id,
                available=user_available,
                assignments=user_assignments,
                groups=None,
            )

        return assignment_ids, users

    def copy_student_data(self, prev):
        for user_id, user in self.students.items():
            try:
                prev_user = prev[user_id]
            except KeyError:
                continue
            if user['groups'] is None:
                user['groups'] = prev_user['groups']
            for assignment_id, a1 in user['assignments'].items():
                try:
                    a2 = prev_user['assignments'][assignment_id]
                except KeyError:
                    continue
                if a1['needs_grading'] and not a2['needs_grading']:
                    continue
                if a1['score'] != a2['score']:
                    continue
                if a1['attempts'] is None:
                    a1['attempts'] = a2['attempts']

    def refresh_attempts(self):
        attempt_keys = []
        for user_id, user in self.students.items():
            for assignment_id, assignment in user['assignments'].items():
                if assignment['attempts'] is None:
                    attempt_keys.append((user_id, assignment_id))
        attempt_data = dwr_get_attempts_info(self.session, attempt_keys)
        for (user_id, aid), attempts in zip(attempt_keys, attempt_data):
            self.students[user_id]['assignments'][aid]['attempts'] = attempts


def print_gradebook(session):
    g = Gradebook(session, 'gradebook.json')
    g.print_gradebook()


if __name__ == "__main__":
    blackboard.wrapper(print_gradebook)
