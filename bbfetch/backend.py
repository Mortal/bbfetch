import io
import os
import re
import csv
import json
import pprint
import html5lib
import collections

from requests.compat import urljoin, unquote, quote

import bbfetch
from bbfetch import logger, ParserError, BlackboardSession, DOMAIN
from bbfetch.datatable import fetch_datatable
from bbfetch.elementtext import (
    element_to_markdown, element_text_content, form_field_value,
    html_to_markdown)

try:
    from json.decoder import JSONDecodeError
except ImportError:
    # No JSONDecodeError in Python 3.4
    JSONDecodeError = ValueError


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def is_course_id_valid(session, course_id=None):
    if course_id is None:
        course_id = session.course_id
    url = (
        'https://%s/webapps/blackboard/execute/' % DOMAIN +
        'courseMain?course_id=%s' % course_id)
    response = session.get(url)
    document = html5lib.parse(response.content, transport_encoding=response.encoding)

    content_panel_path = './/h:div[@id="contentPanel"]'
    content_panel = document.find(content_panel_path, NS)
    if content_panel is None:
        logger.debug("is_course_id_valid: No contentPanel")
        return True
    classes = (content_panel.get('class') or '').split()
    return 'error' not in classes


def fetch_overview(session):
    """Fetch gradebook information. Returns (assignments, students, columns).

    The result is a namedtuple of type fetch_overview.result with attributes
    'assignments', 'students', 'columns'.
    """
    assert isinstance(session, BlackboardSession)
    url = (
        'https://%s/webapps/gradebook/do/instructor/getJSONData' % DOMAIN +
        '?course_id=%s' % session.course_id)
    l = bbfetch.slowlog()
    response = session.get(url)
    l("Fetching gradebook took %.1f s")
    try:
        o = response.json()
    except JSONDecodeError:
        raise ParserError("Couldn't decode JSON", response)

    if 'cachedBook' in o:
        o = o['cachedBook']
    try:
        columns = o['colDefs']
    except KeyError:
        raise ParserError("No colDefs", response)
    assignments = {}
    for c in columns:
        if c.get('src') != 'resource/x-bb-assignment':
            continue
        assignments[c['id']] = c

    users = {}
    for row in o['rows']:
        user_id = row[0]['uid']
        user_available = row[0]['avail']

        user_cells = {cell['c']: cell for cell in row if 'c' in cell}
        user_data = {cell['c']: cell['v'] for cell in row if 'v' in cell}

        user_assignments = {}

        for a in assignments.keys():
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
        )

    return fetch_overview.result(assignments, users, columns)


fetch_overview.result = collections.namedtuple(
    'fetch_overview', 'assignments students columns')


class NotYetSubmitted(Exception):
    pass


def fetch_attempt(session, attempt_id, is_group_assignment):
    assert isinstance(session, BlackboardSession)
    if is_group_assignment:
        url = ('https://%s/webapps/assignment/' % DOMAIN +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % session.course_id +
               '&groupAttemptId=%s' % attempt_id)
    else:
        url = ('https://%s/webapps/assignment/' % DOMAIN +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % session.course_id +
               '&attempt_id=%s' % attempt_id)
    l = bbfetch.slowlog()
    response = session.get(url)
    l("Fetching attempt took %.1f s")
    document = html5lib.parse(response.content, transport_encoding=response.encoding)

    currentAttempt_container = document.find(
        './/h:div[@id="currentAttempt"]', NS)
    if currentAttempt_container is None:
        not_yet_submitted = ('This attempt has not yet been submitted and ' +
                             'is not available to view at present.')
        if not_yet_submitted in response.text:
            raise NotYetSubmitted
        raise bbfetch.ParserError('No <div id="currentAttempt">',
                                  response=response)

    submission_text = document.find(
        './/h:div[@id="submissionTextView"]', NS)
    if submission_text is not None:
        submission_text = element_to_markdown(submission_text)

    comments = document.find(
        './/h:div[@id="currentAttempt_comments"]', NS)
    if comments is not None:
        xpath = './/h:div[@class="vtbegenerated"]'
        comments = [
            element_to_markdown(e)
            for e in comments.findall(xpath, NS)
        ]
        if not comments:
            raise bbfetch.ParserError(
                "Page contains currentAttempt_comments, " +
                "but it contains no comments",
                response)
        comments = '\n\n'.join(comments)

    files = []
    submission_list = document.find(
        './/h:ul[@id="currentAttempt_submissionList"]', NS)
    if submission_list is None:
        if comments is None and submission_text is None:
            logger.warning("The submission is completely empty.")
        elif submission_text is None:
            logger.warning(
                "No submission; the student only uploaded a comment.")
        else:
            logger.warning("The student only uploaded a text submission.")
        submission_list = ()
    for submission in submission_list:
        filename = element_text_content(submission)
        download_button = submission.find(
            './/h:a[@class="dwnldBtn"]', NS)
        if download_button is not None:
            download_link = urljoin(
                response.url, download_button.get('href'))
            files.append(
                dict(filename=filename, download_link=download_link))
        else:
            s = 'currentAttempt_attemptFilesubmissionText'
            a = submission.find(
                './/h:a[@id="' + s + '"]', NS)
            if a is not None:
                # This <li> is for the submission_text
                if not submission_text:
                    raise bbfetch.ParserError(
                        "%r in file list, but no " % (filename,) +
                        "accompanying submission text contents",
                        response)
            else:
                raise bbfetch.ParserError(
                    "No download link for file %r" % (filename,),
                    response)

    score_input = document.find(
        './/h:input[@id="currentAttempt_grade"]', NS)
    if score_input is None:
        score = None
    else:
        score = form_field_value(score_input)
        try:
            score = float(score)
        except ValueError:
            if score:
                raise bbfetch.ParserError(
                    "Couldn't parse currentAttempt_grade: %r" % (score,),
                    response)
            score = None

    feedbacktext_input = document.find(
        './/*[@id="feedbacktext"]', NS)
    if feedbacktext_input is None:
        feedback = ''
    else:
        feedback = form_field_value(feedbacktext_input)
        if '<' in feedback:
            feedback = html_to_markdown(feedback)

    gradingNotestext_input = document.find(
        './/*[@id="gradingNotestext"]', NS)
    if gradingNotestext_input is None:
        grading_notes = ''
    else:
        grading_notes = form_field_value(gradingNotestext_input)

    feedbackfiles_rows = document.find(
        './/h:tbody[@id="feedbackFiles_table_body"]', NS)
    feedbackfiles = []
    for i, row in enumerate(feedbackfiles_rows or []):
        try:
            link = row.findall('.//h:a', NS)[0]
        except IndexError:
            raise bbfetch.ParserError(
                "feedbackFiles_table_body row %s: no link" % i,
                response)
        download_link = urljoin(
            response.url, link.get('href'))
        filename = element_text_content(link)
        feedbackfiles.append(
            dict(filename=filename, download_link=download_link))

    rubric_data = None
    if is_group_assignment:
        rubric_input = document.find(
            './/h:input[@id="%s_rubricEvaluation"]' % attempt_id, NS)
        if rubric_input is not None:
            rubric_data_str = form_field_value(rubric_input)
            try:
                rubric_data = json.loads(unquote(rubric_data_str))
            except JSONDecodeError:
                raise ParserError("Couldn't decode JSON", response)
            t1 = 'blackboard.platform.gradebook2.GroupAttempt'
            t2 = 'blackboard.plugin.rubric.api.core.data.EvaluationEntity'
            if rubric_data['evalDataType'] == t1:
                if rubric_data['evalEntityId'] != attempt_id:
                    raise ParserError(
                        "evalEntityId is %r, expected %r" %
                        (rubric_data['evalEntityId'], attempt_id),
                        response)
            elif rubric_data['evalDataType'] == t2:
                # Seems to indicate an already filled-out rubric
                pass
            else:
                raise ParserError(
                    "Unknown evalDataType %r" % rubric_data['evalDataType'],
                    response)

    return dict(
        submission=submission_text,
        comments=comments,
        files=files,
        feedback=feedback,
        feedbackfiles=feedbackfiles,
        score=score,
        grading_notes=grading_notes,
        rubric_data=rubric_data,
    )


def fetch_rubric(session, assoc_id, rubric_object):
    rubric_id = rubric_object['id']
    rubric_title = rubric_object['title']
    prefix = 'BBFETCH'
    url = (
        'https://%s/webapps/rubric/do/course/gradeRubric' % DOMAIN +
        '?mode=grid&isPopup=true&rubricCount=1&prefix=%s' % prefix +
        '&course_id=%s' % session.course_id +
        '&maxValue=1.0&rubricId=%s' % rubric_id +
        '&viewOnly=false&displayGrades=true&type=grading' +
        '&rubricAssoId=%s' % assoc_id)
    l = bbfetch.slowlog()
    response = session.get(url)
    l("Fetching attempt rubric took %.1f s")
    document = html5lib.parse(response.content, transport_encoding=response.encoding)

    def is_desc(div_element):
        classes = (div_element.get('class') or '').split()
        return ('u_controlsWrapper' in classes and
                'radioLabel' not in classes and
                'feedback' not in classes)

    table = document.find(
        './/h:table[@id="%s_rubricGradingTable"]' % prefix, NS)

    column_headers = list(map(
        element_text_content, table.findall('./h:thead/h:tr/h:th', NS)[1:]))
    rubric_rows = []
    row_tags = table.findall('./h:tbody/h:tr', NS)
    for row in row_tags:
        row_id = row.get('rubricrowid')
        if row_id is None:
            raise ParserError("Could not get rubric row id", response)
        row_title = element_text_content(row.find('./h:th', NS))
        row_cells = row.findall('./h:td', NS)
        if len(row_cells) != len(column_headers):
            raise ParserError("Number of row cells does not equal " +
                              "number of table header cells", response)
        rubric_row_cells = []
        for cell in row_cells:
            cell_id = cell.get('rubriccellid')
            if cell_id is None:
                raise ParserError("Could not get rubric cell id", response)
            cell_container = cell.find(
                './h:div[@class="rubricCellContainer"]', NS)
            cell_percentage_element = cell_container.find(
                './/h:input[@class="selectedPercentField"]', NS)
            if cell_percentage_element is None:
                raise ParserError("No selectedPercentField", response)
            percentage = form_field_value(cell_percentage_element)
            desc = list(filter(is_desc, cell_container.findall('./h:div', NS)))
            if len(desc) != 1:
                raise ParserError("Could not get description", response)
            else:
                desc_text = element_text_content(desc[0])
            rubric_row_cells.append(dict(
                id=cell_id, desc=desc_text, percentage=percentage))
        rubric_rows.append(dict(
            id=row_id, title=row_title, cells=rubric_row_cells))
    return dict(id=rubric_id, title=rubric_title,
                columns=column_headers, rows=rubric_rows)


class Form:
    def __init__(self, session, url, form_xpath):
        # We need to fetch the page to get the nonce
        self._session = session
        if isinstance(url, str):
            response = session.get(url)
        else:
            # Presumably a response object
            response = url
            url = response.url
        self._history = response.history + [response]
        document = html5lib.parse(response.content, transport_encoding=response.encoding)
        form = document.find(form_xpath, NS)
        if form is None:
            raise ParserError("No %s" % form_xpath, response)
        self.enctype_formdata = form.get('enctype') == 'multipart/form-data'
        self.post_url = urljoin(response.url, form.get('action', ''))
        # TODO: <select>?
        fields = (form.findall('.//h:input', NS) +
                  form.findall('.//h:textarea', NS))
        self._data = [
            (field.get('name'), form_field_value(field))
            for field in fields
            if field.get('name')
            and (field.get('type') != 'radio' or
                 field.get('checked') is not None)
            and field.get('type') != 'submit'
        ]
        self._data_lookup = {k: i for i, (k, v) in enumerate(self._data)}

        self.files = []

    def get(self, k, *args):
        if args:
            d, = args
        try:
            return self._data[self._data_lookup[k]][1]
        except KeyError:
            if args:
                return d
            raise

    def getall(self, k):
        return [v for k_, v in self._data if k_ == k]

    def pop(self, k):
        self._data[self._data_lookup[k]] = None

    def set(self, k, v):
        try:
            self._data[self._data_lookup[k]] = k, v
        except KeyError:
            self._data_lookup[k] = len(self._data)
            self._data.append((k, v))

    def extend(self, kvs):
        for k, v in kvs:
            self._data_lookup[k] = len(self._data)
            self._data.append((k, v))

    def submit(self, post_url=None):
        if post_url is None:
            post_url = self.post_url
            print("POST to", post_url)
        if self.enctype_formdata and not self.files:
            # Blackboard requires the POST to be
            # Content-Type: multipart/form-data.
            # Unfortunately, requests can only make a form-data POST
            # if it has file-like input in the files list.
            self.files = [('dummy', io.StringIO(''))]
        try:
            data = [d for d in self._data if d is not None]
            response = self._session.post(post_url, data=data, files=self.files)
        except:
            logger.exception("data=%r files=%r", data, self.files)
            raise
        self._log_badmsg(response)
        response.history = self._history + list(response.history)
        return response

    def _log_badmsg(self, response):
        document = html5lib.parse(response.content, transport_encoding=response.encoding)
        badmsg = document.find('.//h:span[@id="badMsg1"]', NS)
        if badmsg is not None:
            raise ParserError(
                "badMsg1: %s" % element_text_content(badmsg), response,
                'Post data:\n%s' % pprint.pformat(self._data),
                'Files:\n%s' % pprint.pformat(self.files))

    def require_success_message(self, response):
        document = html5lib.parse(response.content, transport_encoding=response.encoding)
        msg = document.find('.//h:span[@id="goodMsg1"]', NS)
        if msg is None:
            raise ParserError(
                "No goodMsg1 in POST response", response,
                'Post data:\n%s' % pprint.pformat(self._data),
                'Files:\n%s' % pprint.pformat(self.files))
        logger.debug("goodMsg1: %s", element_text_content(msg))


def submit_grade(session, attempt_id, is_group_assignment,
                 grade, text, filenames, rubrics):
    assert isinstance(session, BlackboardSession)
    if is_group_assignment:
        url = ('https://%s/webapps/assignment/' % DOMAIN +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % session.course_id +
               '&groupAttemptId=%s' % attempt_id)
    else:
        url = ('https://%s/webapps/assignment/' % DOMAIN +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % session.course_id +
               '&attempt_id=%s' % attempt_id)
    form = Form(session, url, './/h:form[@id="currentAttempt_form"]')

    form.set('grade', str(grade))
    form.set('feedbacktext', text)
    form.set('gradingNotestext',
             'Submitted with https://github.com/Mortal/bbfetch')

    if rubrics:
        rubric_input = '%s_rubricEvaluation' % attempt_id
        rubric_data_str = form.get(rubric_input)
        rubric_data = json.loads(unquote(rubric_data_str))
        for rubric_cells, rubric in zip(rubrics, rubric_data['rubrics']):
            rubric['client_changed'] = True
            for input_row, row in zip(rubric_cells, rubric['rows']):
                row['cell_id'] = input_row
        rubric_data_str = quote(json.dumps(rubric_data))
        form.set(rubric_input, rubric_data_str)

    for i, filename in enumerate(filenames):
        base = os.path.basename(filename)
        form.extend([
            ('feedbackFiles_attachmentType', 'L'),
            ('feedbackFiles_fileId', 'new'),
            ('feedbackFiles_artifactFileId', 'undefined'),
            ('feedbackFiles_artifactType', 'undefined'),
            ('feedbackFiles_artifactTypeResourceKey', 'undefined'),
            ('feedbackFiles_linkTitle', base),
        ])
        with open(filename, 'rb') as fp:
            fdata = fp.read()
        form.files.append(('feedbackFiles_LocalFile%d' % i, (base, fdata)))
    if is_group_assignment:
        post_url = (
            'https://%s/webapps/assignment//gradeGroupAssignment/submit' % DOMAIN)
    else:
        post_url = (
            'https://%s/webapps/assignment//gradeAssignment/submit' % DOMAIN)
    response = form.submit(post_url)
    form.require_success_message(response)


def fetch_groups(session):
    """
    Computes a mapping from usernames (au123) to dictionaries,
    each dictionary containing the first/last name, role and group
    memberships of the particular user.
    The 'groups' entry is a list of (name, group id) pairs.
    """
    def strip_prefix(s, prefix):
        if s.startswith(prefix):
            return s[len(prefix):]
        else:
            raise ValueError("%r does not start with %r" % (s, prefix))

    def extract(key, cell, d):
        if key == 'userorgroupname':
            return d.split()[-1]
        if key not in ('Grupper', 'Groups'):
            return d
        groups = cell.findall(
            './/h:a[@class="userGroupNameListItemRemove"]', NS)
        res = []
        for g in groups:
            name = element_text_content(g)
            i = g.get('id')
            res.append((name, strip_prefix(i, 'rmv_')))
        return res

    url = ('https://%s/webapps/bb-group-mgmt-LEARN/execute/' % DOMAIN +
           'groupInventoryList?course_id=%s' % session.course_id +
           '&toggleType=users&chkAllRoles=on')

    response, keys, rows = fetch_datatable(
        session, url, extract=extract, table_id='userGroupList_datatable',
        edit_mode=True)
    username = keys.index('userorgroupname')
    first_name = keys.index('firstname')
    last_name = keys.index('lastname')
    try:
        role = keys.index('Role')
    except ValueError:
        role = keys.index('Rolle')
    try:
        groups = keys.index('Groups')
    except ValueError:
        groups = keys.index('Grupper')
    users = {}
    for row in rows:
        users[row[username]] = dict(
            username=row[username],
            first_name=row[first_name],
            last_name=row[last_name],
            role=row[role],
            groups=row[groups],
        )
    return users


def upload_csv(session, columns, rows):
    '''
    Upload one or more columns to the Grade Centre overview.

    'columns' is a list of str, and 'rows' is a list of list of str.

    columns[0] must be 'Username', and subsequent columns must end with
    "|nnnn", where nnnn is the column ID of an existing Grade Centre column.

    This function cannot be used to create new columns in the Grade Centre.
    '''
    if columns[0] != 'Username':
        raise ValueError("First column must be Username")

    # Validate column IDs
    column_ids = []
    for c in columns[1:]:
        mo = re.match(r'^.*\|(\d+)$', c)
        if not mo:
            raise ValueError("Column must end in a column ID")
        column_ids.append(mo.group(1))

    for r in rows:
        if len(r) != len(columns):
            raise ValueError("Wrong number of cells in row")

    # TODO: Use cached gradebook data instead of fetching directly
    grade_centre = fetch_overview(session)

    # Validate column IDs against getJSONData
    grade_centre_column_ids = [c.get('id') for c in grade_centre.columns]
    missing = [c for c in column_ids if c not in grade_centre_column_ids]
    if missing:
        raise ValueError('Column IDs not in Grade Centre: %r' % (missing,))

    # Validate usernames against getJSONData
    grade_centre_usernames = set(s.get('username')
                                 for s in grade_centre.students.values())
    missing = [row[0] for row in rows if row[0] not in grade_centre_usernames]
    if missing:
        raise ValueError('Usernames not in Grade Centre: %r' % (missing,))

    url = ('https://%s/webapps/gradebook/do/instructor/' % DOMAIN +
           'uploadGradebook2?course_id=%s' % session.course_id +
           '&actionType=selectFile')

    form = Form(session, url, './/h:form[@name="uploadGradebookForm2"]')
    form.set('theFile_attachmentType', 'L')
    base = 'bbfetch.csv'
    form.set('theFile_linkTitle', base)
    with io.StringIO() as fp:
        writer = csv.writer(fp)
        writer.writerow(columns)
        writer.writerows(rows)
        fdata = fp.getvalue().encode('utf-8')
    form.pop('theFile_LocalFile0')
    form.files.append(('theFile_LocalFile0', (base, fdata)))

    response = form.submit()
    assert response.status_code == 200
    form2 = Form(session, response, './/h:form[@name="uploadGradebookForm2"]')
    form2.set('bottom_Submit', 'Submit')
    # The following is implemented in Blackboard by JavaScript functions
    # validateSelection(form) and checkboxArray(form)
    form2.set('item_positions', ','.join(v for v in form2.getall('items')))
    response2 = form2.submit()
    # No goodMsg1 if no columns changed.
    # form2.require_success_message(response2)
