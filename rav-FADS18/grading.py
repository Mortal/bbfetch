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
    course = '_116845_1'
    student_group_display_regex = (r'Gruppe (.+) - (\S+)', r'\1-\2')
    classes = all
    assignment_name_display_regex = (r'Handin (\d+).*', r'\1')
    rehandin_regex = r'genaflevering|re-?handin'
    accept_regex = r'accepted|godkendt'

    def get_domjudge_team_name(self, student):
        groups = self.get_student_groups(student)
        if groups:
            pattern, repl = self.student_group_display_regex
            for g in groups:
                mo = re.fullmatch(pattern, g.name)
                if mo:
                    class_name = mo.group(1).lower().replace(" ", "")
                    group_number = int(mo.group(2))
                    return 'fads18-%s-%02d' % (class_name, group_number)

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
        base = os.path.expanduser('~/uni/9q1/FADS')
        if hostname == 'novascotia':
            base = os.path.expanduser('~/TA/FADS-2018')

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

    def get_feedback(self, attempt):
        feedback = super().get_feedback(attempt)
        if feedback is None:
            return feedback
        # Example of how to add HTML to comments.txt input:
        # return '<br />'.join(feedback.splitlines())
        return feedback


if __name__ == "__main__":
    Grading.execute_from_command_line()
