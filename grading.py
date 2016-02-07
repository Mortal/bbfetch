import html5lib
from requests.compat import urljoin
import blackboard
# from groups import get_groups
from gradebook import Gradebook
from elementtext import element_to_markdown, element_text_content


NS = {'h': 'http://www.w3.org/1999/xhtml'}


class Grading:
    def __init__(self, session):
        self.session = session
        self.gradebook = Gradebook(self.session, 'gradebook.json')
        self.assignments = self.get_assignments()

    def get_assignments(self):
        assignments = {}
        for assignment in self.gradebook.assignments.keys():
            by_attempt_id = {}
            user_groups = {}
            for user_id, s in self.gradebook.students.items():
                try:
                    assignment_data = s['assignments'][assignment]
                except KeyError:
                    continue
                for i, a in enumerate(assignment_data['attempts']):
                    first = i == 0
                    last = i == (len(assignment_data['attempts']) - 1)
                    data = by_attempt_id.setdefault(
                        a['groupAttemptId'],
                        dict(users=set(), first=first, last=last, **a))
                    data['users'].add(user_id)
                    user_groups.setdefault(user_id, []).append(
                        data['users'])

            for user_id, groups in user_groups.items():
                groups = frozenset(map(frozenset, groups))
                if len(groups) > 1:
                    print("%s has handed in assignment " % user_id +
                          "%s in multiple different groups: " % assignment +
                          "%s" % (groups,))

            assignments[assignment] = by_attempt_id
        return assignments

    def get_attempt_files(self, attempt):
        url = ('https://bb.au.dk/webapps/assignment/' +
               'gradeAssignmentRedirector' +
               '?course_id=%s' % self.session.course_id +
               '&groupAttemptId=_%s_1' % attempt)
        response = self.session.get(url)
        document = html5lib.parse(response.content, encoding=response.encoding)
        submission_text = document.find(
            './/div[@id="submissionTextView"]', NS)
        if submission_text:
            submission_text = element_to_markdown(submission_text)
        submission_list = document.find(
            './/ul[@id="currentAttempt_submissionList"]', NS)
        files = []
        for submission in submission_list:
            filename = element_text_content(submission)
            download_button = submission.find(
                './/a[@class="dwnldBtn"]', NS)
            if download_button:
                download_link = urljoin(
                    response.url, download_button.get('href'))
                files.append((filename, download_link))
            else:
                a = submission.find(
                    './/a[@id="currentAttempt_attemptFilesubmissionText"]', NS)
                if a:
                    # This <li> is for the submission_text
                    if not submission_text:
                        raise Exception(
                            "%r in file list, but no " % (filename,) +
                            "accompanying submission text contents")
                else:
                    raise Exception(
                        "No download link for file %r" % (filename,))
        return files

    def print_assignments(self):
        def group_key(group):
            k = ()
            for v in group['groupName'].split():
                try:
                    k += (0, int(v))
                except ValueError:
                    k += (1, v)
            return k + (group['last'],)

        assignments = self.get_assignments()
        assignments_sorted = sorted(assignments.items(), key=lambda x: x[0])
        for assignment, groups in assignments_sorted:
            print('='*79)
            print(self.gradebook.assignments[assignment]['name'])
            groups = sorted(groups.values(), key=group_key)
            for attempt in groups:
                if not attempt['last']:
                    continue
                members = sorted(
                    '%s %s' % (s['first_name'], s['last_name'])
                    for s in (self.gradebook.students[i]
                              for i in attempt['users'])
                )
                if attempt['groupStatus'] != 'ng':
                    score = attempt['groupScore']
                    if score == 1:
                        tag = '✔'
                    elif score == 0:
                        tag = '✘'
                    else:
                        tag = '%g' % score
                elif attempt['first']:
                    tag = ' '
                else:
                    tag = '.'
                tail = ''
                if not attempt['last']:
                    tail = ' Superseded by later attempt'
                print("[%s] %s (%s)%s" %
                      (tag, attempt['groupName'], ', '.join(members), tail))


def print_assignments(session):
    g = Grading(session)
    g.print_assignments()


if __name__ == "__main__":
    blackboard.wrapper(print_assignments)
