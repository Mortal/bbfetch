import json
import time
import numbers

import blackboard
from blackboard import logger, ParserError, BlackBoardSession
from dwr import dwr_get_attempts_info


def get_handin_attempt_counts(session, handin_id):
    url = ('https://bb.au.dk/webapps/gradebook/do/instructor/' +
           'getJSONUniqueAttemptData?course_id=%s' % session.course_id +
           '&itemId=%s' % handin_id)
    o = session.get(url).json()
    assert set(o.keys()) == set(['totalStudentsOrGroups', 'needsGradingCount',
                                 'numberOfUniqueAttempts'])
    return o


class Student:
    """
    >>> s = Student(dict(first_name="Foo", last_name="Bar", id="123"))
    >>> s
    <Student Foo Bar>
    >>> print(s)
    Foo Bar
    >>> s.id
    '123'
    """

    first_name = property(lambda self: self['first_name'])
    last_name = property(lambda self: self['last_name'])
    id = property(lambda self: self['id'])

    @property
    def name(self):
        return '%s %s' % (self.first_name, self.last_name)

    def __repr__(self):
        return '<Student {}>'.format(self)

    def __str__(self):
        return self.name

    def __init__(self, data):
        """
        data is a mutable mapping in which this student's data is stored.
        """
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __hash__(self):
        return hash(self.id)


class Students:
    sort_key = str

    def __init__(self, data):
        self._data = data

    def __iter__(self):
        students = map(Student, self._data.values())
        return iter(sorted(students, key=type(self).sort_key))

    def __getitem__(self, key):
        return Student(self._data[key])


def truncate_name(name, n):
    if len(name) <= n:
        return name
    parts = name.split()
    while len(parts) >= 2 and len(' '.join(parts)) >= n:
        parts = parts[:-2] + [parts[-2][0] + ' ' + parts[-1]]
    return ' '.join(parts)[:n]


class Gradebook(blackboard.Serializable):
    """Provides a view of what is accessible in the BlackBoard gradebook."""

    FIELDS = '_students fetch_time assignments'.split()

    def __init__(self, session):
        assert isinstance(session, BlackBoardSession)
        self.session = session

    students = property(lambda self: Students(self._students))

    def refresh(self):
        """Fetch gradebook information from BlackBoard website."""
        self.fetch_time = time.time()
        try:
            prev = self._students
        except AttributeError:
            prev = None
        self.assignments, self._students = self.fetch_overview()
        if prev is not None:
            self.copy_student_data(prev)
        self.refresh_attempts()

    def print_gradebook(self):
        """Print a representation of the gradebook state."""
        for u in self.students:
            name = str(u)
            if not u['available']:
                name = '(%s)' % name
            cells = []
            for aid in self.assignments.keys():
                try:
                    a = u['assignments'][aid]
                except KeyError:
                    cells.append('     ')
                    continue
                if a['needs_grading']:
                    ng = '!'
                else:
                    ng = ' '
                score = a['score']
                if isinstance(score, numbers.Real):
                    score = '%g' % score
                cells.append('%s%-4s' % (ng, score))
            name = truncate_name(name, 30)
            print('%-14s %-30s | %s' %
                  (u['username'], name, ' | '.join(cells)))

    def fetch_overview(self):
        """Fetch gradebook information. Returns (assignments, students)."""
        url = (
            'https://bb.au.dk/webapps/gradebook/do/instructor/getJSONData' +
            '?course_id=%s' % self.session.course_id)
        response = self.session.get(url)
        try:
            o = response.json()
        except json.decoder.JSONDecodeError:
            raise ParserError("Couldn't decode JSON", response)

        columns = o['colDefs']
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
        """After updating self._students, copy over old assignment data."""
        for user_id, user in self._students.items():
            try:
                prev_user = prev[user_id]
            except KeyError:
                # This user did not exist in the old gradebook.
                continue
            for assignment_id, a1 in user['assignments'].items():
                try:
                    a2 = prev_user['assignments'][assignment_id]
                except KeyError:
                    # This user did not have this assignment previously.
                    continue
                if a1['needs_grading'] and not a2['needs_grading']:
                    # A new handin needs grading -- don't copy this assignment.
                    continue
                if a1['score'] != a2['score']:
                    # Score information changed -- don't copy this assignment.
                    continue
                if a1['attempts'] is None:
                    a1['attempts'] = a2['attempts']

    def refresh_attempts(self):
        """Bulk-refresh all missing assignment data."""
        attempt_keys = []
        for user_id, user in self._students.items():
            for assignment_id, assignment in user['assignments'].items():
                if assignment['attempts'] is None:
                    attempt_keys.append((user_id, assignment_id))
        attempt_data = dwr_get_attempts_info(self.session, attempt_keys)
        for (user_id, aid), attempts in zip(attempt_keys, attempt_data):
            self._students[user_id]['assignments'][aid]['attempts'] = attempts


def print_gradebook(session):
    g = Gradebook(session)
    g.load('gradebook.json')
    g.print_gradebook()
    # g.save()


if __name__ == "__main__":
    blackboard.wrapper(print_gradebook)
