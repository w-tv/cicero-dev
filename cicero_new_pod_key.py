#!/usr/bin/env -S streamlit run
""" This is Cicero New Pod Key tab.
A tool for updating the list of which people are assigned to which pod, manually or with an xlsx.
You can also do most of this stuff in databricks using the sql query tool.
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
  sql_call("DELETE FROM cicero.default.user_pods WHERE user_email ilike :email", keyword_arguments)
  sql_call("INSERT INTO cicero.default.user_pods (user_email, user_pod) VALUES (:email, :pod)", keyword_arguments)

def main() -> None:
  st.warning("This page is an internal developer tool for Cicero. Also the controls aren't very self-explanatory.\n\nYou may also enjoy the song “Brand New Key” by Melanie Safka (RIP) https://www.youtube.com/watch?v=-mXlW9LytYo, although this will not help you use the tool in any way.")

  st.write("## Meddle")
  st.write("This section contains controls for updating the pod table (listed below) and the activity log (listed even belower).\n\nThe pod table is consulted every time a user does a prompt and cicero thereby writes to the activity log.\n\nSo, the pod table controls what will appear in the pod column in activity log entries going forward for users.\n\nIf you've done something wrong previously, you might also want to update the activity log retroactively, to correct any erroneous pod listing you made have caused to exist in there.")

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
    if st.button("update the activity log with that one new email and pod") and one_new_email and one_new_pod:
      sql_call("UPDATE cicero.default.activity_log SET pod = :pod WHERE useremail ilike :email", {"email": one_new_email, "pod": one_new_pod})

  st.write("### File entry")
  if file := st.file_uploader("Here, you can pick a new pod key excel file. If you do so, you can use it to modify the pod table, using the controls also in this section."):
    new_pods_table = read_excel(file, header=None)
    new_pods_table_dict = new_pods_table.to_dict("records")
    new_pods_tuples = [(pair[0].lower(),pair[1]) for pair in new_pods_table_dict]
    st.write(new_pods_tuples)
  
  if st.button("update the pod table results to match the file contents (will not delete pod table entries not spoken about in file)"):
    for t in new_pods_tuples:
      do_one(*t)

  if st.button("update the activity log retroactively to match the file contents"):
    for t in new_pods_tuples:
      sql_call("UPDATE cicero.default.activity_log SET pod = :pod WHERE useremail ilike :email", {"email": t[0], "pod": t[1]})

  st.write("## Pod table")
  st.info("This is the database table of user pods that Cicero currently uses. Remember: this section is completely collapsable in the user interface, if its huge size is visually distracting.")
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.user_pods (user_email string, user_pod string)")
  pod_table_results = sql_call("SELECT * FROM cicero.default.user_pods")
  st.write(pod_table_results)

  st.write("## Activity log (main, not chatbot)")
  st.info("Here, you can see what pods users actually have in the activity log, in case you need to correct any mistakes of previous pod-assignment. Remember: this section is completely collapsable in the user interface, if its huge size is visually distracting.")
  st.write(f"""activity log entries where the pod is NULL, suggesting you need to run the retroactive application (above) if there are any: ***{sql_call("SELECT count(*) FROM cicero.default.activity_log WHERE pod IS NULL")[0][0]}***""")
  st.write(f"""activity log entries where the pod is "Pod unknown", suggesting you need to run the retroactive application (above) if there are any: ***{sql_call("SELECT count( distinct useremail) FROM cicero.default.activity_log WHERE pod = 'Pod unknown'")[0][0]}***""")
  activity_log_results = sql_call("SELECT DISTINCT useremail, pod FROM cicero.default.activity_log")
  activity_log_results_tuples = [(r[0].lower(),r[1]) for r in activity_log_results]
  st.write(activity_log_results_tuples)
if __name__ == "__main__": main()