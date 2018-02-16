import os
import re
import sys
# sys.path += [os.path.expanduser('~/bbfetch'),
#              os.path.expanduser('~/work/bbfetch')]
import blackboard.grading  # noqa
from blackboard.session import PassBlackboardSession  # noqa


class Grading(blackboard.grading.Grading):
    session_class = PassBlackboardSession
    username = 'au306325'
    course = '_110424_1'
    student_group_display_regex = (r'Gruppe (\S+) - (\S+)', r'\1-\2')
    classes = all
    assignment_name_display_regex = (r'Aflevering (\d+)', r'\1')
    rehandin_regex = r'genaflevering|re-?handin'
    accept_regex = r'accepted|godkendt'

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
        if hostname == 'novascotia':
            base = os.path.expanduser('~/TA/IPSA/grading')
        else:
            raise ValueError(hostname)

        group_name = attempt.group_name
        if group_name.startswith('Gruppe Hold '):
            group_name = group_name.replace('Gruppe Hold ', '')
            # Translate "Gruppe Hold x - yy" into "Hold x" and "yy"
            class_name, group_number = group_name.split(' - ')
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
