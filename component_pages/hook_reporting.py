#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks import sql
from collections.abc import Iterable
from typing import Any, Sequence
from .prompter import cicero_topics_to_user_facing_topic_dict

def main() -> None:
  """
  This page performs a peculiar task known as "hook reporting", which is basically just summary statistics about various topic keywords.

  You must have streamlit installed to run this program. This script is usually run as part of Cicero run.bat in the main folder.

  List of derived quantities, left to right (does not include "hook":
    TV Funds: SUM of TV Funds
    FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
    ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
    Sent: SUM of Sent
    Result_Count: Count Distinct of Result Name
  """
  def to_sql_tuple_string(x: Sequence[str]):
    """SQL doesn't like the trailing comma python puts in a singleton tuple, so we can't just use the tuple constructor and then convert that to string; we have to do this instead."""
    if len(x) == 0: return "(NULL)" #this is a special case, because SQL doesn't like 'in ()' for some reason
    quoted = [f"'{x}'" for x in x]
    return f"({', '.join(quoted)})"
  @st.cache_data() # I decided to memoize this function primarily in order to make development of the graphing go more rapidly, but it's possible that this will cost us an unfortunate amount of RAM if maybe people use this page. So, removing this memoization is something to consider.
  def sql_call(query: str) -> list[str]: #possibly add a params dict param?
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query).fetchall()

  col1, col2, col3, col4, col5 = st.columns(5) #possibly refactor this into non-unpacking for-loop type thing if I need to keep editing it.
  with col1:
    past_days = st.radio("Date range", [1, 7, 14, 30], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).")
  #TODO: Ok, so, do we want the values in these other controls to be pulled from the table each time, or from a list somewhere in Cicero?
  with col2:
    account = st.multiselect("Account", ["dummy value"]) #TODO: populate with values, implement.
  with col3:
    project_types = st.multiselect("Project Type", ["dummy value", "Text Message: P2P Internal"]) #TODO: populate with values
  with col4:
    house_or_prospecting = st.selectbox("House or Prospecting?", ["Both", "House", "Prospecting"], help="This control allows you to select on whether or not the list_name of the sent message contains \"House\" or not.")
    hp_string = {"Both": "true", "House": "list_name like '%House%'", "Prospecting": "list_name not like '%House%'"}[house_or_prospecting]
  with col5:
    askgoal = st.selectbox("Ask-Goal", ["Both", "Hard Ask", "Soft Ask"], help='This control allows you to filter on \"ask type\" which is basically how directly focused on fundraising the text was supposed to be. Hard is more and soft is less.\n\nThe internal logic is that "Both" is no filter, "Soft Ask" is (Goal = Fundraising AND Ask Type = Soft Ask) OR Goal = List Building, and "Hard Ask": Goal = Fundraising AND Ask Type != Soft Ask. (!= "Soft Ask" is the same a in ("Hard Ask", "Medium Ask"); except, it will also catch the values of null and None, which are sometimes in there.)')
    askgoal_string = {"Both": "true", "Hard Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE != 'Soft Ask'", "Soft Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE = 'Soft Ask' or GOAL = 'List Building'"}[askgoal]

  #To minimize RAM usage on the front end, most of the computation is done in the sql query, on the backend.
  #There's only really one complication to this data, which is that each row is duplicated n times — the "product" of the row and the list of hook types, as it were. Then only the true hooks have Hook_Bool true (all others have Hook_Bool null, which is our signal to ignore that row). This is just because it's easy to do a pivot table (or something) in Tableau that way; it doesn't actually matter. But we have to deal with it. It is also easy for us to deal with in SQL using WHERE Hook_Bool=true GROUP BY Hooks.
  summary_data_per_hook = sql_call(f"""WITH stats(hook, funds, sent, spend, result_count) AS (SELECT Hooks, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT RESULT_NAME) FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE in {to_sql_tuple_string(project_types)} and {hp_string} and {askgoal_string} and SEND_DATE >= NOW() - INTERVAL {past_days} DAY and Hook_Bool=true GROUP BY Hooks) SELECT hook, funds, try_divide(funds, sent)*1000, try_divide(funds, spend)*100, sent, result_count from stats""") #this is, basically, the entirety of what we need to do the thing

  # I did a lot of crazy CONCAT and CAST logic in a previous version of this code, but this made everything into a string, and thus the graph used string-sorting order, ruining everything.

  # TODO: use the hook display name to hook table name mapping from the google sheet, or whatever. Also the colors, I suppose. # One of these days I think we're going to change the hook names to human-readable names, anyway.
  # TODO: display big hook color key to the left of the graph?

  key_of_rows = ("Hook", "Funds", "FPM ($)", "ROAS (%)", "Sent", "Result count")

  def to_graphable_dict(values: Sequence[Sequence[Any]], x:str='x', y:str='y', color:str='color') -> list[dict[str, Any]]:
    if len(values) == 3: #it's a 3-list of n-lists
      return [{x: values[0][i], y:values[1][i], color:values[2][i]} for i, _ in enumerate(values[0])]
    else:
      return [{x: value[0], y:value[1], color:value[2]} for value in values]

  dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_hook] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
  if len(summary_data_per_hook):
    st.scatter_chart(dicted_rows, x="ROAS (%)", y="FPM ($)", color="Hook")
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")

  # Behold! Day (x) vs TV funds (y) line graph, per selected hook, which is what we decided was the only other important graph to keep from the old hook reporting application.
  hook = st.multiselect("Hook", ["dummy value"]) #this only affects the graph below it!
  search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text/clean_email field, depending on project type selected above) matching the contents of this box, as a regex (python flavor; see https://regex101.com/?flavor=python&regex=biden|trump&flags=gm&testString=example%20non-matching%20text%0Asome%20trump%20stuff%0Abiden!%0Atrumpbiden for more details and to experiment interactively.")
  # TODO: project types that are texts start with "Text: " and project types that are email start with "Email: "; use this to filter, soon.
  days_per_hook = sql_call(f"""WITH stats(date, funds, hook) AS (SELECT SEND_DATE, SUM(TV_FUNDS), Hooks FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE in {to_sql_tuple_string(project_types)} and {hp_string} and GOAL="Fundraising" and Hook_Bool=true GROUP BY SEND_DATE, Hooks) SELECT date, funds, hook from stats""")
  st.line_chart(to_graphable_dict(days_per_hook, "Day", "Funds ($)", "Hook"), x='Day', y='Funds ($)', color='Hook')
if __name__ == "__main__": main()
