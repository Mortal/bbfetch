import os
import re
import sys
sys.path += [os.path.expanduser('~/bbfetch'),
             os.path.expanduser('~/work/bbfetch')]
import blackboard.grading  # NOQA


class Grading(blackboard.grading.Grading):
    def __init__(self, session):
        super().__init__(session)
        session.forget_password = lambda self: print("keyring not used")

    @classmethod
    def get_username(cls, args):
        """Username to log in to BlackBoard with."""
        return '20103940'

    @classmethod
    def get_password(cls, **kwargs):
        """This method may be overridden to use something other than
        the keyring module to store your login password."""
        # Use https://www.passwordstore.org/ to get password
        import subprocess
        s = subprocess.check_output(
            ('pass', 'au'), universal_newlines=True)
        return s.splitlines()[0].strip()

    @classmethod
    def get_course(cls, args):
        """BlackBoard course ID including leading "_" and trailing "_1"."""
        return '_49446_1'

    def get_student_group_display(self, student):
        for g in self.get_student_groups(student):
            if g.name.startswith('Gruppe'):
                return '%s-%s' % (g.name.split()[1], g.name.split()[3])
        return ''

    def get_student_visible(self, student):
        """
        Return True if the given student should be visible,
        that is, if it is a member of the user's TA class.
        """
        # Add your classes to the following list, e.g. ["DA1", "DA2"]
        classes = ['2']
        for g in self.get_student_groups(student):
            for c in classes:
                if g.name == 'Hold ' + c:
                    return True
        return False

    def get_student_ordering(self, student):
        """
        Return a sorting key for the student
        indicating how students should be sorted when displayed.
        Typically you want to sort by group, then by name.
        """
        return (self.get_student_group_display(student), student.name)

    def get_assignment_name_display(self, assignment):
        """
        Return an abbreviation of the name of an assignment.
        """
        if assignment.name.startswith('Aflevering'):
            # Translate "Aflevering 3" into "3"
            return assignment.name.split()[1]
        else:
            return assignment.name

    def get_attempt_directory_name(self, attempt):
        """
        Return a path to the directory in which to store files
        relating to the given handin.
        """

        try:
            hostname = self.hostname
        except AttributeError:
            from socket import gethostname
            hostname = self.hostname = gethostname()

        # expanduser translates "~" into your home directory
        base = os.path.expanduser('~/uni/6q4/dADS2')
        if hostname == 'novascotia':
            base = os.path.expanduser('~/TA/dADS2-2016')

        group_name = attempt.group_name
        if group_name.startswith('Gruppe'):
            # Translate "Gruppe DAx - yy" into "DAx" and "yy"
            class_name = group_name.split()[1]
            group_number = group_name.split()[3]
            if class_name == '2':
                hyphen_class_name = ''
            else:
                hyphen_class_name = '-' + class_name
        else:
            hyphen_class_name = class_name = group_number = None

        attempt_id = re.sub(r'_(.*)_1', r'\1', attempt.id)
        assignment = self.get_assignment_name_display(attempt.assignment)

        # Translate Handin 1, Class DA2, Group 3, first attempt, id 456 into
        # ~/TA/dADS2-2016/A1-DA2/03_1_456
        fmt = '{base}/A{assignment}{hyphen_class_name}/{group}_{idx}_{id}'
        return fmt.format(
            base=base, assignment=assignment,
            hyphen_class_name=hyphen_class_name, group=group_number,
            id=attempt_id, idx=attempt.attempt_index + 1)

    def get_feedback_score(self, comments):
        """
        Decide from the contents of comments.txt what score to give a handin.
        """
        rehandin = re.search(r'genaflevering|re-?handin', comments, re.I)
        accept = re.search(r'accepted|godkendt', comments, re.I)
        if rehandin and accept:
            raise ValueError("Both rehandin and accept")
        elif rehandin:
            return 0
        elif accept:
            return 1

    def get_feedback(self, attempt):
        feedback = super().get_feedback(attempt)
        if feedback is None:
            return feedback
        # Example of how to add HTML to comments.txt input:
        # return '<br />'.join(feedback.splitlines())
        return feedback

    def get_gradebook_cells(self, columns, students):
        rows = super().get_gradebook_cells(columns, students)
        return rows
        # header_row = rows[0]
        # group_column = header_row.index('Group')

        # def get_group(row):
        #     return row[group_column]

        # result = []

        # from itertools import groupby
        # for group, group_rows in groupby(rows, key=get_group):
        #     group_rows = list(group_rows)
        #     columns = list(zip(*group_rows))
        #     print(columns[group_column:])
        #     all_same = all(
        #         all(c == column[0] for c in column)
        #         for column in columns[group_column:])
        #     if all_same:
        #         for row in group_rows[1:]:
        #             for i in range(group_column, len(row)):
        #                 if row[i] != '|':
        #                     row[i] = ''
        #     result.extend(group_rows)
        #     result.append([''] * len(header_row))
        # return result


if __name__ == "__main__":
    Grading.execute_from_command_line()
