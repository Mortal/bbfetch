import os
import re
import sys
# Path to bbfetch repository
sys.path += [os.path.expanduser('~/Repos/bbfetch')]
import bbfetch.grading


class Grading(bbfetch.grading.Grading):
    # Username used to log in to Blackboard
    username = '20094480'
    # Blackboard course id (of the form '_NNNNN_1')
    course = '_49454_1'
    # Names of classes/groups of students to display
    # If you need to grade hand-ins of all students in the course,
    # put classes = all
    classes = ['Hold DA1', 'Hold DA2']
    # Regex pattern and replacement text to abbreviate group names
    student_group_display_regex = (r'Gruppe (\S+) - (\S+)', r'\1-\2')
    # Regex pattern and replacement text to abbreviate handin names
    assignment_name_display_regex = (r'Week (\d+) Handin', r'\1')
    # Template indicating where to save each handin
    attempt_directory_name = '~/dSik2016/W{assignment}-{class_name}/{group}_{id}'
    # Case-insensitive regex used to capture comments indicating a score of 0
    rehandin_regex = r'genaflevering|re-?handin'
    # Case-insensitive regex used to capture comments indicating a score of 1
    accept_regex = r'accepted|godkendt'


if __name__ == "__main__":
    Grading.execute_from_command_line()
