import time

import blackboard
from blackboard import BlackBoardSession
from blackboard.dwr import dwr_get_attempts_info
from blackboard.backend import fetch_overview


def get_handin_attempt_counts(session, handin_id):
    url = ('https://bb.au.dk/webapps/gradebook/do/instructor/' +
           'getJSONUniqueAttemptData?course_id=%s' % session.course_id +
           '&itemId=%s' % handin_id)
    o = session.get(url).json()
    assert set(o.keys()) == set(['totalStudentsOrGroups', 'needsGradingCount',
                                 'numberOfUniqueAttempts'])
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
    >>> foos = DictWrapper(Foo, foo_data, meta=42)

    Iterating over the DictWrapper will yield the values of foo_data,
    wrapped in item_class.

    >>> for foo in foos:
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

    def __iter__(self):
        try:
            return iter(self._items)
        except AttributeError:
            self._items = [self._item_class(v, data_key=k, **self._kwargs)
                           for k, v in self._data.items()]
            self._items.sort(key=self._order_by)
            return iter(self._items)

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

    @property
    def assignments(self):
        return DictWrapper(StudentAssignment, self['assignments'],
                           student=self,
                           assignments=self._kwargs['assignments'])

    @property
    def name(self):
        return '%s %s' % (self.first_name, self.last_name)

    @property
    def group(self):
        attempts = [attempt for assignment in self.assignments
                    for attempt in assignment.attempts]
        # Attempts are ordered first by assignment (latest last)
        # and then by attempt within the assignment (most recent last).
        # Thus, we take the last group_name.
        group_names = [attempt.group_name for attempt in attempts
                       if attempt.group_name]
        if group_names:
            return group_names[-1]

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

    def __str__(self):
        return self.name


class Attempt(ItemWrapper):
    id = property(lambda self:
                  self['groupAttemptId']
                  if self.assignment.group_assignment
                  else self['id'])
    group_name = property(lambda self: self['groupName'])
    date = property(lambda self: self['date'])
    needs_grading = property(lambda self:
                             self['groupStatus'] == 'ng'
                             if self.assignment.group_assignment
                             else self['status'] == 'ng')
    score = property(lambda self:
                     self['groupScore']
                     if self.assignment.group_assignment
                     else self['score'])

    assignment = property(lambda self: self._kwargs['assignment'])

    def __str__(self):
        if self.assignment.group_assignment:
            return 'Group Attempt %s %s' % (self.group_name, self.date)
        else:
            return 'Attempt %s %s' % (self.group_name, self.date)


class StudentAssignment(ItemWrapper):
    id = property(lambda self: self._kwargs['data_key'])
    student = property(lambda self: self._kwargs['student'])
    score = property(lambda self: self['score'])
    needs_grading = property(lambda self: self['needs_grading'])

    @staticmethod
    def ordering(item):
        return 0  # Don't sort StudentAssignments

    def __getattr__(self, key):
        return getattr(self._kwargs['assignments'][self.id], key)

    @property
    def attempts(self):
        r = self['attempts']
        if r is None:
            self._fetch_attempts()
            r = self['attempts']
        return [Attempt(a, assignment=self) for a in r]

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
    """Provides a view of what is accessible in the BlackBoard gradebook."""

    FIELDS = '_students fetch_time _assignments'.split()

    student_class = Student
    assignment_class = Assignment

    def __init__(self, session):
        assert isinstance(session, BlackBoardSession)
        self.session = session

    @property
    def students(self):
        return DictWrapper(type(self).student_class, self._students,
                           assignments=self.assignments)

    @property
    def assignments(self):
        return DictWrapper(type(self).assignment_class, self._assignments)

    def refresh(self):
        """Fetch gradebook information from BlackBoard website."""
        self.fetch_time = time.time()
        try:
            prev = self._students
        except AttributeError:
            prev = None
        self._assignments, self._students = fetch_overview(self.session)
        if prev is not None:
            self.copy_student_data(prev)
        self.refresh_attempts()

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

    def refresh_attempts(self, students=None):
        """Bulk-refresh all missing assignment data."""
        attempt_keys = []
        if students is None:
            students = self.students
        elif isinstance(students, type(self).student_class):
            students = [students]
        for user in students:
            for assignment_id, assignment in user['assignments'].items():
                if assignment['attempts'] is None:
                    attempt_keys.append((user.id, assignment_id))
        attempt_data = dwr_get_attempts_info(self.session, attempt_keys)
        for (user_id, aid), attempts in zip(attempt_keys, attempt_data):
            self.students[user_id]['assignments'][aid]['attempts'] = attempts
