#!/usr/bin/env -S streamlit run
""" This is Cicero New Pod Key Standalone.
Assuming you have the rest of cicero installed, you should run this using uv run streamlit run cicero_new_pod_key_standalone.py
This entire file is not needed for cicero, but reacts to a situation in which my boss kept updating the list of which people are assigned to which pod, and giving it to me as an xlsx. This file does all the stuff to do that.
"""
import streamlit as st
cacheless = True #this can be set to false to make the page more responsive, but at the cost of data being outdated until you refresh.
if cacheless:
  from cicero_shared import sql_call_cacheless as sql_call
else:
  from cicero_shared import sql_call
from pandas import read_excel

def do_one(email: str, pod: str) -> None:
  keyword_arguments = locals() # This is a dict of the arguments passed to the function. It must be called at the top of the function, because if it is called later then it will list any other local variables as well.
  # DATABRICKS-SQL-CONNECTOR?-BUG-WORKAROUND I got some kind of crazy syntax error trying to do these in the same string. (Even though an analogous command works fine in the databricks query editor.)
  sql_call("""DELETE FROM cicero.default.user_pods WHERE user_email ilike %(email)s""", keyword_arguments)
  sql_call("""INSERT INTO cicero.default.user_pods (user_email, user_pod) VALUES (%(email)s, %(pod)s)""", keyword_arguments)

def main() -> None:
  st.set_page_config(layout="wide", page_title="Cicero", page_icon="favicon.png") # Use wide mode in Cicero, mostly so that results display more of their text by default. Also, set title and favicon. #NOTE: "`set_page_config()` can only be called once per app page, and must be called as the first Streamlit command in your script."

  st.write("## File entry")
  if file := st.file_uploader("Pick the new pod key excel file."):
    new_pods_table = read_excel(file, header=None)
    new_pods_table_dict = new_pods_table.to_dict("records")
    new_pods_tuples = [(pair[0].lower(),pair[1]) for pair in new_pods_table_dict]
    st.write(new_pods_tuples)

  st.write("## pod table")
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.user_pods (user_email string, user_pod string)")
  pod_table_results = sql_call("SELECT * FROM cicero.default.user_pods")
  st.write(pod_table_results)

  st.write("## meddle")

  if st.button("update the pod table results to match the file contents (will not delete pod table entries not spoken about in file)"):
    for t in new_pods_tuples:
      do_one(*t)

  st.write("🙜")

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
    if st.button("update the activity log with that one new email and pod") and one_new_email and one_new_pod:
      sql_call("UPDATE cicero.default.activity_log SET pod = %(pod)s WHERE useremail ilike %(email)s", {"email": one_new_email, "pod": one_new_pod})

  st.write("🙜")

  if st.button("update the activity log retroactively to match the file contents"):
    for t in new_pods_tuples:
      sql_call("UPDATE cicero.default.activity_log SET pod = %(pod)s WHERE useremail ilike %(email)s", {"email": t[0], "pod": t[1]})

  st.write("## activity log (main, not chatbot)")
  st.write(f"""activity log entries where the pod is NULL, suggesting you need to run the retroactive application (above) if there are any: ***{sql_call("SELECT count(*) FROM cicero.default.activity_log WHERE pod IS NULL")[0][0]}***""")
  st.write(f"""activity log entries where the pod is "Pod unknown", suggesting you need to run the retroactive application (above) if there are any: ***{sql_call("SELECT count( distinct useremail) FROM cicero.default.activity_log WHERE pod = 'Pod unknown'")[0][0]}***""")
  activity_log_results = sql_call("SELECT DISTINCT useremail, pod FROM cicero.default.activity_log")
  activity_log_results_tuples = [(r[0].lower(),r[1]) for r in activity_log_results]
  st.write(activity_log_results_tuples)
if __name__ == "__main__": main()