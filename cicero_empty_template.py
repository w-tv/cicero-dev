#!/usr/bin/env -S streamlit run
""" This is a mostly-empty template for a tab/subpage of Cicero. It can also be run standalone using streamlit."""
import streamlit as st
from cicero_shared import sql_call

def main() -> None:
  pass
  if st.session_state.get("REPLACEME_enabled"):
    pass
  else:
    st.caption("To improve performance for the rest of the app, this functionality is disabled in a session by default. However, it can easily be enabled:")
    if st.button("Enable this feature for this session."):
      st.session_state["REPLACEME_enabled"] = True
      st.rerun()
  pass
if __name__ == "__main__": main()
