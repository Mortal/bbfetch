## BlackBoard Grade Centre command line interface

### Setup

First, create a virtual environment and install the dependencies.

```
pyvenv-3.5 venv
source venv/bin/activate
pip install -r requirements.txt
```

Next, copy the two files in `rav-dADS2` to
your own directory and adjust them, filling out the details.

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
pointed to by `get_attempt_directory_name`.

In order to upload feedback to the students, you must create a new file in this
directory named `comments.txt` and include either the word "Accepted"
or "re-handin" ("Godkendt"/"Genaflevering" in Danish).
The `get_feedback_score` function may be modified to change this behavior.
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

If you have deleted student attempts in BlackBoard,
you need to run `grading -a` to refresh the list of old attempts.
This is not refreshed automatically since it takes longer than
simply getting the list of assignments needing grading.

If students have been added to groups or removed from groups,
you need to run `grading -g` to get the new list of group memberships.
This is not refreshed automatically since it can take a while.


### Password security

This project uses the `keyring` 3rd party module from the Python package index (PyPI)
to store your login password to BlackBoard so you don't have to enter it every time.

Thus, your BlackBoard password will be accessible to all Python programs,
making it possible for anyone with access to your computer to read your
password. Keep your computer safe from malicious people!


## Example

In the following shell transcript, the `./grading` program in `~/TA/dADS2-2016`
is run with `-d` to download new student handins.
Then, the handins are graded (not shown), and finally, the feedback is uploaded
to the students with `./grading -u`.

In this way, no browser interaction with BlackBoard is needed,
and the script takes just 30 seconds to download the 9 handins
and 30 seconds to upload the feedback (but your mileage may vary).

```sh
rav@novascotia:~/TA/dADS2-2016$ ./grading -d
[2016-04-29 08:29:42,808 INFO] Refresh gradebook
[2016-04-29 08:29:43,189 INFO] Sending login details to WAYF
[2016-04-29 08:29:43,529 DEBUG] WAYF login -> https://wayf.au.dk/module.php/core/loginuserpass.php?AuthState=...
[2016-04-29 08:29:43,530 DEBUG] WAYF response 200
[2016-04-29 08:29:43,538 DEBUG] Response page form has 1 inputs
[2016-04-29 08:29:43,622 DEBUG] Hidden form 1 -> 200 https://wayf.wayf.dk/module.php/saml/sp/saml2-acs.php/wayf.wayf.dk
[2016-04-29 08:29:43,630 DEBUG] Response page form has 2 inputs
[2016-04-29 08:29:44,258 DEBUG] Hidden form 2 -> 200 https://bb.au.dk/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_1_1
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


## Implementation

Python module to access the BlackBoard installation at Aarhus University
from the command line.

Useful for teaching assistants and teachers who wish to automate the BlackBoard
tedium.

Uses the following 3rd party modules:

* requests (HTTP client for Python 2/3)
* html5lib (to parse and query HTML)
* keyring (to store your BlackBoard password)
* [html2text](https://github.com/Alir3z4/html2text) (to convert HTML forum posts to Markdown)
* six (bridges incompatibilities between Python 2 and 3)

Install with `pip install -r requirements.txt`.

To find the course id to pass to `--course`,
inspect the course URL. If it looks like:

`https://bb.au.dk/webapps/blackboard/execute/content/blankPage?cmd=view&content_id=_347138_1&course_id=_43290_1`

then the course id is `_43290_1`.
