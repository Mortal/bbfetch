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
