import os
import re
import sys
sys.path += [os.path.expanduser('~/work/bbfetch')]
import blackboard.grading


class Grading(blackboard.grading.Grading):
    @classmethod
    def get_username(cls, args):
        """Username to log in to BlackBoard with."""
        return '20103940'

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
        group_name = self.get_student_group_display(student)
        return any(group_name.startswith(c + '-') for c in classes)

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

        # expanduser translates "~" into your home directory
        base = os.path.expanduser('~/uni/6q4/dADS2')

        group_name = attempt.group_name
        if group_name.startswith('Gruppe'):
            # Translate "Gruppe DAx - yy" into "DAx" and "yy"
            class_name = group_name.split()[1]
            group_number = group_name.split()[3]
        else:
            class_name = group_number = None

        attempt_id = re.sub(r'_(.*)_1', r'\1', attempt.id)
        assignment = self.get_assignment_name_display(attempt.assignment)

        # Translate Handin 1, Class DA2, Group 3, attempt id 456 into
        # ~/TA/dADS2-2016/A1-DA2/03-456
        return '{base}/A{assignment}-{class_name}/{group}_{id}'.format(
            base=base, assignment=assignment,
            class_name=class_name, group=group_number, id=attempt_id)

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


if __name__ == "__main__":
    Grading.execute_from_command_line()
