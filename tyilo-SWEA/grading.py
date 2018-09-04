import os
import re
import sys
# Path to bbfetch repository
sys.path += [os.path.expanduser('~/repos/bbfetch')]
import blackboard.grading
import csv
from subprocess import run
from time import sleep


class Grading(blackboard.grading.Grading):
    # Username used to log in to Blackboard
    username = 'au522953'
    # Blackboard course id (of the form '_NNNNN_1')
    course = '_116853_1'
    # Names of classes/groups of students to display
    # If you need to grade hand-ins of all students in the course,
    # put classes = all
    classes = ['Hold DA3', 'Hold DA4']
    # Regex pattern and replacement text to abbreviate group names
    student_group_display_regex = (r'Gruppe (\S+) - (\S+)', r'\1-\2')
    # Regex pattern and replacement text to abbreviate handin names
    assignment_name_display_regex = (r'Iteration (\d+).*', r'\1')
    # Template indicating where to save each handin
    attempt_directory_name = '~/TA/SWEA18/{assignment}/{group}_{id}'

    def soffice_convert(self, in_file, out_format):
        out_dir = os.path.dirname(in_file)
        print(out_dir)
        out_file = in_file.split('.')[0] + '.' + out_format
        try:
            os.unlink(out_file)
        except:
            pass

        run(['soffice', '--convert-to', out_format, '--outdir', out_dir, in_file])

        # Wait for soffice to write file
        while not os.path.exists(out_file):
            sleep(0.1)
            print('Waiting for soffice...')

        return out_file

    def get_excel_fields(self, filename, fields):
        result = {k: None for k in fields}
        csv_filename = self.soffice_convert(filename, 'csv')
        with open(csv_filename) as f:
            reader = csv.reader(f)
            for row in reader:
                k = row[0].strip()
                if k in fields:
                    assert result[k] == None
                    value = row[1].strip()
                    result[k] = value

        assert None not in result.values()
        return result

    def get_swea_feedback(self, attempt):
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

        # Feedback for group 42 is stored in a file named eval_42.xlsx
        group_name = attempt.group_name
        group_name = re.sub(self.student_group_display_regex[0],
                            self.student_group_display_regex[1],
                            group_name)

        assignment = re.sub(self.assignment_name_display_regex[0],
                                 self.assignment_name_display_regex[1],
                                 attempt.assignment.name)

        excel_filename = f'eval_{group_name}.xlsx'
        excel_filename = 'graded%s/%s' % (assignment, excel_filename)
        print(os.path.abspath(excel_filename))
        if not os.path.exists(excel_filename):
            return None, None

        scoring = self.get_excel_fields(excel_filename, ['Submission', 'Score'])
        assert scoring['Submission'] in {'Yes', 'No'}

        score = int(scoring['Score']) if scoring['Submission'] == 'Yes' else 0

        pdf_filename = self.soffice_convert(excel_filename, 'pdf')
        return score, pdf_filename

    def has_feedback(self, attempt):
        score, filename = self.get_swea_feedback(attempt)
        if filename:
            return True
        # No SWEA feedback, but maybe we want to give feedback to this attempt
        # in the standard bbfetch way, so we delegate to superclass.
        return super().has_feedback(attempt)

    def get_feedback_attachments(self, attempt):
        score, filename = self.get_swea_feedback(attempt)
        if filename:
            return [filename]
        # No SWEA feedback, but we delegate to superclass.
        return super().get_feedback_attachments(attempt)

    def get_feedback(self, attempt):
        score, filename = self.get_swea_feedback(attempt)
        if score == None:
            return super().get_feedback(attempt)
        elif score == 0:
            return ('Genaflevering. ' +
                    'Se kommentarerne i den vedhæftede PDF.')
        else:
            return ('Godkendt. ' +
                    'Se kommentarerne i den vedhæftede PDF.')

    def get_attempt_score(self, attempt, comments):
        score, filename = self.get_swea_feedback(attempt)
        if score == None:
            return self.get_feedback_score(comments)
        else:
            return score



if __name__ == "__main__":
    Grading.execute_from_command_line()
