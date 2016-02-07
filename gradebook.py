import json
import time
import numbers

import blackboard
from blackboard import logger
from dwr import dwr_get_attempts_info


def get_handin_attempt_counts(session, handin_id):
    url = ('https://bb.au.dk/webapps/gradebook/do/instructor/' +
           'getJSONUniqueAttemptData?course_id=%s' % session.course_id +
           '&itemId=%s' % handin_id)
    o = session.get(url).json()
    assert set(o.keys()) == set(['totalStudentsOrGroups', 'needsGradingCount',
                                 'numberOfUniqueAttempts'])
    return o


class Gradebook:
    """Provides a view of what is accessible in the BlackBoard gradebook."""

    def __init__(self, session, filename):
        self.session = session
        self.filename = filename
        try:
            self.load_file()
        except FileNotFoundError:
            self.assignments = self.students = self.fetch_time = None
            self.refresh()
            self.save_file()

    def load_file(self):
        with open(self.filename) as fp:
            o = json.load(fp)
        self.students = o['students']
        self.fetch_time = o['fetch_time']
        self.assignments = o['assignments']

    def refresh(self):
        self.fetch_time = time.time()
        prev = self.students
        self.assignments, self.students = self.fetch_overview()
        if prev is not None:
            self.copy_student_data(prev)
        self.refresh_attempts()

    def save_file(self):
        with open(self.filename, 'w') as fp:
            json.dump({'students': self.students,
                       'assignments': self.assignments,
                       'fetch_time': self.fetch_time}, fp, indent=2)

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
            for aid in self.assignments.keys():
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
            print('%-14s %-30s | %s' %
                  (u['username'], name, ' | '.join(cells)))

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
        assignments = {}
        for c in columns:
            if c.get('src') != 'resource/x-bb-assignment':
                continue
            elif not c['groupActivity']:
                logger.warn(
                    "Assignment %s is not a group activity -- skipping",
                    c['name'])
            else:
                assignments[c['id']] = c


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

    def copy_student_data(self, prev):
        for user_id, user in self.students.items():
            try:
                prev_user = prev[user_id]
            except KeyError:
                continue
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
    # g.save_file()


if __name__ == "__main__":
    blackboard.wrapper(print_gradebook)
