#!/usr/bin/env -S streamlit run
"""It's useless to run this stand-alone. But I guess you can."""

from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from databricks.sql.types import Row as Row
import streamlit as st
from typing import Any, NoReturn, TypedDict

def exit_error(exit_code: int) -> NoReturn:
  st.write("*Ego vero consisto. Accede, veterane, et, si hoc saltim potes recte facere, incide cervicem.*")
  exit(exit_code)

@st.experimental_dialog("Database error") #type: ignore[attr-defined] # STREAMLIT-BUG-WORKAROUND: https://github.com/streamlit/streamlit/issues/8712
def die_with_database_error_popup(e_args: tuple[Any, ...]) -> NoReturn:
  print("Database error", e_args)
  st.write("There was a database error, and the application could not continue. Sorry.")
  st.code(e_args)
  exit_error(4)

@st.cache_data()
def sql_call(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """This is a wrapper function for sql_call_cacheless that *is* cached. See that other function for more information about the actual functionality."""
  return sql_call_cacheless(query, sql_params_dict)

def sql_call_cacheless(query: str, sql_params_dict:dict[str, Any]|None=None) -> list[Row]:
  """Make a call to the database, returning a list of Rows. The returned values within the Rows are usually str, but occasionally might be int (as when getting the count) or float or perhaps any of these https://docs.databricks.com/en/dev-tools/python-sql-connector.html#type-conversions"""
  # COULD: (but probably won't) there is a minor problem where we'd like to ensure that a query to a table x only occurs after a call to CREATE TABLE IF NOT EXISTS x (parameters of x). Technically, we could ensure this by creating a new function ensure_table(table_name, table_types) which then returns an TableEnsurance object, which then must be passed in as a parameter to SQL call. However, then we would want to check if it were the correct table (and possibly the right parameter types) which would greatly complicate the function signature of sql_call, because we'd have to pass the table name(s) in too, and then string-replace them into the query(?). So, doesn't seem worth it.
  try:
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(query, sql_params_dict).fetchall()
  except Exception as e:
    die_with_database_error_popup(e.args)

@st.cache_data()
def load_account_names() -> list[str]:
  return [row[0] for row in sql_call("SELECT * FROM cicero.default.client_list")]

def assert_always(x: Any, message_to_assert: str|None = None) -> None | NoReturn:
  """This function is equivalent to assert, but cannot be disabled by -O"""
  if not x:
    raise AssertionError(message_to_assert or x)
  return None

# This is the 'big' of topics, the authoritative record of various facts and mappings about topics.
Topics_Big_Payload = TypedDict("Topics_Big_Payload", {'color': str, 'internal name': str, 'show in prompter?': bool})
topics_big: dict[str, Topics_Big_Payload] = {
  'All': {'color': '#61A5A2', 'internal name': 'all', 'show in prompter?': False},
  "’murica": {'color': '#F0D0E8', 'internal name': 'murica', 'show in prompter?': True}, #for SQL syntax reasons, this has to be a typographic apostrophe instead of a straight apostrophe. (’ instead of ')
  '2A': {'color': '#6B747D', 'internal name': 'sec_amend', 'show in prompter?': True},
  'America Wrong Track': {'color': '#658AB2', 'internal name': 'america_wrong_track', 'show in prompter?': True},
  'Announcement': {'color': '#FDB0A1', 'internal name': 'announcement', 'show in prompter?': True},
  'Biden Impeachment': {'color': '#F58271', 'internal name': 'biden_impeach', 'show in prompter?': True},
  'Big Tech': {'color': '#EF6862', 'internal name': 'big_tech', 'show in prompter?': True},
  'Bio': {'color': '#FFF', 'internal name': 'bio', 'show in prompter?': True},
  'Birthday': {'color': '#E24F59', 'internal name': 'birthday', 'show in prompter?': True},
  'Border': {'color': '#CF3D54', 'internal name': 'border', 'show in prompter?': True},
  'Breaking News': {'color': '#B93154', 'internal name': 'breaking_news', 'show in prompter?': True},
  'Campaign Message / Memo': {'color': '#FFF021', 'internal name': 'campaign_msg', 'show in prompter?': True},
  'China': {'color': '#F5E721', 'internal name': 'china', 'show in prompter?': True},
  'Climate Change': {'color': '#000', 'internal name': 'climate_change', 'show in prompter?': True},
  'Communism / Socialism': {'color': '#E3D321', 'internal name': 'commie', 'show in prompter?': True},
  'Contest': {'color': '#DBC628', 'internal name': 'contest', 'show in prompter?': True},
  'Control of Congress': {'color': '#CBB828', 'internal name': 'control_of_congress', 'show in prompter?': True},
  'Control of WH': {'color': '#C7BC42', 'internal name': 'control_of_wh', 'show in prompter?': True},
  'Covid': {'color': '#A69F56', 'internal name': 'covid', 'show in prompter?': True},
  'Crime': {'color': '#A6A633', 'internal name': 'crime', 'show in prompter?': True},
  'DC Statehood': {'color': '#BDE4B2', 'internal name': 'dc_state', 'show in prompter?': True},
  'Deadline': {'color': '#85C37B', 'internal name': 'deadline', 'show in prompter?': True},
  'Deep State / Corruption': {'color': '#5CA065', 'internal name': 'deep_state', 'show in prompter?': True},
  'Dems': {'color': '#407D56', 'internal name': 'dems', 'show in prompter?': True},
  'Donald Trump': {'color': '#F49D70', 'internal name': 't_djt', 'show in prompter?': True},
  'Education': {'color': '#ABD1E9', 'internal name': 'education', 'show in prompter?': True},
  'Election Integrity': {'color': '#95BFDD', 'internal name': 'election_integrity', 'show in prompter?': True},
  'Endorsement for Principal': {'color': '#888', 'internal name': 'endorse_for_principal', 'show in prompter?': True},
  'Endorsement from Donor': {'color': '#83AECF', 'internal name': 'endorse_from_donor', 'show in prompter?': True},
  'Endorsement from Principal': {'color': '#729DC2', 'internal name': 'endorse_from_principal', 'show in prompter?': True},
  'Energy / Oil': {'color': '#628CB4', 'internal name': 'energy', 'show in prompter?': True},
  'Event Debate': {'color': '#547DA4', 'internal name': 'event_debate', 'show in prompter?': True},
  'Event Speech / Rally': {'color': '#466D93', 'internal name': 'event_speech', 'show in prompter?': True},
  'Faith': {'color': '#4F60C7', 'internal name': 'faith', 'show in prompter?': True},
  'GA Runoff': {'color': '#444', 'internal name': 'ga_runoff', 'show in prompter?': True},
  'GOP': {'color': '#BBB', 'internal name': 'gop', 'show in prompter?': True},
  'Gender': {'color': '#6B55DB', 'internal name': 'gender', 'show in prompter?': True},
  'Hamas': {'color': '#8D4EE6', 'internal name': 'hamas', 'show in prompter?': True},
  'Iran': {'color': '#A547F6', 'internal name': 'iran', 'show in prompter?': True},
  'Israel': {'color': '#C839F0', 'internal name': 'israel', 'show in prompter?': True},
  'Joe Biden': {'color': '#FB9A86', 'internal name': 'biden', 'show in prompter?': True},
  'Matching': {'color': '#916990', 'internal name': 'matching', 'show in prompter?': True},
  'Media Conservative': {'color': '#DBC921', 'internal name': 'con_media', 'show in prompter?': True},
  'Media Mainstream': {'color': '#8D648A', 'internal name': 'main_media', 'show in prompter?': True},
  'Membership': {'color': '#966F96', 'internal name': 'membership', 'show in prompter?': True},
  'Merch Book': {'color': '#B8A', 'internal name': 'merch_book', 'show in prompter?': True},
  'Merch Koozie': {'color': '#B8F', 'internal name': 'merch_koozie', 'show in prompter?': True},
  'Merch Mug': {'color': '#B587AA', 'internal name': 'merch_mug', 'show in prompter?': True},
  'Merch Ornament': {'color': '#BAA', 'internal name': 'merch_ornament', 'show in prompter?': True},
  'Merch Shirt': {'color': '#D8A', 'internal name': 'merch_shirt', 'show in prompter?': True},
  'Merch Sticker': {'color': '#D1A4C1', 'internal name': 'merch_sticker', 'show in prompter?': True},
  'Merch Wrapping Paper': {'color': '#D8F', 'internal name': 'merch_wrapping_paper', 'show in prompter?': True},
  'Military': {'color': '#E4BCD8', 'internal name': 'military', 'show in prompter?': True},
  'National Security': {'color': '#CDCFCE', 'internal name': 'nat_sec', 'show in prompter?': True},
  'Non-Trump MAGA': {'color': '#BFC2C2', 'internal name': 'non_trump_maga', 'show in prompter?': True},
  'North Korea': {'color': '#DADADA', 'internal name': 'n_korea', 'show in prompter?': True},
  'Parental Rights': {'color': '#ABA', 'internal name': 'parental_rights', 'show in prompter?': True},
  'Pro-Life': {'color': '#A5ABAD', 'internal name': 'pro_life', 'show in prompter?': True},
  'Pro-Trump': {'color': '#CF693F', 'internal name': 't_pro', 'show in prompter?': True},
  'Race Update': {'color': '#97A0A4', 'internal name': 'race_update', 'show in prompter?': True},
  'Radical DAs / Judges': {'color': '#8B959A', 'internal name': 'radical_judge', 'show in prompter?': True},
  'Russia': {'color': '#7F8A91', 'internal name': 'russia', 'show in prompter?': True},
  'SCOTUS': {'color': '#757E88', 'internal name': 'scotus', 'show in prompter?': True},
  'State of the Union': {'color': '#FF0', 'internal name': 'sotu', 'show in prompter?': True},
  'Swamp': {'color': '#616873', 'internal name': 'swamp', 'show in prompter?': True},
  'Taxes / Economy': {'color': '#C2E1F3', 'internal name': 'economy', 'show in prompter?': True},
  'Trump America First': {'color': '#F9BD74', 'internal name': 't_af', 'show in prompter?': False},
  'Trump Arrest': {'color': '#F6AB57', 'internal name': 't_arrest', 'show in prompter?': True},
  'Trump Contest': {'color': '#F49648', 'internal name': 't_contest', 'show in prompter?': False},
  'Trump MAGA': {'color': '#EF823D', 'internal name': 't_maga', 'show in prompter?': False},
  'Trump Mar-a-Lago Raid': {'color': '#E1743D', 'internal name': 't_mal_raid', 'show in prompter?': False},
  'Trump Supporter': {'color': '#BD6040', 'internal name': 't_supporter', 'show in prompter?': False},
  'Trump Witchhunt': {'color': '#AB563F', 'internal name': 't_witchhunt', 'show in prompter?': False},
  'Ukraine': {'color': '#0056B9', 'internal name': 'ukraine', 'show in prompter?': True},
}
