#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks import sql
from collections.abc import Iterable
from typing import Any, Sequence
from .prompter import cicero_topics_to_user_facing_topic_dict, load_account_names

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

def to_graphable_dict(values: Sequence[Sequence[Any]], x:str='x', y:str='y', color:str='color') -> list[dict[str, Any]]:
  if len(values) == 3: #it's a 3-list of n-lists
    return [{x: values[0][i], y:values[1][i], color:values[2][i]} for i, _ in enumerate(values[0])]
  else:
    return [{x: value[0], y:value[1], color:value[2]} for value in values]

def inverse_topic_dict_lookup_list_mapping_hook_mode(user_facing_topics: list[str]) -> list[str]:
  return [key+"_hook" for key, value in cicero_topics_to_user_facing_topic_dict.items() if value in user_facing_topics]

def main() -> None:
  """
  This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords (internally called "hooks").

  You must have streamlit installed to run this program. This script is usually run as part of Cicero run.bat in the main folder.

  List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
    TV Funds: SUM of TV Funds
    FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
    ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
    Sent: SUM of Sent
    Result_Count: Count Distinct of Result Name
  """

  topics_internal = [ x+"_hook" for x in cicero_topics_to_user_facing_topic_dict.keys() ] #these are slightly different than the input to Cicero ahaha (joker laugh)
  topics_external = list(cicero_topics_to_user_facing_topic_dict.values())

  col1, col2, col3, col4, col5 = st.columns(5) #possibly refactor this into non-unpacking for-loop type thing if I need to keep editing it.
  with col1:
    past_days = st.radio("Date range", [1, 7, 14, 30], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).\n\nThis control only controls the top graph, and is never applied to the bottom graph.")
  with col2:
    accounts = st.multiselect("Account", ["(all)"]+load_account_names(), default="(all)", help="This control allows you to filter on the account name. If '(all)' is one of the selected values, all of the accounts will be presented.")
    if "(all)" in accounts:
      accounts = load_account_names()
  with col3:
    project_type = st.selectbox("Project Type", ["Both", "Text Message", "Email"], index=0, help="This control allows you to filter on the project type, between email and text message. If Both selected, no filtering will be done.\n\n Internally, the filtering is done based on whether the project_type begins with \"\", \"Text Message\", or \"Email\".")
    if project_type == "Both":
      project_type = "" # this should match anything.
  with col4:
    house_or_prospecting = st.selectbox("House or Prospecting?", ["Both", "House", "Prospecting"], help="This control allows you to filter on whether the list_name of the sent message contains \"House\" or not.")
    hp_string = {"Both": "true", "House": "list_name like '%House%'", "Prospecting": "list_name not like '%House%'"}[house_or_prospecting]
  with col5:
    askgoal = st.selectbox("Ask-Goal", ["Both", "Hard Ask", "Soft Ask"], help='This control allows you to filter on \"ask type\" which is basically how directly focused on fundraising the text was supposed to be. Hard is more and soft is less.\n\nThe internal logic is that "Both" is no filter, "Soft Ask" is (Goal = Fundraising AND Ask Type = Soft Ask) OR Goal = List Building, and "Hard Ask": Goal = Fundraising AND Ask Type != Soft Ask. (!= "Soft Ask" is the same a in ("Hard Ask", "Medium Ask"); except, it will also catch the values of null and None, which are sometimes in there.)')
    askgoal_string = {"Both": "true", "Hard Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE != 'Soft Ask'", "Soft Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE = 'Soft Ask' or GOAL = 'List Building'"}[askgoal]

  #To minimize RAM usage on the front end, most of the computation is done in the sql query, on the backend.
  #There's only really one complication to this data, which is that each row is duplicated n times — the "product" of the row and the list of hook types, as it were. Then only the true hooks have Hook_Bool true (all others have Hook_Bool null, which is our signal to ignore that row). This is just because it's easy to do a pivot table (or something) in Tableau that way; it doesn't actually matter. But we have to deal with it. It is also easy for us to deal with in SQL using WHERE Hook_Bool=true GROUP BY Hooks.
  summary_data_per_topic = sql_call(f"""WITH stats(topic, funds, sent, spend, result_count) AS (SELECT Hooks, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT RESULT_NAME) FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and {hp_string} and {askgoal_string} and SEND_DATE >= NOW() - INTERVAL {past_days} DAY and Hook_Bool=true GROUP BY Hooks) SELECT topic, funds, try_divide(funds, sent)*1000, try_divide(funds, spend)*100, sent, result_count from stats""") #this is, basically, the entirety of what we need to do the thing

  # TODO: use the topic display name to internal topic name mapping in the big dict , to display the human-readable topic names to the user. Also the colors, I suppose. # One of these days I think we're going to change the topic names internally to human-readable names, anyway.
  # TODO: display big topic color key to the left or above of the graph?

  key_of_rows = ("Topic", "Funds", "FPM ($)", "ROAS (%)", "Sent", "Result count")

  dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_topic] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
  if len(summary_data_per_topic):
    st.scatter_chart(dicted_rows, x="ROAS (%)", y="FPM ($)", color="Topic")
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")

  # Behold! Day (x) vs TV funds (y) line graph, per selected topic, which is what we decided was the only other important graph to keep from the old topic reporting application.
  topics = st.multiselect("Topics", ["All"]+topics_external, default="All", help="This control filters the below graph to only include results that have the selected topic.  If 'All' is one of the selected values, an aggregate sum of all the topics will be presented, as well.")
  topics = inverse_topic_dict_lookup_list_mapping_hook_mode(topics) + (["all_hook"] if "All" in topics else [])
  print(to_sql_tuple_string(topics))
  search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text/clean_email field, depending on project type selected above) matching the contents of this box, as a regex (python flavor; see https://regex101.com/?flavor=python&regex=biden|trump&flags=gm&testString=example%20non-matching%20text%0Asome%20trump%20stuff%0Abiden!%0Atrumpbiden for more details and to experiment interactively.") #TODO: implement. Might have to use SQL regex instead...
  day_data_per_topic = sql_call(f"""WITH stats(date, funds, topic) AS (SELECT SEND_DATE, SUM(TV_FUNDS), Hooks FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and hooks in {to_sql_tuple_string(topics)} and {hp_string} and GOAL="Fundraising" and Hook_Bool=true GROUP BY SEND_DATE, Hooks) SELECT date, funds, topic from stats""")
  if len(day_data_per_topic):
    st.line_chart(to_graphable_dict(day_data_per_topic, "Day", "Funds ($)", "Topic"), x='Day', y='Funds ($)', color='Topic')
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
if __name__ == "__main__": main()
