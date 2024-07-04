#!/usr/bin/env -S streamlit run
""" This is a mostly-empty template for a tab/subpage of Cicero. It can also be run standalone using streamlit."""
import streamlit as st
from cicero_shared import sql_call_cacheless

def main() -> None:
  if st.session_state.get("activity_looker_enabled"):
    st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
    st.table(sql_call_cacheless("SELECT * FROM cicero.default.activity_log ORDER BY timestamp DESC LIMIT 20"))
  else:
    st.caption("To improve performance for the rest of the app, this functionality is disabled in a session by default. However, it can easily be enabled:")
    if st.button("Enable this feature for this session."):
      st.session_state["activity_looker_enabled"] = True
      st.rerun()
if __name__ == "__main__": main()
