#!/usr/bin/env -S streamlit run
"""Tests Cicero in some basic ways. It's just prompting right now. And a small subset of testing, at that!"""
from streamlit.testing.v1 import AppTest
from pprint import pprint
#this is mostly just example code so far, but at least it seems to work
#next step is figuring out how to enter dev mode in this code, since those are some of the features we most want to test!
print("Testing Cicero...")
at = AppTest.from_file("cicero_prompter.py", default_timeout=30).run()
#these don't mean anything in terms of meaningful text cases, just example code:
at.selectbox[1].select_index(0).run()
pprint(at.session_state)
print(at.session_state.developer_mode)


assert not at.exception
at.session_state.developer_mode = True
pprint(at.session_state)
at.button("unlucky").run()
#at.button("Submit").run()
at.session_state.developer_mode = True
at.button("unlucky").click()
at.button("unlucky").click().run()
