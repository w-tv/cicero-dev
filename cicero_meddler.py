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
  c = st.columns(3)
  with c[0]:
    acct = st.text_input("New account name").strip()
  with c[1]:
    rollup = st.text_input("Rollup Name").strip()
  with c[2]:
    #st.caption("")
    if st.button("Add a new account and rollup name to the ref_account_rollup table (DO NOT CLICK)") and acct and rollup:
      # this code definitely doesn't work
      sql_call_cacheless("INSERT INTO cicero.ref_tables.ref_account_rollup (ACCOUNT_NAME, ROLLUP_NAME) VALUES (acct, rollup)", {"acct": acct, "rollup": rollup}) # This is untested because I didn't want to mar the names. (:kongzi:)
  st.table(sql_call_cacheless("SELECT Account_Name, Rollup_Name FROM cicero.ref_tables.ref_account_rollup ORDER BY Account_Name ASC"))

# thanks for this, we gotta align the Visible_Frontend and Enabled columns with topic big
with st.expander("Topics"):
  c = st.columns(2)
  with c[0]:
    st.write(topics_big)
  with c[1]:
    st.write(
      {"All":{ "color":"#61A5A2", "internal name":"all", "show in prompter?": False}} # We need to add this in bespoke.
      | # dict addition operator "why did they need to use an existing symbol meant for something else when there is already a perfectly good addition operator symbol: '+'" - chang "because, of course, | is the perfectly good existing operator for or ;)" - wyatt
      {external.title():{"color":color.upper(), "internal name":internal.removesuffix("_hook"), "show in prompter?": True} for external, internal, color in sql_call_cacheless('select tag_name, tag_column_name, color from cicero.ref_tables.ref_tags WHERE tag_type == "Topic" ORDER BY tag_name ASC')} #TODO: Visible_Frontend and Enabled will presumably be useful some day, when we get around to making them not all false.
    )

with st.expander("Bios"):
  c = st.columns(3)
  with c[0]:
    bio_name = st.text_input("Candidate Rollup Name").strip()
  with c[1]:
    bio = st.text_input("Bio").strip()
  with c[2]:
    if st.button("Add a new bio to an existing rollup name in the cicero.ref_tables.ref_bios table (DO NOT CLICK)") and bio_name and bio:
      sql_call_cacheless("INSERT INTO cicero.ref_tables.ref_bios (Candidate, Bio) VALUES (acct, bio)", {"acct": bio_name, "bio": bio}) # This also probably does not work
  st.table(sql_call_cacheless("SELECT Candidate, Bio FROM cicero.ref_tables.ref_bios ORDER BY Candidate ASC"))
