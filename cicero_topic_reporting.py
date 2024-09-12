#!/usr/bin/env -S streamlit run
"""This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords. To minimize RAM usage on the front end, most of the computation & filtering is done in the sql query, on the backend (nb: this is how SQL is supposed to be used).

List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
  TV Funds: SUM of TV Funds
  FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
  ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
  Sent: SUM of Sent
  Result_Count: Count Distinct of Result Name

  (Since FPM is Funds per mille, I think the symbol should be $‰, but Alex nixed this idea.) TODO: float this idea to others once Alex is gone.
"""
import streamlit as st
from typing import Sequence
from cicero_shared import dev_str, is_dev, load_account_names, sql_call, topics_big

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

def bool_dict_to_string_list(dict_of_strings_to_bool: dict[str, bool]) -> list[str]:
  return [s for s, value in dict_of_strings_to_bool.items() if value]

def to_graphable_dict[T](values: Sequence[Sequence[T]], x:str='x', y:str='y', color:str='color') -> list[dict[str, T]]:
  if len(values) == 3: #it's a 3-list of n-lists
    return [{x: values[0][i], y:values[1][i], color:values[2][i]} for i, _ in enumerate(values[0])]
  else:
    return [{x: value[0], y:value[1], color:value[2]} for value in values]

internal_account_name_to_external_account_name = {k: v for k, v in sql_call("SELECT account_name, rollup_name FROM cicero.ref_tables.ref_account_rollup WHERE visible_frontend SORT BY account_name ASC")} # many-to-one relationship of several internal names per one external name. This is what everyone at work calls a "rollup" (one of several sense of the word "rollup" that they use), apparently because many values are "rolled-up" into the few values.

def external_account_name_to_internal_account_names(external_account_name: str) -> list[str]:
  return [ian for ian, ean in internal_account_name_to_external_account_name.items() if ean == external_account_name]

def external_account_names_to_internal_account_names_list_mapping(external_account_names: list[str]) -> list[str]:
  return [ian for ean in external_account_names for ian in external_account_name_to_internal_account_names(ean)]

def permissible_account_names(user_email: str) -> list[str]:
  """Note that these should be the "external" names (the short and more user-friendly ones, which map to a number of internal projects (or whatever) run by those people (or however that works).
  Note that all users are always allowed to see the aggregate of all things, as permitted by the page logic (tho not explicitly addressed in this function) largely because we don't really care."""
  result = sql_call("FROM cicero.ref_tables.user_pods SELECT user_permitted_to_see_these_accounts_in_topic_reporting WHERE user_email = :user_email", locals())[0][0]
  return [r for r in result if isinstance(r, str)] if result is not None else [] # Unfortunately, it could be None, and thus not iterable, and the typechecker is no help here (since the database read loses type information). So, we have to do this awkward little dance.

def lowalph(s: str) -> str:
  """Given a string, return only its alphabetical characters, lowercased. This is especially useful when trying to string compare things that might have different punctuation. In our case, often en dashes vs hyphens."""
  return ''.join(filter(str.isalpha, s)).lower()

with st.expander("Topics..."):
  # Complicated logic just to have defaults and de/select all. Remember, the streamlit logic seems to be that the default value is overriden by user-selected values... unless the default value changes. Which makes sense, as these things go.
  # It's called an "opinion" and not a "state" because it doesn't directly mirror the state; it only changes when we need to change the state away from what the user has set. Thus, the program suddenly having an opinion about what should be selected, so to speak.
  #TODO: (semi-urgent) whatever I did here, it's slightly wrong, because uhh sometimes when the user selects something just now and then clicks a button, the button doesn't override it. But another click of a button does it. So, I have to re-read the streamlit docs about this, because I guess my mental model (or code) is wrong.
  topics_gigaselect_default_selected = ["America", "Biden", "Border", "Communist", "Control Of Congress", "Deadline", "Economy", "Election Integrity", "Faith", "Scotus"]
  cols = st.columns(3)
  with cols[0]:
    if st.button("Select All"):
      st.session_state["topics_gigaselect_opinion"] = {t: True for t in topics_big}
  with cols[1]:
    if st.button("Deselect All"):
      st.session_state["topics_gigaselect_opinion"] = {t: False for t in topics_big}
  with cols[2]:
    if st.button("Reset To Default Selection") or not st.session_state.get("topics_gigaselect_opinion"): # set the haver of opinions up by default
      st.session_state["topics_gigaselect_opinion"] = {t: (t in topics_gigaselect_default_selected) for t in topics_big}

  topics_gigaselect = {}
  topic_check_cols = st.columns(len(topics_big)//14 + 1) #the items per column is chosen arbitrarily to kind of be good.
  for i, t in enumerate(topics_big): #In even cols, including 0, put a color square
    with topic_check_cols[i//14]:
      col1, col2 = st.columns([0.1, 0.9])
      with col1:
        color_code = topics_big[t]["color"]
        st.markdown(f' <div style="color:{color_code}" title="{t}, {color_code}">&#9632;</div>', unsafe_allow_html=True)
      with col2:
        topics_gigaselect[t] = st.checkbox(t, value=st.session_state["topics_gigaselect_opinion"][t])

col1, col2, col3, col4 = st.columns(4)
with col1:
  past_days = st.radio("Date range", [1, 7, 14, 30, 180], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", horizontal=True, help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).")
with col2:
  permitted_accounts = load_account_names() if "everything" in permissible_account_names(st.session_state["email"]) else [ x for x in load_account_names() if lowalph(x) in map(lowalph, permissible_account_names(st.session_state["email"])) ]
  accounts = st.multiselect("Account", permitted_accounts, help=f"This control allows you to filter on the account name. If nothing is selected in this control all of the accounts will be presented (however, you will not be able to drill down on a topic without first selecting an account {dev_str('; unless you are in developer mode, which you are')}). Also, you must be individually permissioned for access to account names, so you may not have the ability to select additional ones.")
  accounts_string = "true" if not accounts else f"account_name in {to_sql_tuple_string(external_account_names_to_internal_account_names_list_mapping(accounts))}"
with col3:
  project_types = st.multiselect("Project Type", ["Text Message: P2P External", "Text Message: P2P Internal", "Text Message: SMS"], help="This control allows you to filter on the project type. If nothing is selected in this control, no filtering will be done.")
  project_types_string = "true" if not project_types else f"project_type in {to_sql_tuple_string(project_types)}"
with col4:
  askgoals = st.multiselect("Ask-Goal", ["Hard/Medium Ask", "Soft Ask/Listbuilding"], help='This control allows you to filter on \"ask type\" which is basically how directly focused on fundraising the text was supposed to be. Hard is more and soft is less.\n\nThe internal logic is: nothing selected is no filter; "Soft Ask/Listbuilding" is (Goal = Fundraising AND Ask Type = Soft Ask) OR Goal = List Building; and "Hard/Medium Ask" is Goal = Fundraising AND Ask Type != Soft Ask. (`!= "Soft Ask"` is the same as `in ("Hard Ask", "Medium Ask")` except it will also catch the values null and \'None\', which are sometimes also in there.)\n\nNotably: at the current moment, selecting both values in this control is the same as selecting no values.')
  askgoal = "Both" if len(askgoals)!=1 else askgoals[0] #We take a little shortcut here because both is the same as none in this one case.
  askgoal_string = {"Both": "true", "Hard/Medium Ask": "(GOAL = 'Fundraising' and FUNDRAISING_TYPE != 'Soft Ask)'", "Soft Ask/Listbuilding": "((GOAL = 'Fundraising' and FUNDRAISING_TYPE = 'Soft Ask') or GOAL = 'List Building')"}[askgoal]

topics = bool_dict_to_string_list(topics_gigaselect)
summary_data_per_topic = sql_call(f"""
  WITH stats(topic, funds, sent, spend, project_count) AS (
    SELECT topic_tag, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT PROJECT_NAME)
    FROM topic_reporting.default.gold_topic_data_array
    CROSS JOIN LATERAL explode(concat(array("All"), Topics_Array)) as t(topic_tag) -- this does, uh, the thing. it also adds the All pseudo-topic
    WHERE {project_types_string} and {accounts_string} and {askgoal_string} and SEND_DATE >= CURRENT_DATE() - INTERVAL {past_days} DAY and SEND_DATE <= CURRENT_DATE() and topic_tag in {to_sql_tuple_string(topics)}
    GROUP BY topic_tag
  )
  SELECT topic, funds, cast( try_divide(funds, sent)*1000*100 as int )/100, cast( try_divide(funds, spend)*100 as int ), project_count from stats
""")

key_of_rows = ("Topic", "TV Funds ($)", "FPM ($)", "ROAS (%)", "Project count")
dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_topic] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
dicted_rows["color"] = [tb["color"] for t in dicted_rows["Topic"] for name, tb in topics_big.items() if name == t]
#COULD: set up some kind of function for these that decreases the multiplier as the max gets bigger
fpm_max = max([val if val is not None else 0 for val in dicted_rows['FPM ($)']]) * 1.1 #TODO: fix iterable empty error here that occurs when you deselect all
roas_max = max([val if val is not None else 0 for val in dicted_rows['ROAS (%)']]) * 1.05
@st.fragment
def malarky() -> None:
  """This code displays a graph and lets the user select a point to drill down on its values. However, selecting the point reruns the page (this is unavoidable due to streamlit), and it seems like the way we get the points that go into this graph is a little unstable, so a rerun would often change the data slightly (order?) and change the colors of the graph and prevent the drilldown from appearing. So, we have to wrap it in a fragment. This is just another thing I hope to sort out in a refactor once the topic reporting is all moved over. TODO."""
  if len(summary_data_per_topic):
    single = alt.selection_point()
    chart = alt.Chart( pd.DataFrame( { key:pd.Series(value) for key, value in dicted_rows.items() } ) )\
      .mark_circle(size=400)\
      .encode(
        alt.X("ROAS (%)", scale=alt.Scale(domain=(0, roas_max))),
        alt.Y("FPM ($)", scale=alt.Scale(domain=(0, fpm_max))),
        alt.Color("Topic", scale=alt.Scale(domain=dicted_rows["Topic"], range=dicted_rows["color"]), legend=None), #todo: I don't think the current legend displays all the values, if more than about 13, because the text box for it is too small ¯\_(ツ)_/¯
        alt.Size(field="Project count", scale=alt.Scale(range=[150, 500]), legend=alt.Legend(title='Project Count', symbolFillColor='red', symbolStrokeColor='red')),
        opacity = alt.condition(single, alt.value(1.0), alt.value(0.4)),
        tooltip=key_of_rows
      ).add_params( single )
    event = st.altair_chart(chart, use_container_width=True, on_select="rerun")
    if "selection" in event and (is_dev() or len(accounts) == 1): #on click we "drill down"
      if len(event['selection']['param_1']) > 0:
        selected_topics = event['selection']['param_1'][0]['Topic']
        st.header(selected_topics.title())
        selected_topics_rows = sql_call(f"""SELECT {dev_str("account_name,")} project_name, send_date , project_type, sum(tv_funds) as tv_funds, clean_text FROM topic_reporting.default.gold_topic_data_array WHERE {project_types_string} and {accounts_string} and {askgoal_string} and SEND_DATE >= CURRENT_DATE() - INTERVAL {past_days} DAY and SEND_DATE <= CURRENT_DATE() and array_contains(topics_array, '{selected_topics}') GROUP BY {dev_str("account_name,")} project_name, send_date, project_type, clean_text""")
        column_names = {str(i): k for i, k in enumerate(selected_topics_rows[0].asDict())}
        st.dataframe(selected_topics_rows, column_config=column_names, use_container_width=True)
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
malarky()

# Behold! Day (x) vs TV funds / FPM / ROAS (y) line graphs, per selected topic
topics = st.multiselect("Topics", topics_big, default="All", help="This control filters the below graph to only include results that have the selected topic.  If 'All' is one of the selected values, an aggregate sum of all the topics will be presented, as well.")
# COULD: maybe have a radio button or something here that lets dev mode users switch between regex and contains
search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text or clean_email field) matching the contents of this box, case-insensitively. (If you enter text that doesn't match any text appearing anywhere then the below graph might become nonsensical.)")
if search:
  search_string = "(LOWER(clean_email) LIKE LOWER(CONCAT('%', :regexp, '%')) OR LOWER(clean_text) LIKE LOWER(CONCAT('%', :regexp, '%')))"
else:
  search_string = "true"

day_data_per_topic = sql_call(
  f"""
    WITH stats(date, funds, sent, spend, topic) AS (
      SELECT send_date, SUM(tv_funds), SUM(sent), SUM(spend_amount), topic_tag
      FROM topic_reporting.default.gold_topic_data_array
      CROSS JOIN LATERAL explode(concat(array("All"), Topics_Array)) as t(topic_tag)
      WHERE {project_types_string} AND {accounts_string} AND topic_tag IN {to_sql_tuple_string(topics)} AND {askgoal_string} AND send_date >= NOW() - INTERVAL {past_days} DAY AND send_date < NOW() AND {search_string}
      GROUP BY send_date, topic_tag
    )
    SELECT date, funds, CAST( TRY_DIVIDE(funds, sent)*1000*100 as INT )/100, CAST( TRY_DIVIDE(funds, spend)*100 as INT ), topic FROM stats
  """,
  {"regexp": search}
)

if len(day_data_per_topic):
  tv_funds_df = pd.DataFrame([(row[0], row[1], row[4]) for row in day_data_per_topic], columns=['Day', 'TV Funds ($)', 'Topic'])
  fpm_df = pd.DataFrame([(row[0], row[2], row[4]) for row in day_data_per_topic], columns=['Day', 'FPM ($)', 'Topic'])
  roas_df = pd.DataFrame([(row[0], row[3], row[4]) for row in day_data_per_topic], columns=['Day', 'ROAS (%)', 'Topic'])

  tv_funds_chart = alt.Chart(data=tv_funds_df).mark_line(size=5).encode(
    alt.X("Day"),
    alt.Y("TV Funds ($)"),
    alt.Color("Topic", legend=None)
  )

  fpm_chart = alt.Chart(data=fpm_df).mark_line(size=5).encode(
    alt.X("Day"),
    alt.Y("FPM ($)"),
    alt.Color("Topic", legend=None)
  )

  roas_chart = alt.Chart(data=roas_df).mark_line(size=5).encode(
    alt.X("Day"),
    alt.Y("ROAS (%)"),
    alt.Color("Topic", legend=None)
  )

  st.altair_chart(tv_funds_chart, use_container_width=True)
  st.altair_chart(fpm_chart, use_container_width=True)
  st.altair_chart(roas_chart, use_container_width=True)
else:
  st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
