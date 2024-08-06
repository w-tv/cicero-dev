#!/usr/bin/env -S streamlit run
"""Tests Cicero in some basic ways. It's just prompting right now. And a small subset of testing, at that!"""
from streamlit.testing.v1 import AppTest # I couldn't really get this to work, so I just test the prompting functionality.
print("Testing Cicero...")
at = AppTest.from_file("cicero.py", default_timeout=30).run()
at.selectbox[1].select_index(0).run()
assert not at.exception
at.text_input("word").input("Bazbat").run()
assert at.warning[0].value == "Try again."
