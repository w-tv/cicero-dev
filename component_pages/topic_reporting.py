#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks import sql
from collections.abc import Iterable
from typing import Any, Sequence
from .prompter import cicero_topics_to_user_facing_topic_dict, load_account_names

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def to_sql_tuple_string(x: Sequence[str]):
  """SQL doesn't like the trailing comma python puts in a singleton tuple, so we can't just use the tuple constructor and then convert that to string; we have to do this instead."""
  if len(x) == 0:
    return "(NULL)" #this is a special case, because SQL doesn't like 'in ()' for some reason
  else:
    quoted = [f"'{x}'" for x in x]
    return f"({', '.join(quoted)})"

def bool_dict_to_string_list(dict_of_strings_to_bool: dict[str, bool]) -> list[str]:
  return [s for s, value in dict_of_strings_to_bool.items() if value]

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
  return (["all_hook"] if "All" in user_facing_topics else []) + [key+"_hook" for key, value in cicero_topics_to_user_facing_topic_dict.items() if value in user_facing_topics]

#In order to specify one of the colors (the only thing we really care about is Trump stuff being orange), you must specify all of the colors. These colors are taken from colors.png, by Alexander Chang.
internal_topics_to_colors = {
  "all_hook": "#61A5A2", #†
  "america_wrong_track_hook": "#658AB2",
  "announcement_hook": "#FDB0A1",
  "biden_hook": "#FB9A86",
  "biden_impeach_hook": "#F58271",
  "big_tech_hook": "#EF6862",
  "birthday_hook": "#E24F59",
  "bio_hook": "#FFF", #*
  "border_hook": "#CF3D54",
  "breaking_news_hook": "#B93154",
  "campaign_msg_hook": "#FFF021",
  "china_hook": "#F5E721",
  "climate_change_hook": "#000", #*
  "commie_hook": "#E3D321",
  "con_media_hook": "#DBC921",
  "contest_hook": "#DBC628",
  "control_of_congress_hook": "#CBB828",
  "control_of_wh_hook": "#C7BC42",
  "covid_hook": "#A69F56",
  "crime_hook": "#A6A633",
  "dc_state_hook": "#BDE4B2",
  "deadline_hook": "#85C37B",
  "deep_state_hook": "#5CA065",
  "dems_hook": "#407D56",
  "economy_hook": "#C2E1F3",
  "education_hook": "#ABD1E9",
  "election_integrity_hook": "#95BFDD",
  "endorse_for_principal_hook": "#888", #* (!!!! "for"?!)
  "endorse_from_donor_hook": "#83AECF",
  "endorse_from_principal_hook": "#729DC2",
  "energy_hook": "#628CB4",
  "event_debate_hook": "#547DA4",
  "event_speech_hook": "#466D93",
  "faith_hook": "#4F60C7",
  "ga_runoff_hook": "#444", #*
  "gender_hook": "#6B55DB",
  "gop_hook": "#BBB", #*
  "hamas_hook": "#8D4EE6",
  "iran_hook": "#A547F6",
  "israel_hook": "#C839F0",
  "main_media_hook": "#8D648A",
  "matching_hook": "#916990",
  "membership_hook": "#966F96",
  "merch_book_hook": "#B8A", #*
  "merch_koozie_hook": "#B8F", #*
  "merch_mug_hook": "#B587AA",
  "merch_ornament_hook": "#BAA", #*
  "merch_shirt_hook": "#D8A", #*
  "merch_sticker_hook": "#D1A4C1",
  "merch_wrapping_paper_hook": "#D8F", #*
  "military_hook": "#E4BCD8",
  "murica_hook": "#F0D0E8",
  "n_korea_hook": "#DADADA",
  "nat_sec_hook": "#CDCFCE",
  "non_trump_maga_hook": "#BFC2C2",
  "parental_rights_hook": "#ABA", #*
  "pro_life_hook": "#A5ABAD",
  "race_update_hook": "#97A0A4",
  "radical_judge_hook": "#8B959A",
  "russia_hook": "#7F8A91",
  "scotus_hook": "#757E88",
  "sec_amend_hook": "#6B747D",
  "sotu_hook": "#FF0", #*
  "swamp_hook": "#616873",
  "t_af_hook": "#F9BD74", #†
  "t_arrest_hook": "#F6AB57",
  "t_contest_hook": "#F49648", #†
  "t_djt_hook": "#F49D70",
  "t_maga_hook": "#EF823D", #†
  "t_mal_raid_hook": "#E1743D", #†
  "t_pro_hook": "#CF693F",
  "t_supporter_hook": "#BD6040", #†
  "t_witchhunt_hook": "#AB563F", #†
  "ukraine_hook": "#0056B9", #this was "616873", a dark gray, in colors.png, but I changed it to be the blue color of the Ukrainian flag ( #0056B9, "Strong azure"; per https://en.wikipedia.org/wiki/Flag_of_Ukraine#Design )
} #* = colors.png didn't have this, so, uh, whatever, I just picked a color, a three-digit one. #† = color.png had this entry but the cicero internal topics names dict initially did not.

def main() -> None:
  """This page performs a peculiar task known as "topic reporting", which is basically just summary statistics about various topic keywords (internally called "hooks").

  You must have streamlit installed to run this program. This script is usually run as part of Cicero run.bat in the main folder.

  List of derived quantities, left to right (does not include "topic", which is also there, but not derived per se):
    TV Funds: SUM of TV Funds
    FPM ($): SUM([TV_FUNDS]) / SUM([SENT]) * 1000
    ROAS (%): SUM([TV_FUNDS]) / SUM([SPEND_AMOUNT]) PERCENT
    Sent: SUM of Sent
    Result_Count: Count Distinct of Result Name
  """
  topics_internal = ["all_hook"]+[ x+"_hook" for x in cicero_topics_to_user_facing_topic_dict.keys() ] #these are slightly different than the input topics for Cicero ahaha (joker laugh)
  topics_external = ["All"]+list(cicero_topics_to_user_facing_topic_dict.values())


  topics_gigaselect = {}
  # This version does not actually display right, but I might want to go back to it.
  """
  topic_check_cols = st.columns(len(topics_internal)*2)
  for i, col in enumerate(topic_check_cols[::2]): #In even cols, including 0, put a color square
    with col:
      m = st.markdown(f' <div style="color:{list(internal_topics_to_colors.values())[i]}">&#9632;</div>', unsafe_allow_html=True)
  for i, col in enumerate(topic_check_cols[1::2]): #In odd cols, put a checkbox control (this includes the final col, because of 0-indexing)
    with col:
      t = list(internal_topics_to_colors.keys())[i]
      topics_gigaselect[t] = st.checkbox(t)
"""
  topic_check_cols = st.columns(len(topics_internal)//14 + 1) #the items per column is chosen arbitrarily to kind of be good.
  for i, t in enumerate(topics_internal): #In even cols, including 0, put a color square
    with topic_check_cols[i//14]:
      col1, col2 = st.columns([0.1, 0.9])
      with col1:
        m = st.markdown(f' <div style="color:{list(internal_topics_to_colors.values())[i]}">&#9632;</div>', unsafe_allow_html=True)
      with col2:
        t = list(internal_topics_to_colors.keys())[i]
        topics_gigaselect[t] = st.checkbox(t, value=True)

  col1, col2, col3, col4, col5 = st.columns(5) #possibly refactor this into non-unpacking for-loop type thing if I need to keep editing it.
  with col1:
    past_days = st.radio("Date range", [1, 7, 14, 30], index=1, format_func=lambda x: "Yesterday" if x == 1 else f"Last {x} days", help="The date range from which to display data. This will display data from any calendar day greater than or equal to (the present day minus the number of days specified). That is, 'Yesterday' will display data from both yesterday and today (and possibly, in rare circumstances, from the future).\n\nThis control only controls the top graph, and is never applied to the bottom graph.")
  with col2:
    accounts = st.multiselect("Account", ["(all)"]+load_account_names(), default="(all)", help="This control allows you to filter on the account name. If '(all)' is one of the selected values, all of the accounts will be presented.")
    #TODO: external name to internal names mapping
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
  summary_data_per_topic = sql_call(f"""WITH stats(topic, funds, sent, spend, result_count) AS (SELECT Hooks, SUM(TV_FUNDS), SUM(SENT), SUM(SPEND_AMOUNT), COUNT(DISTINCT RESULT_NAME) FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and {hp_string} and {askgoal_string} and SEND_DATE >= NOW() - INTERVAL {past_days} DAY and Hooks in {to_sql_tuple_string(bool_dict_to_string_list(topics_gigaselect))} and Hook_Bool=true GROUP BY Hooks) SELECT topic, funds, try_divide(funds, sent)*1000, try_divide(funds, spend)*100, sent, result_count from stats""") #this is, basically, the entirety of what we need to do the thing

  # TODO: use the topic display name to internal topic name mapping in the big dict , to display the human-readable topic names to the user. Also the colors, I suppose. # One of these days I think we're going to change the topic names internally to human-readable names, anyway.
  # TODO: match the colors

  key_of_rows = ("Topic", "Funds", "FPM ($)", "ROAS (%)", "Sent", "Result count")

  dicted_rows = {key_of_rows[i]: [row[i] for row in summary_data_per_topic] for i, key in enumerate(key_of_rows)} #various formats probably work for this; this is just one of them.
  dicted_rows["color"] = [internal_topics_to_colors[key] for key in dicted_rows["Topic"]] #special... "wide format" hack.
  if len(summary_data_per_topic):
    chart = alt.Chart(pd.DataFrame(dicted_rows)).mark_circle().encode(alt.X("ROAS (%)"), alt.Y("FPM ($)"), alt.Color("color", legend=None), tooltip=key_of_rows)
    st.altair_chart(chart, use_container_width=True)
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")



  # Behold! Day (x) vs TV funds (y) line graph, per selected topic, which is what we decided was the only other important graph to keep from the old topic reporting application.
  topics = st.multiselect("Topics", topics_external, default="All", help="This control filters the below graph to only include results that have the selected topic.  If 'All' is one of the selected values, an aggregate sum of all the topics will be presented, as well.")
  topics = inverse_topic_dict_lookup_list_mapping_hook_mode(topics)
  search = st.text_input("Search", help="This box, if filled in, makes the below graph only include results that have text (in the clean_text/clean_email field, depending on project type selected above) matching the contents of this box, as a regex (python flavor; see https://regex101.com/?flavor=python&regex=biden|trump&flags=gm&testString=example%20non-matching%20text%0Asome%20trump%20stuff%0Abiden!%0Atrumpbiden for more details and to experiment interactively.") #TODO: implement. Might have to use SQL regex instead...
  day_data_per_topic = sql_call(f"""WITH stats(date, funds, topic) AS (SELECT SEND_DATE, SUM(TV_FUNDS), Hooks FROM hook_reporting.default.hook_data_prod WHERE PROJECT_TYPE like '{project_type}%' and account_name in {to_sql_tuple_string(accounts)} and hooks in {to_sql_tuple_string(topics)} and {hp_string} and GOAL="Fundraising" and Hook_Bool=true GROUP BY SEND_DATE, Hooks) SELECT date, funds, topic from stats""")
  if len(day_data_per_topic):
    st.line_chart(to_graphable_dict(day_data_per_topic, "Day", "Funds ($)", "Topic"), x='Day', y='Funds ($)', color='Topic')
  else:
    st.info("No data points are selected by the values indicated by the controls. Therefore, there is nothing to graph. Please broaden your criteria.")
if __name__ == "__main__": main()
