#!/usr/bin/env -S streamlit run
"""This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call_cacheless, topics_big

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
st.write("""TODO: Figure out how to write the record hashes... then, sections that will let us:
  * add rollup name(s)
  * add a bio (corresponding to a rollup name) (internal or external?)
  * and maybe some other stuff if you can think of anything"""
)
with st.expander("Account (client) names w/ rollup"):
  with st.form("account_enter_rollup_thingy", clear_on_submit=True):
    c = st.columns(4)
    with c[0]:
      acct = st.text_input("New account name").strip()
    with c[1]:
      rollup = st.text_input("Rollup Name").strip()
    with c[2]:
      visible_frontend = st.checkbox("Visible_Frontend")
    with c[3]:
      if st.form_submit_button("Add a new account and rollup name to the ref_account_rollup table") and acct and rollup:
        sql_call_cacheless("INSERT INTO cicero.ref_tables.ref_account_rollup (account_name, rollup_name, visible_frontend, modified_datetime) VALUES (:acct, :rollup, :visible_frontend, NOW())", {"acct": acct, "rollup": rollup, "visible_frontend": visible_frontend})
      if st.form_submit_button("delete rows matching both name fields") and acct and rollup:
        sql_call_cacheless("DELETE FROM cicero.ref_tables.ref_account_rollup WHERE account_name=:acct AND rollup_name=:rollup", {"acct": acct, "rollup": rollup})
  st.table(sql_call_cacheless("SELECT account_name, rollup_name, visible_frontend FROM cicero.ref_tables.ref_account_rollup ORDER BY account_name ASC"))

with st.expander("Topics"):
  c = st.columns(2)
  with c[0]:
    st.write(topics_big)
  with c[1]:
    st.write(
      {"All":{ "color":"#61A5A2", "internal name":"all", "show in prompter?": False}} # We need to add this in bespoke.
      | # dict addition operator
      {external.title():{"color":color, "internal name":internal.removesuffix("_hook"), "visible_fronted": visible_frontend, "enabled": enabled} for external, internal, color, visible_frontend, enabled in sql_call_cacheless('select tag_name, tag_column_name, color, visible_frontend, enabled from cicero.ref_tables.ref_tags WHERE tag_type == "Topic" ORDER BY tag_name ASC')}
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

with st.expander("Misc"):
  st.write("Put code here to evaluate it and see what happens. (I'm not including an eval here because lol don't use eval.)")
