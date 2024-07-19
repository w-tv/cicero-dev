#!/usr/bin/env -S streamlit run
""" This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call_cacheless

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
st.write("""TODO:

  page that will let us:
  
  * add account(s) and rollup name(s)
  * add a bio (corresponding to a rollup name)
  * add/remove client from the account list dropdown — and maybe some other stuff if you can think of anything"""
)
_ = """
column_config = {1: "Timestamp",
                 2: "User Email",
                 3: "User Pod",
                 4: "Prompter/Chatbot",
                 5: "Prompt Sent",
                 6: "Response Given",
                 7: "Model Name",
                 8: "Model URL",
                 9: "Model Parameters",
                 10: "System Prompt",
                 11: "Base URL",
                 12: "User Feedback"}
st.dataframe(sql_call_cacheless("SELECT * FROM cicero.default.activity_log ORDER BY timestamp DESC LIMIT 20"), column_config=column_config)"""
