bbfetch changes
===============

0.3 (2017-xx-xx)
----------------

* Detect and handle the obscure Blackboard message
  "This attempt has not yet been submitted and is not available to view at present."
* Bugfix in `fetch_attempt`
* Fix dependency specification in `setup.py`
* Rename `blackboard` Python module to `bbfetch`

0.2 (2017-10-09)
----------------

* Fix login detection

0.1 (2017-10-02)
----------------

First release that can be installed with pip:

`pip install https://github.com/Mortal/bbfetch/archive/master.zip`

The following recent changes were made since 2017-09-18:

* Switch from html5lib 0.9999999 to 0.999999999.
  This is a breaking change, since html5lib changed its API
* Add `blackboard.backend.upload_csv()` to upload CSV file to Grade Centre
