import os
import re
import sys
import subprocess
# Path to bbfetch repository
sys.path += [os.path.expanduser('~/Projects/Instructor/bbfetch')]
import blackboard.grading

class Grading(blackboard.grading.Grading):
    # Username used to log in to Blackboard
    username = '201206000'
    # Blackboard course id (of the form '_NNNNN_1')
    course = '_116847_1'
    # Names of classes/groups of students to display
    # If you need to grade hand-ins of all students in the course,
    # put classes = all
    classes = ['Class 2', 'Class 4']
    # Regex pattern and replacement text to abbreviate group names
    student_group_display_regex = (r'Class (\S+) - (\S+)', r'\1-\2')
    # Regex pattern and replacement text to abbreviate handin names
    assignment_name_display_regex = (r'Hand In (\d+)', r'\1')
    # Template indicating where to save each handin
    attempt_directory_name = '~/Documents/Instructor/ml18/handins/A{assignment}-{class_name}/{group}_{id}'
    # Case-insensitive regex used to capture comments indicating a score of 0
    rehandin_regex = r'genaflevering|re-?handin'
    # Case-insensitive regex used to capture comments indicating a score of 1
    accept_regex = r'accepted|godkendt'

    def get_attempt_directory_name(self, attempt):
        group_name = attempt.group_name
        class_name = group_name.split()[1]
        group_number = group_name.split()[3]
        attempt_id = re.sub(r'_(.*)_1', r'\1', attempt.id)
        assignment = self.get_assignment_name_display(attempt.assignment)

        return os.path.expanduser(self.attempt_directory_name.format(
            assignment=assignment,
            class_name=class_name, group=group_number, id=attempt_id))


    def extract_rar(self, filename):
        subprocess.check_call(
                ('/usr/bin/unrar', 'x', filename),
                cwd=os.path.dirname(filename))


    def extract_gz(self, filename):
        subprocess.check_call(
                ('tar', 'xvfz', filename), cwd=os.path.dirname(filename))


if __name__ == "__main__":
    Grading.execute_from_command_line()
