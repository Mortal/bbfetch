import os
import re
import sys
import subprocess
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
    attempt_directory_name = '~/TA/ml2016/W{assignment}/{group:02}_{id}'
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
            assignment=assignment, group=int(group_name), id=attempt_id))

    def get_student_ordering(self, student):
        return (int(self.get_student_group_display(student) or '0'),
                student.name)

    def extract_rar(self, filename):
        subprocess.check_call(
            ('/usr/bin/unrar', 'x', filename),
            cwd=os.path.dirname(filename))

    def get_ml_feedback(self, attempt):
        """
        Compute (score, feedback_file) for given attempt, or (None, None)
        if no feedback exists.
        """
        if attempt != attempt.assignment.attempts[-1]:
            # This attempt is not the last attempt uploaded by the student,
            # so we do not give any feedback to this attempt.
            return None, None
        if any(a.score is not None for a in attempt.assignment.attempts[:-1]):
            # We already graded previous attempts, so this is an actual
            # re-handin from the student, which we do not handle with this
            # method.
            return None, None

        # Feedback for group 42 is stored in a file named comments_42.pdf
        group_name = attempt.group_name
        group_name = re.sub(self.student_group_display_regex[0],
                            self.student_group_display_regex[1],
                            group_name)
        filename = 'comments_%02d.pdf' % int(group_name)
        assignment = self.get_assignment_name_display(attempt.assignment)

        # Re-handin comments are stored separately from accepted handins.
        # The directory determines whether the assignment is accepted or not.
        accept_file = 'graded%s/godkendt/%s' % (assignment, filename)
        has_accept = os.path.exists(accept_file)
        reject_file = 'graded%s/genaflevering/%s' % (assignment, filename)
        has_reject = os.path.exists(reject_file)
        # Check that we don't have both accept and re-handin feedback.
        assert not (has_accept and has_reject)
        if has_accept:
            return 1, accept_file
        elif has_reject:
            return 0, reject_file
        else:
            return None, None

    def has_feedback(self, attempt):
        score, filename = self.get_ml_feedback(attempt)
        if filename:
            return True
        # No ML feedback, but maybe we want to give feedback to this attempt
        # in the standard bbfetch way, so we delegate to superclass.
        return super().has_feedback(attempt)

    def get_feedback_attachments(self, attempt):
        score, filename = self.get_ml_feedback(attempt)
        if filename:
            return [filename]
        # No ML feedback, but we delegate to superclass.
        return super().get_feedback_attachments(attempt)

    def get_feedback(self, attempt):
        score, filename = self.get_ml_feedback(attempt)
        assignment = self.get_assignment_name_display(attempt.assignment)
        if score == 0:
            # This string must contain 're-handin' so that get_feedback_score
            # will compute the score correctly.
            if assignment == '1':
                return ('Re-handin. ' +
                        'Deadline November 3, 2016 at 9:00 ' +
                        '(same as Hand-in 2). See comments in attached PDF.')
            else:
                raise ValueError(assignment)
        if score == 1:
            # This string must contain 'accepted' so that get_feedback_score
            # will compute the score correctly.
            return ('Accepted. ' +
                    'See comments in attached PDF.')
        # No ML feedback, but we delegate to superclass.
        return super().get_feedback(attempt)

    def get_gradebook_columns(self):
        columns = super().get_gradebook_columns()
        return [(name, fn, 4 if width == 3 else width)
                for name, fn, width in columns]


if __name__ == "__main__":
    Grading.execute_from_command_line()
