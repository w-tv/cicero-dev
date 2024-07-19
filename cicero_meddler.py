#!/usr/bin/env -S streamlit run
""" This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call_cacheless, topics_big

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
st.write("""TODO: Figure out how to write the record hashes... then, sections that will let us:
  * add rollup name(s)
  * add a bio (corresponding to a rollup name) (internal or external?)
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

with st.expander("Rollup"):
  c = st.columns(2)
  with c[0]:
    st.write(r"¯\_(ツ)_/¯")
  with c[1]:
    st.write(r"¯\\\_(ツ)\_/¯")

with st.expander("Topics"):
  c = st.columns(2)
  with c[0]:
    st.write(topics_big)
  with c[1]:
    st.write(
      {"All":{ "color":"#61A5A2", "internal name":"all", "show in prompter?": False}} # We need to add this in bespoke.
      | # dict addition operator
      {external.title():{"color":color.upper(), "internal name":internal.removesuffix("_hook"), "show in prompter?": True} for external, internal, color in sql_call_cacheless('select tag_name, tag_column_name, color from cicero.ref_tables.ref_tags WHERE tag_type == "Topic" ORDER BY tag_name ASC')} #TODO: Visible_Frontend and Enabled will presumably be useful some day, when we get around to making them not all false.
    )
