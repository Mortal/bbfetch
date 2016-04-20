from blackboard.grading import Grading


class GradingDads(Grading):
    def get_group_name_display(self, group_name):
        """Given a group name, compute an abbreviation of the name."""
        if group_name is None:
            return group_name
        elif group_name.startswith('Gruppe'):
            x = group_name.split()
            return '%s-%s' % (x[1], x[3])
        else:
            return group_name

    def get_student_visible(self, student):
        """
        Return True if the given student should be visible,
        that is, if it is a member of the user's TA class.
        """
        group_name = self.get_group_name_display(student.group) or ''
        return group_name.startswith('2-')

    def get_student_ordering(self, student):
        """
        Return a sorting key for the student
        indicating how students should be sorted when displayed.
        Typically you want to sort by group, then by name.
        """
        return (student.group, student.name)

    def get_assignment_name_display(self, assignment):
        """
        Return an abbreviation of the name of an assignment.
        """
        if assignment.name.startswith('Aflevering'):
            return assignment.name.split()[-1]
        else:
            return assignment.name

    def get_attempt_directory_name(self, attempt):
        """
        Return a path to the directory in which to store files
        relating to the given handin.
        """

        group_name = attempt.group_name
        if group_name.startswith('Gruppe'):
            class_name = group_name.split()[1]
            group_number = group_name.split()[3]
        else:
            class_name = group_number = None

        attempt_id = attempt.id
        if attempt_id.startswith('_'):
            attempt_id = attempt_id[1:]
        if attempt_id.endswith('_1'):
            attempt_id = attempt_id[:-2]
        return '{base}/A{assignment}-{class_name}/{group}_{id}'.format(
            base='/home/rav/TA/dADS2-2016',
            assignment=self.get_assignment_name_display(attempt.assignment),
            class_name=class_name, group=group_number, id=attempt_id)


if __name__ == "__main__":
    GradingDads.execute_from_command_line()
