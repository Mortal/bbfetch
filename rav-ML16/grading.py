import os
import re
import sys
# Path to bbfetch repository
sys.path += [os.path.expanduser('~/bbfetch')]
import blackboard.grading
from blackboard.session import PassBlackboardSession


class Grading(blackboard.grading.Grading):
    session_class = PassBlackboardSession
    # Username used to log in to Blackboard
    username = '20103940'
    # Blackboard course id (of the form '_NNNNN_1')
    course = '_54703_1'
    # Names of classes/groups of students to display
    classes = all
    # Regex pattern and replacement text to abbreviate group names
    student_group_display_regex = (r'Group +(\S+)', r'\1')
    # Regex pattern and replacement text to abbreviate handin names
    assignment_name_display_regex = (r'Hand-In (\S+)', r'\1')
    # Template indicating where to save each handin
    attempt_directory_name = '~/TA/ml2016/W{assignment}/{group}_{id}'
    # Case-insensitive regex used to capture comments indicating a score of 0
    rehandin_regex = r'genaflevering|re-?handin'
    # Case-insensitive regex used to capture comments indicating a score of 1
    accept_regex = r'accepted|godkendt'

    def get_attempt_directory_name(self, attempt):
        group_name = attempt.group_name
        group_name = re.sub(self.student_group_display_regex[0],
                            self.student_group_display_regex[1],
                            group_name)
        attempt_id = re.sub(r'_(.*)_1', r'\1', attempt.id)
        assignment = self.get_assignment_name_display(attempt.assignment)
        return os.path.expanduser(self.attempt_directory_name.format(
            assignment=assignment, group=group_name, id=attempt_id))


if __name__ == "__main__":
    Grading.execute_from_command_line()
