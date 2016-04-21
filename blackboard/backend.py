import json
import html5lib

from requests.compat import urljoin

import blackboard
from blackboard import logger, ParserError, BlackBoardSession
from blackboard.elementtext import (
    element_to_markdown, element_text_content)


NS = {'h': 'http://www.w3.org/1999/xhtml'}


def fetch_overview(session):
    """Fetch gradebook information. Returns (assignments, students)."""
    assert isinstance(session, BlackBoardSession)
    url = (
        'https://bb.au.dk/webapps/gradebook/do/instructor/getJSONData' +
        '?course_id=%s' % session.course_id)
    response = session.get(url)
    try:
        o = response.json()
    except json.decoder.JSONDecodeError:
        raise ParserError("Couldn't decode JSON", response)

    columns = o['colDefs']
    assignments = {}
    for c in columns:
        if c.get('src') != 'resource/x-bb-assignment':
            continue
        elif not c.get('groupActivity'):
            logger.debug(
                "Assignment %s is not a group activity -- skipping",
                c['name'])
        else:
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

    return assignments, users


def fetch_attempt(session, attempt_id):
    assert isinstance(session, BlackBoardSession)
    url = ('https://bb.au.dk/webapps/assignment/' +
           'gradeAssignmentRedirector' +
           '?course_id=%s' % session.course_id +
           '&groupAttemptId=%s' % attempt_id)
    response = session.get(url)
    document = html5lib.parse(response.content, encoding=response.encoding)
    submission_text = document.find(
        './/h:div[@id="submissionTextView"]', NS)
    if submission_text is not None:
        submission_text = element_to_markdown(submission_text)
    submission_list = document.find(
        './/h:ul[@id="currentAttempt_submissionList"]', NS)
    if submission_list is None:
        raise ParserError("No currentAttempt_submissionList",
                          response)
    comments = document.find(
        './/h:div[@id="currentAttempt_comments"]', NS)
    if comments is not None:
        xpath = './/h:div[@class="vtbegenerated"]'
        comments = [
            element_to_markdown(e)
            for e in comments.findall(xpath, NS)
        ]
        if not comments:
            raise blackboard.ParserError(
                "Page contains currentAttempt_comments, " +
                "but it contains no comments",
                response)
        comments = '\n\n'.join(comments)
    files = []
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
                    raise blackboard.ParserError(
                        "%r in file list, but no " % (filename,) +
                        "accompanying submission text contents",
                        response)
            else:
                raise blackboard.ParserError(
                    "No download link for file %r" % (filename,),
                    response)
    return dict(
        submission=submission_text,
        comments=comments,
        files=files)
