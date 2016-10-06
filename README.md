## Blackboard Grade Centre command line interface

### Setup

First, create a virtual environment and install the dependencies.

```
pyvenv-3.5 venv
source venv/bin/activate
pip install -r requirements.txt
```

Next, copy the two files in `roberto-dSik` to
your own directory and adjust them, filling out the details.

The course ID of a Blackboard courses is found by inspecting the course URL.
If it looks like:

`https://bb.au.dk/webapps/blackboard/execute/content/blankPage?cmd=view&content_id=_347138_1&course_id=_43290_1`

then the course id is `_43290_1`.

### Usage

Simply run the shell script `./grading`,
which will activate the virtual environment
and run your file `grading.py`:
```
cd path/to/grading
./grading --help
```

The useful options are `-d` (download new handins),
`-u` (upload feedback) and `-n` (offline mode).

#### Grading handins

When handins are downloaded, they are stored in the directories
pointed to by `attempt_directory_name`.

In order to upload feedback to the students, you must create a new file in this
directory named `comments.txt` and include either the word "Accepted"
or "re-handin" ("Godkendt"/"Genaflevering" in Danish).
To use other words, adjust `rehandin_regex` and `accept_regex`,
or override the `get_feedback_score` function to change the scoring behavior.

The `-u` (`--upload`) argument will look for handins that need grading
and have a `comments.txt` file, and then upload the comments to the student.

By default, if the student has handed in a file name `my-pretty-handin.pdf`
and you create a file with the same name followed by `_ann` ("annotated"),
e.g. `my-pretty-handin_ann.pdf`, it will be uploaded along with the feedback.
This is the naming convention used by
[PDFAnnotater](https://github.com/Mortal/pdfannotater).
You can change this behavior by overriding `get_feedback_attachments`.

#### Unzipping student handins

By default, if the student has submitted a `.zip`-file, it is extracted
into the same directory as the rest of the student handin files.
If you want to change this behavior or handle other kinds of archives
automatically, you need to override `Grading.extract_archive`.

#### Refreshing student data

With no arguments, `grading` will refetch the list of students that have
assignments that need to be graded.

If you have deleted student attempts in Blackboard,
you need to run `grading -a` to refresh the list of old attempts.
This is not refreshed automatically since it takes longer than
simply getting the list of assignments needing grading.

If students have been added to groups or removed from groups,
you need to run `grading -g` to get the new list of group memberships.
This is not refreshed automatically since it can take a while.


### Password security

This project uses the `keyring` 3rd party module from the Python package index (PyPI)
to store your login password to Blackboard so you don't have to enter it every time.

Thus, your Blackboard password will be accessible to all Python programs,
making it possible for anyone with access to your computer to read your
password. Keep your computer safe from malicious people!


## Example

In the following shell transcript, the `./grading` program in `~/TA/dADS2-2016`
is run with `-d` to download new student handins.
Then, the handins are graded (not shown), and finally, the feedback is uploaded
to the students with `./grading -u`.

In this way, no browser interaction with Blackboard is needed,
and the script takes just 30 seconds to download the 9 handins
and 30 seconds to upload the feedback (but your mileage may vary).

```sh
rav@novascotia:~/TA/dADS2-2016$ ./grading -d
[2016-04-29 08:29:42,808 INFO] Refresh gradebook
[2016-04-29 08:29:43,189 INFO] Sending login details to WAYF
[2016-04-29 08:29:52,556 INFO] Download Group Attempt Gruppe 2 - 01 28/04/16 /home/rav/TA/dADS2-2016/A3-2/01_26421/afl3.pdf (None bytes)
[2016-04-29 08:29:55,132 INFO] Download Group Attempt Gruppe 2 - 03 28/04/16 /home/rav/TA/dADS2-2016/A3-2/03_26348/main.pdf (None bytes)
[2016-04-29 08:29:57,650 INFO] Saving student_comments.txt for attempt Group Attempt Gruppe 2 - 04 26/04/16
[2016-04-29 08:29:57,735 INFO] Download Group Attempt Gruppe 2 - 04 26/04/16 /home/rav/TA/dADS2-2016/A3-2/04_26294/aflevering-3(2).pdf (None bytes)
[2016-04-29 08:30:00,379 INFO] Download Group Attempt Gruppe 2 - 05 28/04/16 /home/rav/TA/dADS2-2016/A3-2/05_26373/A3_Gruppe5.pdf (None bytes)
[2016-04-29 08:30:03,088 INFO] Download Group Attempt Gruppe 2 - 06 28/04/16 /home/rav/TA/dADS2-2016/A3-2/06_26429/Dads2Afl3.pdf (None bytes)
[2016-04-29 08:30:05,649 INFO] Download Group Attempt Gruppe 2 - 07 28/04/16 /home/rav/TA/dADS2-2016/A3-2/07_26416/Handin3.pdf (None bytes)
[2016-04-29 08:30:08,251 INFO] Download Group Attempt Gruppe 2 - 10 27/04/16 /home/rav/TA/dADS2-2016/A3-2/10_26316/aflevering10.pdf (None bytes)
[2016-04-29 08:30:10,968 INFO] Download Group Attempt Gruppe 2 - 11 28/04/16 /home/rav/TA/dADS2-2016/A3-2/11_26405/A3.pdf (None bytes)
Username Name                           Group  |  1    |  2    |  3    |  4    |  5    |  6
auxxxxxx xxxxxxxxxxxxxx                 DA2-01 | ✔     | ✘✔    | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-01 | ✔     | ✘✔    | !     |       |       |
auxxxxxx xxxxxxxxxxxxxx                 DA2-02 | ✘✔    | ✔     |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-03 | ✔     | ✘     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-03 | ✘✔    | ✘     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-03 | ✘✔    | ✘     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-04 | ✘     |       |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-05 | ✘✔    | ✘✔    | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-06 | ✘     | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-06 | ✘     | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxx                   DA2-06 | ✘     | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxx                   DA2-07 | ✘✔    | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-08 | ✔     |       |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-09 | ✘✔    | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-09 | ✘✔    | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-09 | ✘✔    | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-10 | ✔     | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-10 | ✔     | ✔     | !     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-11 | ✔     | ✔     | !     |       |       |
rav@novascotia:~/TA/dADS2-2016$ ./grading -u
[2016-04-29 09:56:30,295 INFO] Refresh gradebook
[2016-04-29 09:56:35,660 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:39,362 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:42,853 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:46,993 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:50,802 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:54,116 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:56:57,708 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:57:01,419 DEBUG] goodMsg1: Success: Grade Submitted.
[2016-04-29 09:57:01,419 INFO] Refresh gradebook
Username Name                           Group  |  1    |  2    |  3    |  4    |  5    |  6
auxxxxxx xxxxxxxxxxxxxx                 DA2-01 | ✔     | ✘✔    | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-01 | ✔     | ✘✔    | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxx                 DA2-02 | ✘✔    | ✔     |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-03 | ✔     | ✘     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-03 | ✘✔    | ✘     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-03 | ✘✔    | ✘     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-04 | ✘     |       |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-05 | ✘✔    | ✘✔    | ✔     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-06 | ✘     | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-06 | ✘     | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxx                   DA2-06 | ✘     | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxx                   DA2-07 | ✘✔    | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-08 | ✔     |       |       |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-09 | ✘✔    | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-09 | ✘✔    | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxxx          DA2-09 | ✘✔    | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-10 | ✔     | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxxxxx           DA2-10 | ✔     | ✔     | ✘     |       |       |
auxxxxxx xxxxxxxxxxxxxxxxx              DA2-11 | ✔     | ✔     | ✘     |       |       |
```


## Customizing how feedback is stored and found

If you have a different workflow for grading handins,
you might be able to customize `Grading` to suit your workflow
if you are ready to write a bit of Python code.

For instance, in the Machine Learning course, I store the feedback for accepted
handins in the directory `graded1/godkendt` and for re-handins in
`graded1/genaflevering`.

To support this, I have added a method named `get_ml_feedback` to my
Grading class which finds the feedback and score of a given attempt,
and then I have overriden `has_feedback`, `get_feedback`
and `get_feedback_attachments` to use `get_ml_feedback`.

The implementations are as follows.

```python
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

def get_feedback(self, attempt):
    score, filename = self.get_ml_feedback(attempt)
    if score == 0:
	# This string must contain 're-handin' so that get_feedback_score
	# will compute the score correctly.
	return ('Re-handin. ' +
		'Deadline November 3, 2016 at 9:00 (same as Hand-in 2). ' +
		'See comments in attached PDF.')
    if score == 1:
	# This string must contain 'accepted' so that get_feedback_score
	# will compute the score correctly.
	return ('Accepted. ' +
		'See comments in attached PDF.')
    # No ML feedback, but we delegate to superclass.
    return super().get_feedback(attempt)

def get_feedback_attachments(self, attempt):
    score, filename = self.get_ml_feedback(attempt)
    if filename:
	return [filename]
    # No ML feedback, but we delegate to superclass.
    return super().get_feedback_attachments(attempt)
```


## Implementation

This project contains classes to access
the Blackboard installation at Aarhus University
with the Python Requests framework, and is useful for teaching assistants and
teachers who wish to automate the Blackboard tedium.

The main component is a wrapper around `requests.Session`
named `blackboard.BlackboardSession`
with methods to automatically login and resubmit an HTTP request,
automatically follow HTML redirects,
save and load cookies, save and load login passwords.

For grading handins, the class `blackboard.grading.Grading`
should be extended with information on which course and students
should have their handins graded by the user.

For other Blackboard automation purposes, the `blackboard/examples/` directory
contains examples of how to download all forum posts for a course,
how to download the list of groups,
how to download a list of email addresses for each group of students,
and how to download the list of when students last accessed the course website.

The project uses the following 3rd party modules:

* requests (HTTP client for Python 2/3)
* html5lib (to parse and query HTML)
* keyring (to store your Blackboard password)
* [html2text](https://github.com/Alir3z4/html2text) (to convert HTML forum posts to Markdown)
* six (bridges incompatibilities between Python 2 and 3)

Install these requirements with `pip install -r requirements.txt`.
