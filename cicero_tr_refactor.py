#!/usr/bin/env -S streamlit run
"""This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords (internally called "hooks").

List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
  TV Funds: SUM of TV Funds
  FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
  ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
  Sent: SUM of Sent
  Result_Count: Count Distinct of Result Name

  (Since FPM is Funds per mille, I think the symbol should be $‰, but Alex nixed this idea.)
"""
import streamlit as st
from typing import Sequence
from cicero_shared import dev_str, is_dev, load_account_names, sql_call

import pandas as pd
import altair as alt

def to_sql_tuple_string(x: Sequence[str]) -> str:
  """SQL doesn't like the trailing comma python puts in a singleton tuple, so we can't just use the tuple constructor and then convert that to string; we have to do this instead."""
  # databricks-sql-python-BUG-WORKAROUND: https://github.com/databricks/databricks-sql-python/issues/377 https://github.com/databricks/databricks-sql-python/issues/290
  if len(x) == 0:
    return "(NULL)" #this is a special case, because SQL doesn't like 'in ()' for some reason
  else:
    quoted = [f"'{x}'" for x in x]
    return f"({', '.join(quoted)})"

def permissible_account_names(user_email: str) -> list[str]:
  """Note that these should be the "external" names (the short and more user-friendly ones, which map to a number of internal projects (or whatever) run by those people (or however that works).
  Note that all users are always allowed to see the aggregate of all things, as permitted by the page logic (tho not explicitly addressed in this function) largely because we don't really care."""
  result = sql_call("FROM cicero.ref_tables.user_pods SELECT user_permitted_to_see_these_accounts_in_topic_reporting WHERE user_email = :user_email", locals())[0][0]
  return [r for r in result if isinstance(r, str)]

def lowalph(s: str) -> str:
  """Given a string, return only its alphabetical characters, lowercased. This is especially useful when trying to string compare things that might have different punctuation. In our case, often en dashes vs hpyhens."""
  return ''.join(filter(str.isalpha, s)).lower()

topics_table = sql_call("""select tag_name from cicero.ref_tables.ref_tags where visible_frontend = True """)
# st.dataframe(topics_table)

with st.expander("Topics..."):
  for i in topics_table:
    st.checkbox(label=i[0], value=i[0])


col1, col2, col3, col4 = st.columns(4) #possibly refactor this into non-unpacking for-loop type thing if I need to keep editing it.
with col1:
  past_days = st.radio("Date range", [1, 7, 14, 30, 180], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", horizontal=True, help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).")
with col2:
  permitted_accounts = load_account_names() if "everything" in permissible_account_names(st.session_state["email"]) else [ x for x in load_account_names() if lowalph(x) in map(lowalph, permissible_account_names(st.session_state["email"])) ]
  accounts = st.multiselect("Account", permitted_accounts, help=f"This control allows you to filter on the account name. If nothing is selected in this control all of the accounts will be presented (however, you will not be able to drill down on a topic without first selecting an account {dev_str('; unless you are in developer mode, which you are')}). Also, you must be individually permissioned for access to account names, so you may not have the ability to select additional ones.")
  accounts_string = "true" #if not accounts else f"account_name in {to_sql_tuple_string(external_account_names_to_internal_account_names_list_mapping(accounts))}"
with col3:
  project_types = st.multiselect("Project Type", ["Text Message: P2P External", "Text Message: P2P Internal", "Text Message: SMS"], help="This control allows you to filter on the project type. If nothing is selected in this control, no filtering will be done.")
  project_types_string = "true" if not project_types else f"project_type in {to_sql_tuple_string(project_types)}"
with col4:
  askgoals = st.multiselect("Ask-Goal", ["Hard/Medium Ask", "Soft Ask/Listbuilding"], help='This control allows you to filter on \"ask type\" which is basically how directly focused on fundraising the text was supposed to be. Hard is more and soft is less.\n\nThe internal logic is: nothing selected is no filter; "Soft Ask/Listbuilding" is (Goal = Fundraising AND Ask Type = Soft Ask) OR Goal = List Building; and "Hard/Medium Ask" is Goal = Fundraising AND Ask Type != Soft Ask. (`!= "Soft Ask"` is the same as `in ("Hard Ask", "Medium Ask")` except it will also catch the values null and \'None\', which are sometimes also in there.)\n\nNotably: at the current moment, selecting both values in this control is the same as selecting no values.')
  askgoal = "Both" if len(askgoals)!=1 else askgoals[0] #We take a little shortcut here because both is the same as none in this one case.
  askgoal_string = {"Both": "true", "Hard/Medium Ask": "GOAL = 'Fundraising' and FUNDRAISING_TYPE != 'Soft Ask'", "Soft Ask/Listbuilding": "GOAL = 'Fundraising' and FUNDRAISING_TYPE = 'Soft Ask' or GOAL = 'List Building'"}[askgoal]

# #To minimize RAM usage on the front end, most of the computation is done in the sql query, on the backend.
# #There's only really one complication to this data, which is that each row is duplicated n times — the "product" of the row and the list of hook types, as it were. Then only the true hooks have Hook_Bool true (all others have Hook_Bool null, which is our signal to ignore that row). This is just because it's easy to do a pivot table (or something) in Tableau that way; it doesn't actually matter. But we have to deal with it. It is also easy for us to deal with in SQL using WHERE Hook_Bool=true GROUP BY Hooks.
# topics = topics_table
# # TODO: refactor from pivoted version to non-pivoted, smaller table: hook_reporting.default.gold_topic_data_array
# summary_data_per_topic = sql_call(f"""WITH stats(topic, funds, sent, spend, project_count) AS (SELECT Hooks, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT PROJECT_NAME) FROM hook_reporting.default.gold_topic_data_pivot WHERE {project_types_string} and {accounts_string} and {askgoal_string} and SEND_DATE >= CURRENT_DATE() - INTERVAL {past_days} DAY and SEND_DATE <= CURRENT_DATE() and Hooks in {to_sql_tuple_string(topics)} and Hook_Bool=true GROUP BY Hooks) SELECT topic, funds, cast( try_divide(funds, sent)*1000*100 as int )/100, cast( try_divide(funds, spend)*100 as int ), project_count from stats""")
# if "all_hook" in topics: #This special case is just copy-pasted from above, with modifications, to make the all_hook (since the new table process has no all_hook in).
#   summary_data_per_topic += sql_call(f"""WITH stats(topic, funds, sent, spend, project_count) AS (SELECT "all_hook", SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT PROJECT_NAME) FROM hook_reporting.default.gold_topic_data_pivot WHERE {project_types_string} and {accounts_string} and {askgoal_string} and SEND_DATE >= CURRENT_DATE() - INTERVAL {past_days} DAY and SEND_DATE <= CURRENT_DATE()) SELECT topic, funds, cast( try_divide(funds, sent)*1000*100 as int )/100, cast( try_divide(funds, spend)*100 as int ), project_count from stats""") #TODO: handle (remove) the case where all_hook is 0, in this and the lower graph.
# key_of_rows = ("Topic", "TV Funds ($)", "FPM ($)", "ROAS (%)", "Project count")
# dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_topic] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
# dicted_rows["color"] = [tb["color"] for t in dicted_rows["Topic"] for _, tb in topics_big.items() if tb["internal name"] == t.removesuffix("_hook")] #COULD: one day revise the assumptions that necessitate this logic, which is really grody. #TODO: in some cases we get a "All arrays must be of the same length" error on this, but I'm pretty sure that's just a result of us being mid- topic-pivot.
# #COULD: set up some kind of function for these that decreases the multiplier as the max gets bigger
# fpm_max = max(dicted_rows['FPM ($)'] or [0]) * 1.1 # The `or [0]` clauses prevent a crash when fpm (for example) is empty. #TODO: are the lower graphs correct in this case? Probably not, since they show... any data at all? Honestly when we change this graphing code to not use dicted_rows it will probably be clearer what's going on.
# roas_max = max(dicted_rows['ROAS (%)'] or [0]) * 1.05
# @st.fragment
# def malarky() -> None:
#   """This code displays a graph and lets the user select a point to drill down on its values. However, selecting the point reruns the page (this is unavoidable due to streamlit), and it seems like the way we get the points that go into this graph is a little unstable, so a rerun would often change the data slightly (order?) and change the colors of the graph and prevent the drilldown from appearing. So, we have to wrap it in a fragment. This is just another thing I hope to sort out in a refactor once the topic reporting is all moved over."""
#   if len(summary_data_per_topic):
#     single = alt.selection_single()
#     chart = alt.Chart( pd.DataFrame( { key:pd.Series(value) for key, value in dicted_rows.items() } ) )\
#       .mark_circle(size=400)\
#       .encode(
#         alt.X("ROAS (%)", scale=alt.Scale(domain=(0, roas_max))), 
#         alt.Y("FPM ($)", scale=alt.Scale(domain=(0, fpm_max))), 
#         alt.Color("Topic", scale=alt.Scale(domain=dicted_rows["Topic"], range=dicted_rows["color"]), legend=None), #todo: I don't think the current legend displays all the values, if more than about 13, because the text box for it is too small ¯\_(ツ)_/¯
#         alt.Size(field="Project count", scale=alt.Scale(range=[150, 500]), legend=alt.Legend(title='Project Count', symbolFillColor='red', symbolStrokeColor='red')), #TODO: add a new column to dicted_rows to generate this legend, the thing is i want this to be dynamic, so we'll talk.
#         opacity = alt.condition(single, alt.value(1.0), alt.value(0.4)),
#         tooltip=key_of_rows
#       ).add_selection( single )
#     event = st.altair_chart(chart, use_container_width=True, on_select="rerun")
#     if "selection" in event and (is_dev() or len(accounts) == 1): #on click we "drill down"
#       if len(event['selection']['param_1']) > 0:
#         selected_topics = event['selection']['param_1'][0]['Topic']
#         st.header(selected_topics.title())
#         selected_topics_rows = sql_call(f"""SELECT {dev_str("account_name,")} project_name, send_date , project_type, sum(tv_funds) as tv_funds, clean_text FROM hook_reporting.default.gold_topic_data_array WHERE {project_types_string} and {accounts_string} and {askgoal_string} and SEND_DATE >= CURRENT_DATE() - INTERVAL {past_days} DAY and SEND_DATE <= CURRENT_DATE() and array_contains(topics_array, '{selected_topics}') GROUP BY {dev_str("account_name,")} project_name, send_date, project_type, clean_text""")
#         column_names = {str(i): k for i, k in enumerate(selected_topics_rows[0].asDict())}
#         st.dataframe(selected_topics_rows, column_config=column_names, use_container_width=True)
#   else:
#     st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
# malarky()

# # Behold! Day (x) vs TV funds (y) line graph, per selected topic, which is what we decided was the only other important graph to keep from the old topic reporting application.
# topics = st.multiselect("Topics", topics_big, default="All", help="This control filters the below graph to only include results that have the selected topic.  If 'All' is one of the selected values, an aggregate sum of all the topics will be presented, as well.")
# topics = external_topic_names_to_internal_hooks_list_mapping(topics)
# # TODO: change to just a simple, case-insensitve contains
# # COULD: maybe have a radio button or something here that lets dev mode users switch between regex and contains
# search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text or clean_email field) matching the contents of this box, as a regex (Java flavor regex; see https://regex101.com/?flavor=java&regex=biden|trump&flags=gm&testString=example%20non-matching%20text%0Asome%20trump%20stuff%0Abiden!%0Atrumpbiden for more details and to experiment interactively). This ***is*** case sensitive, and if you enter a regex that doesn't match any text appearing anywhere then the below graph might become nonsensical.") # Java flavor mentioned here: https://docs.databricks.com/en/sql/language-manual/functions/regexp.html # I've only seen the nonsensical graph (it's wrong axes) occur during testing, and haven't seen it in a while, but I guess it might still happen.
# if search:
#   search_string = "(clean_email regexp :regexp or clean_text regexp :regexp)"
# else:
#   search_string = "true"

# day_data_per_topic = sql_call(f"""WITH stats(date, funds, sent, spend, topic) AS (SELECT send_date, SUM(tv_funds), SUM(sent), SUM(spend_amount), hooks FROM hook_reporting.default.gold_topic_data_pivot WHERE {project_types_string} AND {accounts_string} AND hooks IN {to_sql_tuple_string(topics)} AND {askgoal_string} AND send_date >= NOW() - INTERVAL {past_days} DAY AND send_date < NOW() AND hook_bool=true AND {search_string} GROUP BY send_date, hooks) SELECT date, funds, CAST( TRY_DIVIDE(funds, sent)*1000*100 as INT )/100, CAST( TRY_DIVIDE(funds, spend)*100 as INT ), topic FROM stats""", {"regexp": search})
# if "all_hook" in topics: #This special case is just copy-pasted from above, with modifications, to make the all_hook (since the new table process has no all_hook in).
#   day_data_per_topic += sql_call(f"""WITH stats(date, funds, sent, spend, topic) AS (SELECT DISTINCT send_date, SUM(tv_funds), SUM(sent), SUM(spend_amount), 'all_hook' FROM hook_reporting.default.gold_topic_data_pivot WHERE {project_types_string} AND {accounts_string} AND {askgoal_string} AND send_date >= NOW() - INTERVAL {past_days} DAY AND send_date < NOW() AND {search_string} GROUP BY send_date) SELECT date, funds, CAST( TRY_DIVIDE(funds, sent)*1000*100 as INT )/100, CAST( TRY_DIVIDE(funds, spend)*100 as INT ), topic FROM stats""", {"regexp": search})

# if len(day_data_per_topic):
#   tv_funds_graph = [(row[0], row[1], row[4]) for row in day_data_per_topic]
#   fpm_graph = [(row[0], row[2], row[4]) for row in day_data_per_topic]
#   roas_graph = [(row[0], row[3], row[4]) for row in day_data_per_topic]
#   st.line_chart(to_graphable_dict(fpm_graph, "Day", "FPM ($)", "Topic"), x='Day', y='FPM ($)', color='Topic', height=500) #COULD: make colors match above. Not sure if it's important.
#   st.line_chart(to_graphable_dict(roas_graph, "Day", "ROAS (%)", "Topic"), x='Day', y='ROAS (%)', color='Topic', height=500) #COULD: make colors match above. Not sure if it's important.
#   st.line_chart(to_graphable_dict(tv_funds_graph, "Day", "TV Funds ($)", "Topic"), x='Day', y='TV Funds ($)', color='Topic', height=500) #COULD: make colors match above. Not sure if it's important.
# else:
#   st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")