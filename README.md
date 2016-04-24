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


### Password security

This project uses the `keyring` 3rd party module from the Python package index (PyPI)
to store your login password to BlackBoard so you don't have to enter it every time.

Thus, your BlackBoard password will be accessible to all Python programs,
making it possible for anyone with access to your computer to read your
password. Keep your computer safe from malicious people!


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
