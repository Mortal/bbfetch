import re
import sys
sys.path += ['/home/rav/bbfetch']
import blackboard.grading


class Grading(blackboard.grading.Grading):
    username = '20103940'
    course = '_13158_1'
    classes = all

    def get_attempt_directory_name(self, attempt):
        """
        Return a path to the directory in which to store files
        relating to the given handin.
        """

        if attempt.assignment.group_assignment:
            group_name = attempt.group_name
            if group_name.startswith('Hand In Group'):
                group_number = group_name.split()[3]
            else:
                group_number = None
            name = group_number
        else:
            name = attempt.student.name

        attempt_id = attempt.id
        if attempt_id.startswith('_'):
            attempt_id = attempt_id[1:]
        if attempt_id.endswith('_1'):
            attempt_id = attempt_id[:-2]
        return '{base}/{assignment}/{name}_{id}'.format(
            base='/home/rav/TA/testcourse',
            assignment=self.get_assignment_name_display(attempt.assignment),
            name=name, id=attempt_id)

    def get_group_name_display(self, group_name):
        """Given a group name, compute an abbreviation of the name."""
        if group_name is None:
            return '?'
        elif group_name.startswith('Gruppe'):
            x = group_name.split()
            return '%s-%s' % (x[1], x[3])
        else:
            return group_name

    def get_student_ordering(self, student):
        """
        Return a sorting key for the student
        indicating how students should be sorted when displayed.
        Typically you want to sort by group, then by name.
        """
        return (self.get_group_name_display(student.group),
                student.name)

    def get_assignment_name_display(self, assignment):
        """
        Return an abbreviation of the name of an assignment.
        """
        if assignment.name.startswith('Hand In'):
            return assignment.name.split()[-1]
        else:
            return assignment.name

    def get_feedback_score(self, attempt, comments):
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
