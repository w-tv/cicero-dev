#!/usr/bin/env -S streamlit run
"""This shows you the top of the activity log, to make sure things are going through."""
import streamlit as st
from cicero_shared import sql_call, sql_call_cacheless

st.button("Refresh the page", help="Clicking this button will do nothing, but it will refresh the page, which is sometimes useful if this page loaded before the activity log was written to, and you want to see the new data in the activity log.")
results = sql_call_cacheless("SELECT * FROM cicero.default.activity_log ORDER BY timestamp DESC LIMIT 20")
column_names = {str(i): k for i, k in enumerate(results[0].asDict())}
st.dataframe(results, column_config=column_names)

st.caption("Use of similarity search backup:")
st.line_chart({r.timestamp: r.used_similarity_search_backup for r in results})

#todo: the use int index thing simplify this a little
#todo: also, it would be nice to have a point=True parameter in st.line_chart as well. I mean we don't use it now but it would be nice.
st.caption("Daily usages last 90 days (excludes `test@example.com` user):")
daily_usage = sql_call("""SELECT DATE(timestamp) AS d, COUNT(*) AS c FROM cicero.default.activity_log WHERE user_email != "test@example.com" AND DATE(timestamp) >= CURRENT_DATE() - INTERVAL 90 DAY GROUP BY d ORDER BY d DESC""")
st.bar_chart({d.d: d.c for d in daily_usage}) #trying to make the x-axis on this look good is probably not worth it.
