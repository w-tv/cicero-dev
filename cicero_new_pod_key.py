#!/usr/bin/env -S streamlit run
""" This is Cicero New Pod Key tab.
A tool for updating the list of which people are assigned to which pod, manually or with an xlsx.
You can also do most of this stuff in databricks using the sql query tool.
"""
import streamlit as st
from pandas import read_excel
from cicero_shared import sql_call_cacheless

def do_one(email: str, pod: str) -> None:
  """Because we need to update the value if it exists, and create a new record if none exist, this is an "upsert", and a MERGE INTO is apparently the best way to do it. Also I got almost all of this code from the AI. But it's very basic code, like example code of just how you would use MERGE INTO syntax, really. I just think it's interesting."""
  sql_call_cacheless("""
    MERGE INTO cicero.ref_tables.user_pods AS target
    USING (SELECT :email AS user_email, :pod AS user_pod) AS source
    ON target.user_email = source.user_email
    WHEN MATCHED THEN
        UPDATE SET user_pod = :pod
    WHEN NOT MATCHED THEN
        INSERT (       user_email,        user_pod, user_permitted_to_see_these_accounts_in_topic_reporting)
        VALUES (source.user_email, source.user_pod, ARRAY())
    """,
    locals()
  )

def to_sql_string_array_literal(x: list[str]) -> str:
  # databricks-sql-python-BUG-WORKAROUND: https://github.com/databricks/databricks-sql-python/issues/377 https://github.com/databricks/databricks-sql-python/issues/290
  quoted = [f"'{x}'" for x in x if x]
  return f"array({', '.join(quoted)})"

def do_one_tr(email: str, accounts: list[str]) -> None:
  """Because we need to update the value if it exists, and create a new record if none exist, this is an "upsert", and a MERGE INTO is apparently the best way to do it. Also I got almost all of this code from the AI. But it's very basic code, like example code of just how you would use MERGE INTO syntax, really. I just think it's interesting."""
  a = to_sql_string_array_literal(accounts)
  sql_call_cacheless(f"""
    MERGE INTO cicero.ref_tables.user_pods AS target
    USING (SELECT :email AS user_email, {a} AS user_permitted_to_see_these_accounts_in_topic_reporting) AS source
    ON target.user_email = source.user_email
    WHEN MATCHED THEN
        UPDATE SET user_permitted_to_see_these_accounts_in_topic_reporting = {a}
    WHEN NOT MATCHED THEN
        INSERT (       user_email,     user_pod, user_permitted_to_see_these_accounts_in_topic_reporting)
        VALUES (source.user_email, "Pod unknown", {a})
    """,
    {"email": email}
  )


st.warning("This page is an internal developer tool for Cicero. Also the controls aren't very self-explanatory.\n\nYou may also enjoy the song “Brand New Key” by Melanie Safka (RIP) https://www.youtube.com/watch?v=-mXlW9LytYo, although this will not help you use the tool in any way.")
st.write("## Concerning The Topic Reporting")
st.write("### Manual entry")
with st.form("form_pod_tr"):
  st.write("Here, you can manually update what accounts a user is allowed to see in the drop down of the topic reporting page. THEN GO SET THE POD VALUE IF YOU'RE MAKING A NEW PERSON.")
  c = st.columns(4)
  with c[0]:
    one_new_email_tr = st.text_input("one new email (tr)").strip()
  with c[1]:
    one_new_list = st.text_input("accounts (internal names) separated by `, `").strip().split(", ")
  with c[2]:
    st.caption("enticing button")
    if st.form_submit_button("input that one new email and accounts-list value...") and one_new_email_tr and one_new_list:
      do_one_tr(one_new_email_tr, one_new_list)

st.write("## Concerning The Pods")
st.write("This section contains controls for updating the pod table (listed below) and the activity log (listed even belower).\n\nThe pod table is consulted every time a user does a prompt and cicero thereby writes to the activity log.\n\nSo, the pod table controls what will appear in the pod column in activity log entries going forward for users.\n\nIf you've done something wrong previously, you might also want to update the activity log retroactively, to correct any erroneous pod listing you may have caused to exist in there.")

st.write("### Manual entry")
st.write("Here, you can manually update pod table values or activity log values, one user-pod association at a time. This is, by far, the most common way for us to make updates.")
c = st.columns(4)
with c[0]:
  one_new_email = st.text_input("one new email").strip()
with c[1]:
  one_new_pod = st.text_input("one new pod value").strip()
with c[2]:
  st.caption("enticing button")
  if st.button("input that one new email and pod value... just one") and one_new_email and one_new_pod:
    do_one(one_new_email, one_new_pod)
with c[3]:
  st.caption("enticing button 2")
  if st.button("update the activity log retroactively with that one new email and pod") and one_new_email and one_new_pod:
    sql_call_cacheless("UPDATE cicero.default.activity_log SET user_pod = :pod WHERE user_email ilike :email", {"email": one_new_email, "pod": one_new_pod})
st.write("#### Time-limited activity log updating")
st.caption("Want to update the pod value, and also the activity log but only *since* a certain date? No problem; fill out the date box here with the first date the change should affect (eg 2024-06-01) and then click the button below. The value of pod and email from the boxes above will be used. The date specified is included (using `>=`), as is every date up to and including the present, and also, if you think about it, the future.")
date_str = st.text_input("date since (inclusive)").strip()
if st.button("update the pod table and also the activity log retroactively IN A TIME-LIMITED MANNER with that one new email and pod") and one_new_email and one_new_pod:
  do_one(one_new_email, one_new_pod)
  #even though datetime is now a proper timestamp and not a string, this seems to work.
  sql_call_cacheless("UPDATE cicero.default.activity_log SET user_pod = :pod WHERE user_email ilike :email AND timestamp >= :date_str", {"email": one_new_email, "pod": one_new_pod, "date_str": date_str})

new_pods_tuples = None #avoid run-time variable-not-defined error. Obviously we could just put the buttons inside the file_uploader if, but I think it leads for better discoverability to do it this way.
st.write("### File entry")
if file := st.file_uploader("Here, you can pick a new pod key excel file. If you do so, you can use it to modify the pod table, using the controls also in this section."):
  new_pods_table = read_excel(file, header=None)
  new_pods_table_dict = new_pods_table.to_dict("records")
  new_pods_tuples = [(pair[0].lower(),pair[1]) for pair in new_pods_table_dict]
  st.write(new_pods_tuples)

if st.button("update the pod table results to match the file contents (will not delete pod table entries not spoken about in file)"):
  if new_pods_tuples:
    for t in new_pods_tuples:
      do_one(*t)
  else:
    st.error("*No file is selected, or perhaps I just don't recognize the format of the file.*")

if st.button("update the activity log retroactively to match the file contents"):
  if new_pods_tuples:
    for t in new_pods_tuples:
      sql_call_cacheless("UPDATE cicero.default.activity_log SET user_pod = :pod WHERE user_email ilike :email", {"email": t[0], "pod": t[1]})
  else:
    st.error("*No file is selected, or perhaps I just don't recognize the format of the file.*")

st.write("## Pod table")
st.info("This is the database table of user pods that Cicero currently uses. Remember: this section is completely collapsable in the user interface, if its huge size is visually distracting.")
sql_call_cacheless("CREATE TABLE IF NOT EXISTS cicero.ref_tables.user_pods (user_email string, user_pod string)")
pod_table_results = sql_call_cacheless("SELECT * FROM cicero.ref_tables.user_pods")
st.write(pod_table_results)

st.write("## Activity log (main, not chatbot)")
st.info("Here, you can see what pods users actually have in the activity log, in case you need to correct any mistakes of previous pod-assignment. Remember: this section is completely collapsable in the user interface, if its huge size is visually distracting.\n\nPlease note also that if a user has had multiple pod values over the course of time, you should expect to see multiple values for them in here (one for each different pod). These are in no particular order, so you might want to ctrl+f (although, beware the other table, the pod table above) which will also contain them!).")
st.write(f"""activity log entries where the pod is NULL, suggesting you need to run the retroactive application (above) if there are any: ***{sql_call_cacheless("SELECT count(*) FROM cicero.default.activity_log WHERE user_pod IS NULL")[0][0]}***""")
st.write(f"""activity log entries where the pod is "Pod unknown", suggesting you need to run the retroactive application (above) if there are any: ***{sql_call_cacheless("SELECT count( distinct user_email) FROM cicero.default.activity_log WHERE user_pod = 'Pod unknown'")[0][0]}***""")
activity_log_results = sql_call_cacheless("SELECT DISTINCT user_email, user_pod FROM cicero.default.activity_log")
activity_log_results_tuples = [(r[0].lower(),r[1]) for r in activity_log_results]
st.write(activity_log_results_tuples)
