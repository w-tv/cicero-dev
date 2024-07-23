#!/usr/bin/env -S streamlit run
""" This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call_cacheless

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
results = sql_call_cacheless("SELECT * FROM cicero.default.activity_log ORDER BY timestamp DESC LIMIT 20")
column_names = {i+1: k for i, k in enumerate(results[0].asDict())}
st.dataframe(results, column_config=column_names)
