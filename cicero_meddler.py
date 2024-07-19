#!/usr/bin/env -S streamlit run
""" This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call_cacheless

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
st.write("""TODO: page that will let us:
  * add rollup name(s)
  * add a bio (corresponding to a rollup name)
  * add/remove client from the account list dropdown — and maybe some other stuff if you can think of anything"""
)
with st.expander("Account names"):
  c = st.columns(2)
  with c[0]:
    acct = st.text_input("New account name").strip()
  with c[1]:
    #st.caption("")
    if st.button("Add the account name to the list of account names in the database") and acct:
      sql_call_cacheless("INSERT INTO cicero.default.client_list VALUES (:acct)", {"acct": acct}) # This is untested because I didn't want to mar the names. (:kongzi:)
  st.table(sql_call_cacheless("SELECT * FROM cicero.default.client_list ORDER BY account_name ASC"))
