import time
import textwrap
import collections

import blackboard
from blackboard import BlackboardSession, logger, DOMAIN
from blackboard.dwr import dwr_get_attempts_info
from blackboard.backend import fetch_overview


def get_handin_attempt_counts(session, handin_id):
    url = ('https://%s/webapps/gradebook/do/instructor/' % DOMAIN +
           'getJSONUniqueAttemptData?course_id=%s' % session.course_id +
           '&itemId=%s' % handin_id)
    o = session.get(url).json()
    assert set(o.keys()) == {'totalStudentsOrGroups', 'needsGradingCount',
                             'numberOfUniqueAttempts'}
    return o


class DictWrapper:
    """
    Wrapper around a dictionary of objects.
    Each object is wrapped in the class type(self).item_class,
    and any keyword arguments passed to the constructor
    are passed along to item_class.

    >>> from collections import namedtuple
    >>> Foo = namedtuple('Foo', 'inner meta data_key')
    >>> foo_data = {'bar': ('bar', 2), 'baz': ('baz', 3)}
    >>> foos = DictWrapper(Foo, foo_data, meta=42, order_by=str)

    Iterating over the DictWrapper will yield the values of foo_data,
    wrapped in item_class.

    >>> for foo in foos.values():
    ...     print(foo)
    Foo(inner=('bar', 2), meta=42, data_key='bar')
    Foo(inner=('baz', 3), meta=42, data_key='baz')

    The index operator looks up the key in the underlying dictionary
    and wraps the result in item_class.

    >>> print(foos['bar'])
    Foo(inner=('bar', 2), meta=42, data_key='bar')
    """

    def __init__(self, item_class, data, order_by=None, **kwargs):
        self._item_class = item_class
        self._data = data
        if order_by is None:
            order_by = self._item_class.ordering
        self._order_by = order_by
        self._kwargs = kwargs

    def __len__(self):
        try:
            return len(self._items)
        except AttributeError:
            return len(self._data)

    def _init(self):
        self._values = [self._item_class(v, data_key=k, **self._kwargs)
                        for k, v in self._data.items()]
        self._values.sort(key=self._order_by)
        self._keys = [x._kwargs['data_key'] for x in self._values]

    def values(self):
        try:
            return iter(self._values)
        except AttributeError:
            self._init()
            return iter(self._values)

    def items(self):
        try:
            return zip(self._keys, self._values)
        except AttributeError:
            self._init()
            return zip(self._keys, self._values)

    def __getitem__(self, key):
        return self._item_class(self._data[key], data_key=key, **self._kwargs)


class ItemWrapper:
    id = property(lambda self: self['id'])

    @staticmethod
    def ordering(item):
        """Items are naturally ordered according to this key."""
        return str(item)

    def __repr__(self):
        return '<{} {}>'.format(type(self).__name__, self)

    def __str__(self):
        return self.id

    def __init__(self, data, **kwargs):
        self._data = data
        self._kwargs = kwargs

    def __getitem__(self, key):
        return self._data[key]

    def __hash__(self):
        return hash(self.id)

    def __lt__(self, other):
        if type(self) != type(other):
            raise TypeError("unorderable types: %s() < %s()" %
                            (type(self).__name__, type(other).__name__))
        return self.ordering(self) < self.ordering(other)

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self.id == other.id


class Student(ItemWrapper):
    """
    >>> s = Student(dict(first_name="Foo", last_name="Bar", id="au123"))
    >>> s
    <Student Foo Bar>
    >>> print(s)
    Foo Bar
    >>> s.id
    'au123'
    """

    first_name = property(lambda self: self['first_name'])
    last_name = property(lambda self: self['last_name'])
    username = property(lambda self: self['username'])
    student_number = property(lambda self: self['student_number'])

    @property
    def assignments(self):
        return DictWrapper(StudentAssignment, self['assignments'],
                           student=self,
                           assignments=self._kwargs['assignments'])

    @property
    def name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def group_from_cached_attempts(self):
        attempts = [attempt for assignment in self.assignments.values()
                    for attempt in (assignment.cached_attempts or [])]
        # Attempts are ordered first by assignment (latest last)
        # and then by attempt within the assignment (most recent last).
        # Thus, we take the last group_name.
        group_names = [attempt.group_name for attempt in attempts
                       if attempt.group_name]
        if group_names:
            return group_names[-1]

    @property
    def group(self):
        raise Exception(
            "Student.group is deprecated; use Grading.get_student_groups " +
            "or Student.group_from_cached_attempts instead")

    @property
    def score(self):
        return sum(a.score for a in self.assignments.values())

    def __str__(self):
        return self.name


class Assignment(ItemWrapper):
    """
    >>> a = Assignment(dict(
    ...     gpid="", due=0, src="resource/x-bb-assignment",
    ...     limitedAttendance=True, name="Aflevering 3", scrble=True,
    ...     userCreated=False, gbvis=True, hideAtt=False, cdate=0,
    ...     sid="449245", catid="813746", align="y", pos=5, an="n", am="y",
    ...     points=1, groupActivity=True, ldue=0, ssid="", manual=False,
    ...     visAll=False, vis=True, id="219347", isDeleg=False, type="N"))
    >>> print(a)
    Aflevering 3
    """

    name = property(lambda self: self['name'])

    @property
    def group_assignment(self):
        try:
            return self['groupActivity']
        except KeyError:
            return False

    @staticmethod
    def ordering(item):
        return int(item['pos'])  # Sort Assignments by position

    def __str__(self):
        return self.name


class Attempt(ItemWrapper):
    id = property(lambda self:
                  self['groupAttemptId']
                  if self.assignment.group_assignment
                  else self['id'])
    group_name = property(lambda self: self['groupName'])
    date = property(lambda self: self['date'])

    status_string = property(lambda self:
                             self['groupStatus']
                             if self.assignment.group_assignment
                             else self['status'])

    # The following interpretation of status_string
    # adheres to the Gradebook.AttemptInfo JavaScript class.
    @property
    def status(self):
        s = self.status_string
        if s == 'ip':
            return 'attempt_in_progress'
        elif s == 'nr':
            return 'needs_reconciliation'
        elif s:
            return 'needs_grading'
        else:
            return 'graded'

    needs_grading = property(lambda self: self.status == 'needs_grading')
    is_graded = property(lambda self: self.status == 'graded')
    score = property(lambda self:
                     None if not self.is_graded else
                     self['groupScore'] if self.assignment.group_assignment
                     else self['score'])

    # In all observed cases, status_string is 'ng' when the attempt needs
    # grading, but the JavaScript implementation doesn't seem to require this.
    unknown_status = property(lambda self:
                              self.needs_grading and
                              self.status_string != 'ng')

    assignment = property(lambda self: self._kwargs['assignment'])
    attempt_index = property(lambda self: self._kwargs['attempt_index'])

    student = property(lambda self: self.assignment.student)

    def __repr__(self):
        if self.assignment.group_assignment:
            return '<Attempt id=%s assignment=%s group=%r score=%s>' % (
                self.id, self.assignment, self.group_name,
                self.score if self.is_graded else self.status)
        else:
            return '<Attempt id=%s assignment=%s student=%s score=%s>' % (
                self.id, self.assignment, self.student,
                self.score if self.is_graded else self.status)

    def __str__(self):
        if self.assignment.group_assignment:
            return 'Group Attempt %s %s' % (self.group_name, self.date)
        else:
            return 'Attempt %s %s' % (self.student.name, self.date)


class StudentAssignment(ItemWrapper):
    id = property(lambda self: self._kwargs['data_key'])
    student = property(lambda self: self._kwargs['student'])
    needs_grading = property(lambda self: self['needs_grading'])

    @property
    def score(self):
        try:
            return float(self['score'])
        except ValueError:
            return 0

    @staticmethod
    def ordering(item):
        return 0  # Don't sort StudentAssignments

    def __getattr__(self, key):
        return getattr(self._kwargs['assignments'][self.id], key)

    @property
    def cached_attempts(self):
        r = self['attempts']
        if r is not None:
            return [Attempt(a, assignment=self, attempt_index=i)
                    for i, a in enumerate(r)]

    @property
    def attempts(self):
        a = self.cached_attempts
        if a is not None:
            return a
        self._fetch_attempts()
        return self.cached_attempts

    def _fetch_attempts(self):
        raise NotImplementedError(
            "StudentAssignment attempts was None, " +
            "implement _fetch_attempts!")

    def __str__(self):
        return self.name


def truncate_name(name, n):
    if len(name) <= n:
        return name
    parts = name.split()
    while len(parts) >= 2 and len(' '.join(parts)) >= n:
        parts = parts[:-2] + [parts[-2][0] + ' ' + parts[-1]]
    return ' '.join(parts)[:n]


class Gradebook(blackboard.Serializable):
    """Provides a view of what is accessible in the Blackboard gradebook."""

    FIELDS = '_students fetch_time _assignments'.split()

    def __init__(self, session):
        assert isinstance(session, BlackboardSession)
        self.session = session

    @property
    def students(self):
        return DictWrapper(Student, self._students,
                           assignments=self.assignments)

    @property
    def assignments(self):
        return DictWrapper(Assignment, self._assignments)

    def refresh(self, refresh_attempts=False, student_visible=None):
        """Fetch gradebook information from Blackboard website."""
        new_fetch_time = time.time()
        try:
            prev = self._students
        except AttributeError:
            prev = None
        # The following may raise requests.ConnectionError
        overview = fetch_overview(self.session)
        self._assignments = overview.assignments
        self._students = overview.students
        if prev is not None:
            self.copy_student_data(prev)
        # No exception raised; store fetch_time
        self.fetch_time = new_fetch_time
        self.refresh_attempts(refresh_all=refresh_attempts,
                              student_visible=student_visible)

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

    def refresh_attempts(self, attempts=None, student_visible=None, refresh_all=False):
        """Bulk-refresh all missing assignment data."""
        attempt_keys = []
        students = self.students.values()
        if attempts is None:
            if student_visible is not None:
                students = list(filter(student_visible, students))
            for user in students:
                for assignment_id, assignment in user.assignments.items():
                    if refresh_all or assignment.cached_attempts is None:
                        attempt_keys.append((user.id, assignment_id))
        else:
            attempt_ids = set(attempt.id for attempt in attempts)
            for user in students:
                for assignment_id, assignment in user.assignments.items():
                    a = assignment.cached_attempts or []
                    if any(attempt.id in attempt_ids for attempt in a):
                        attempt_keys.append((user.id, assignment_id))
        if not attempt_keys:
            return
        logger.info("Fetching %d attempt list%s",
                    len(attempt_keys), '' if len(attempt_keys) == 1 else 's')
        attempt_data = dwr_get_attempts_info(self.session, attempt_keys)
        for (user_id, aid), attempts in zip(attempt_keys, attempt_data):
            self.students[user_id]['assignments'][aid]['attempts'] = attempts


class Rubric(object):
    def __init__(self, **kwargs):
        self.title = kwargs.pop('title')
        self.rows = kwargs.pop('rows')
        super().__init__(**kwargs)

    def get_row_name(self, row_index):
        row = self.rows[row_index]
        name = row['title'].split()[0]
        return '%s. %s' % (row_index + 1, name)

    def get_cell_keys(self, cells):
        cells_sorted = sorted(cells, key=lambda cell: cell['score'])
        cell_keys = {cell['id']: str(i+1)
                     for i, cell in enumerate(cells_sorted)}
        return cell_keys

    def get_row_options(self, row_index):
        row = self.rows[row_index]
        cell_keys = self.get_cell_keys(row['cells'])
        chosen_key = (None if row['chosen_id'] is None
                      else cell_keys[row['chosen_id']])
        options = collections.OrderedDict([
            (cell_keys[cell['id']], cell)
            for cell in row['cells']])
        return chosen_key, options

    def rubric_form_indicator(self):
        return 'Rubric title: %s' % self.title

    def rubric_option_indicator(self, row_index):
        row_name = self.get_row_name(row_index)
        chosen_key, options = self.get_row_options(row_index)
        option_keys = ''.join(sorted(options.keys()))
        return '%s [%s]:' % (row_name, option_keys)

    def get_form_as_text(self):
        lines = [self.rubric_form_indicator()]
        for i, r in enumerate(self.rows):
            chosen_key, options = self.get_row_options(i)
            s = self.rubric_option_indicator(i)
            if chosen_key is not None:
                s += ' %s' % chosen_key
            lines.append(s)
        for i, r in enumerate(self.rows):
            lines.append('')
            row_name = self.get_row_name(i)
            lines.append('Options for %s:' % row_name)
            lines.append(r['title'])
            chosen_key, options = self.get_row_options(i)
            for key, option in options.items():
                lines.append('%s: %s' % (key, option['title']))
                lines.append(option['desc'])
        return '\n'.join(lines) + '\n'

    def get_form_input(self, text):
        lines = text.splitlines()
        indicator = self.rubric_form_indicator()
        indicator_index = [i for i, line in enumerate(lines)
                           if line == indicator]
        if len(indicator_index) == 0:
            raise ValueError("Could not find indicator line %r" % indicator)
        if len(indicator_index) > 1:
            raise ValueError("Found multiple indicators %r %r" %
                             (indicator, indicator_index))

        # Unpack line index
        indicator_index, = indicator_index

        answer_ids = []
        for i, r in enumerate(self.rows):
            line = lines[indicator_index + 1 + i]
            s = self.rubric_option_indicator(i)
            if not line.startswith(s):
                raise ValueError("Could not find option indicator %r" % s)
            answer = line[len(s):].strip()
            chosen_key, options = self.get_row_options(i)
            if not answer:
                answer_id = None
            else:
                try:
                    answer_id = options[answer]['id']
                except KeyError:
                    raise ValueError("Invalid option %r; must be one of %r" %
                                     (answer, ' '.join(options.keys())))
            answer_ids.append(answer_id)
        return answer_ids
