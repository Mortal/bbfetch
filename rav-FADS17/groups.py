from grading import Grading


def main():
    grading = Grading.init()
    for student in grading.gradebook.students.values():
        if not grading.get_student_visible(student):
            continue
        print(student.first_name, student.last_name, grading.get_student_group_display(student))


if __name__ == '__main__':
    main()
