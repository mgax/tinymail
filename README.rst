TinyMail
========

An IMAP mail client for the Mac. It's written in 100% Python within the
Cocoa environment (using PyObjC). Inspiration for TinyMail comes from
the `email-init`_ discussion and the `Letters.app`_ project.

.. _`email-init`: http://lists.ranchero.com/listinfo.cgi/email-init-ranchero.com
.. _`Letters.app`: http://github.com/ccgus/letters

Running
-------
Create a ``.tinymail`` folder in your home directory with mode
``0700``. Inside create a file named ``account.json`` that looks like
this::

    {"host": "mail.example.com",
     "login_name": "your-username",
     "login_pass": "j00r p455w0rd"}

Then build and run the project.

Status
------
At the moment it's a basic IMAP account browser, showing folders and
messages, read-only. Communication with the server is done in separate
threads.

Plans
-----
For the moment sending email is not a priority. I'd like to have solid
IMAP support first. Here's the current TODO list:

* unit tests for everything non-GUI
* local message cache
* managing unread status and flags
* uploading, deleting, copying messages

The name `tinymail` is temporary. Looking for a better name.
