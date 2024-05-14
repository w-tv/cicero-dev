#!/usr/bin/env -S streamlit run

"""Post hoc ergo prompter hoc?"""

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date
#COULD: use https://pypi.org/project/streamlit-profiler/ for profiling
from transformers import GenerationConfig
from typing import Iterable, TypedDict, TypeVar
from zoneinfo import ZoneInfo as z
from cicero_shared import assert_always, exit_error, sql_call, sql_call_cacheless, Row
import cicero_rag_only

from num2words import num2words
from itertools import chain, combinations
from functools import reduce
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatDatabricks
from langchain.schema.output_parser import StrOutputParser

import re
import random
from os import environ

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

def external_topic_names_to_internal_topic_names_list_mapping(external_topic_names: list[str]) -> list[str]:
  return [topics_big[e]["internal name"] for e in external_topic_names]

@st.cache_data()
def load_model_permissions(useremail: str) -> list[str]:
  results = sql_call("SELECT DISTINCT modelname FROM models.default.permissions WHERE useremail = :useremail", {'useremail': useremail})
  return [result[0].lower() for result in results]

def ensure_existence_of_activity_log() -> None:
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.activity_log (datetime string, useremail string, promptsent string, responsegiven string, modelparams string, modelname string, modelurl string, pod string)")

@st.cache_data() #STREAMLIT-BUG-WORKAROUND: Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
def count_from_activity_log_times_used_today(useremail: str) -> int: #this goes by whatever the datetime default timezone is because we don't expect the exact boundary to matter much.
  ensure_existence_of_activity_log()
  return int( sql_call(f"SELECT COUNT(*) FROM cicero.default.activity_log WHERE useremail = :useremail AND datetime LIKE '{date.today()}%%'", {'useremail': useremail})[0][0] )

def write_to_activity_log_table(datetime: str, useremail: str, promptsent: str, responsegiven: str, modelparams: str, modelname: str, modelurl: str) -> None:
  """Write the arguments into the activity_log table. If you change the arguments this function takes, you must change the sql_call in the function and in ensure_existence_of_activity_log. It wasn't worth generating them programmatically. (You must also change the caller function of this function, of course.)"""
  keyword_arguments = locals() # This is a dict of the arguments passed to the function. It must be called at the top of the function, because if it is called later then it will list any other local variables as well. (The docstring isn't included; I guess it's the __doc__ attribute of the enclosing function, not a local variable. <https://docs.python.org/3.11/glossary.html#term-docstring>)
  ensure_existence_of_activity_log()
  sql_call_cacheless(
    "WITH tmp(pod) AS (SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike :useremail)\
    INSERT INTO cicero.default.activity_log\
            ( datetime,  useremail,  promptsent,  responsegiven,  modelparams,  modelname,  modelurl,  pod)\
      SELECT :datetime, :useremail, :promptsent, :responsegiven, :modelparams, :modelname, :modelurl,  pod FROM tmp",
    keyword_arguments
  )

@st.cache_data()
def load_bios() -> dict[str, str]:
  return {row["candidate"]:row["bio"] for row in sql_call("SELECT candidate, bio FROM cicero.default.ref_bios")}

@st.cache_data()
def load_bio(candidate: str) -> str:
  return sql_call("SELECT bio FROM cicero.default.ref_bios WHERE candidate = :candidate", locals())[0][0]

@st.cache_data()
def load_account_names() -> list[str]:
  return [row[0] for row in sql_call("SELECT * FROM cicero.default.client_list")]

@st.cache_data()
def load_headlines(get_all: bool = False, past_days: int = 7) -> list[str]:
   # The (arbitrary) requirement is that we return results from the last 7 days by default.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.headline_log (datetime string, headline string)")
  results = sql_call(
    "SELECT headline FROM cicero.default.headline_log " +
    (f"WHERE datetime >= NOW() - INTERVAL {past_days} DAY " if not get_all else "") +
    "GROUP BY headline ORDER BY min(datetime) DESC"
  )
  return [result[0] for result in results]

#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
class PresetsPayload(TypedDict):
  temperature: float
  target_charcount_min: int
  target_charcount_max: int
  num_beams: int
  top_k: int
  top_p: float
  repetition_penalty: float
  no_repeat_ngram_size: int
  num_return_sequences: int
  early_stopping: bool
  do_sample: bool
  output_scores: bool
  model: str
  account: str | None
  ask_type: str
  tone: list[str]
  topics: list[str]
  additional_topics: str
  exact_match_query: str
  headline: str | None
  overdrive: bool
  exact_match: bool

presets: dict[str, PresetsPayload] = {
  "default": {
    "temperature": 0.7,
    "target_charcount_min": 80,
    "target_charcount_max": 160,
    "num_beams" : 1,
    "top_k" : 50,
    "top_p" : 1.0,
    "repetition_penalty" : 1.2,
    "no_repeat_ngram_size" : 4,
    "num_return_sequences" : 5,
    "early_stopping" : False,
    "do_sample" : True,
    "output_scores" : False,
    "model": "gpt-short-medium-long",
    "account" : None,
    "ask_type": "Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
    "exact_match_query": "",
    "headline": None,
    "overdrive": False,
    "exact_match": False
  },
}

def set_ui_to_preset(preset_name: str) -> None:
  preset = presets[preset_name]
  for key, value in preset.items():
    st.session_state[key] = value

def list_from_cicero_tone_format_to_human_format(l: list[str]) -> list[str]:
  return [x.replace("_", " ").title() for x in l]
def list_from_human_format_to_cicero_tone_format(l: list[str]) -> list[str]:
  return [x.replace(" ", "_").lower() for x in l]
def list_to_bracketeds_string(l: list[str]) -> str:
  return " ".join([f"[{i}]" for i in l])

def only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(l: list[str], s: str) -> list[str]: return [x for x in l if s.lower() in x.lower()]

def send(model_uri: str, databricks_token: str, data: dict[str, list[bool|str]], dummy: bool = False) -> list[str]:
  headers = {"Authorization": f"Bearer {databricks_token}", "Content-Type": "application/json"}
  data_json = json.dumps({"inputs": data}, allow_nan=True)
  if dummy: # If this is a dummy prompt, we're trying to wake up the endpoint, which means we don't want to wait for a response (the request *will* hold up the entire program unless you tell it to time out.)
    try: # When the dummy prompt fails (ie, the endpoint is waking up), it raises an exception, which is harmless except that it screws up the rest of the page render a bit sometimes, so we catch the error to suppress it.
      requests.request(method='POST', headers=headers, url=model_uri, data=data_json, timeout=1)
    except requests.exceptions.ReadTimeout as _e:
      pass
    return []
  response = requests.request(method='POST', headers=headers, url=model_uri, data=data_json)
  if response.status_code == 504:
    print("response.status_code == 504; we recursively call this until the machine wakes up...")
    return send(model_uri, databricks_token, data)
  elif response.status_code == 404 and response.json()["error_code"] == "RESOURCE_DOES_NOT_EXIST":
    raise Exception("Encountered 404 error \"RESOURCE_DOES_NOT_EXIST\" when trying to query the model. This usually means the model endpoint has been moved. Please contact the team in charge of model serving to rectify the situation.")
  elif response.status_code != 200:
    if response.json()["error_code"] == "BAD_REQUEST":
      raise Exception(response.json()["message"])
    else:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return [str(r) for r in response.json()["predictions"][0]["0"]] # This list comprehension is just for appeasing the type-checker.

class dbutils:
  """A fake version of dbutils, to make Wes' code work outside of databricks with minimal changes."""
  class widgets:
    @staticmethod
    def text(variable_name: str, default_value:str, description: str) -> None:
      st.session_state["fake_dbutils_"+variable_name] = st.text_input(label=description+f"({variable_name})", value=default_value)
    @staticmethod
    def get(variable_name: str) -> str:
      return st.session_state["fake_dbutils_"+variable_name]

def everything_from_wes() -> None:
  dbutils.widgets.text("score_threshold", "0.5", "Document Similarity Score Acceptance Threshold")
  dbutils.widgets.text("model_temp", "0.8", "Model Temperature")

  dbutils.widgets.text("doc_pool_size", "10", "Document Pool Size")
  dbutils.widgets.text("num_examples", "10", "Number of Documents to Use as Examples")
  dbutils.widgets.text("num_outputs", "5", "Number of Texts the Model Should Generate")
  dbutils.widgets.text("output_table_name", "models.lovelytics.gold_text_outputs", "Text Output Table Name")
  dbutils.widgets.text("ref_tag_name", "models.lovelytics.ref_tags", "Tags Table Name")
  dbutils.widgets.text("rag_output_table_name", "models.lovelytics.rag_outputs", "RAG Outputs Table Name")
  dbutils.widgets.text("primary_key", "PROJECT_NAME", "Index Table Primary Key Name")

  dbutils.widgets.text("topics", "", "Topics")
  dbutils.widgets.text("client", "", "Client/Account Name")
  dbutils.widgets.text("ask", "", "Ask Type")
  dbutils.widgets.text("tones", "", "Tones")
  dbutils.widgets.text("text_len", "", "Text Length")
  dbutils.widgets.text("use_bio", "True", "Include Bio Information")
  dbutils.widgets.text("headlines", "", "News Headlines")

  dbutils.widgets.text("topic_weight", "4", "Topic Filter Weight")
  dbutils.widgets.text("tone_weight", "1", "Tone Filter Weight")
  dbutils.widgets.text("client_weight", "6", "Client Filter Weight")
  dbutils.widgets.text("ask_weight", "2", "Ask Type Weight")
  dbutils.widgets.text("text_len_weight", "4", "Text Length Weight")

  score_threshold = float(dbutils.widgets.get("score_threshold"))
  model_temp = float(dbutils.widgets.get("model_temp"))

  doc_pool_size = int(dbutils.widgets.get("doc_pool_size"))
  num_examples = int(dbutils.widgets.get("num_examples"))
  num_outputs = int(dbutils.widgets.get("num_outputs"))
  output_table_name = dbutils.widgets.get("output_table_name")
  ref_tag_name = dbutils.widgets.get("ref_tag_name")
  rag_output_table_name = dbutils.widgets.get("rag_output_table_name")
  primary_key = dbutils.widgets.get("primary_key")

  topics = dbutils.widgets.get("topics").lower()
  client = dbutils.widgets.get("client")
  ask = dbutils.widgets.get("ask")
  tones = dbutils.widgets.get("tones").lower()
  text_len = dbutils.widgets.get("text_len")
  use_bio = bool(dbutils.widgets.get("use_bio"))
  headlines = dbutils.widgets.get("headlines")

  topic_weight = float(dbutils.widgets.get("topic_weight"))
  tone_weight = float(dbutils.widgets.get("tone_weight"))
  client_weight = float(dbutils.widgets.get("client_weight"))
  ask_weight = float(dbutils.widgets.get("ask_weight"))
  text_len_weight = float(dbutils.widgets.get("text_len_weight"))

  assert_always(num_examples <= doc_pool_size, "You can't ask to provide more examples than there are documents in the pool! Try again with a different value.")

  # Topics and tones are expected to be passed with a comma and space separating each item; e.g. topics = "a, b, c"
  topics_list = topics.split(", ") if topics else []
  tones_list = tones.split(", ") if tones else []

  # Create a target prompt that is used during the vector index similarity search to score retrieved texts.
  target_prompt = f"A {text_len} {ask} text message from {client}" + f" about {topics}"*bool(topics) + f" written with an emphasis on {tones}"*bool(tones)

  # Wes 6. Create All Possible Filter Combinations and Sort By Importance

  ### Tag importance from most important to least
  # Topics (Tp)
  # Account/Client Name (C)
  # Ask Type (A)
  # Tone (To)
  # Ask Length (L)
  ### Example Priority Ordering
  # Tp, C, A, To, L
  # Tp, C, A, To
  # Tp, C, A, L
  # Tp, C, A
  # Tp, C, To, L
  # Tp, C, To
  # Tp, C, L
  # Tp, C

  # Used to generate powersets of filters
  T = TypeVar('T') # Could: Changed in version 3.12: Syntactic support for generics is new in Python 3.12.
  def powerset(iterable: Iterable[T], start: int = 0) -> Iterable[tuple[T]]: #TODO: once the code is mostly working, muck about with this and its types. (Need the code to be working to make sure it continues to work after the transformations lol.)
    "powerset([1,2,3]) → () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    assert 0 <= start <= len(s) #TODO: is this check necessary? Or will it just return () in "bad" cases?
    return chain.from_iterable(combinations(s, r) for r in range(start, len(s)+1))

  # Generate the powersets (i.e. each combination of items) for both topics and tones
  # Normally, the set starts with length of 0, but for performance purposes either start with 1 or 0, depending on if the list is empty
  # e.g. the powerset of [a, b] would be [(), (a), (b), (a, b)] but by starting with length 1 we only need to consider [(a), (b), (a, b)]
  # We only start with length 0 if there are no topics or tones. This is to make sure we at least generate filter combinations using the other three filter types
  # The topic/tone combinations are joined together with (, .*){1,} which is a regex pattern that means
  # match at least one time the pattern of a comma and space followed by any character zero or more times
  # So a(, .*){1,}b would mean: in the search space look for a, then at least one or more characters, and then b
  # This would match the string a, b and a, c, d, e, f, g, b
  # And would not match the string acdb
  # ^(?=.*\btopic\b)(?=.*\btopic\b).*$ regex for matching
  topic_sets = [("topics", "(, .*){1,}".join(x), topic_weight * len(x)) for x in powerset(sorted(topics_list), start=min(1, len(topics_list)))]
  tone_sets = [("tones", "(, .*){1,}".join(x), tone_weight * len(x)) for x in powerset(sorted(tones_list), start=min(1, len(tones_list)))]
  combos = set()
  # Iterate through each pairing of topics and tones
  for tp in topic_sets:
      for to in tone_sets:
          # Generate every combination between client, ask type, text length, topic, and tone
          # This means that for each topic set and tone set, we're generating every possible combination between those and the client, ask, and length
          temp_arr = [("client", client, client_weight), ("ask", ask, ask_weight), ("text_len", text_len, text_len_weight)]
          # But only add the topics and tones if they exist i.e. are not an empty string
          if tp[-1] != 0:
              temp_arr.append(tp)
          if to[-1] != 0:
              temp_arr.append(to)
          # Then update the set of filter combinations. A set is used to remove any duplicate filter combinations
          # Note that each filter tag (e.g. client, a topic set) has it's own weight value that dictate the filter's importance
          # Higher weight filters will be used first
          # When the sets of all filters are generated, their combined weight is summed together using the reduce function
          combos.update((x, reduce(lambda a, b: a+b[2], x, 0))  if len(x) != 0 else (x, 0) for x in powerset(temp_arr))
  # Then, the filters are sorted by their weight in descending order
  # So higher weight filter combinations are first in the array which means any documents with those filters will be considered first
  combos = [{y[0]: y[1] for y in x[0]} for x in sorted(combos, key=lambda a: a[1], reverse=True)]

  # Wes 7. Find as Many Relevant Documents as Possible

  @st.cache_data()
  def read_output_table() -> list[Row]:
    return sql_call(f"SELECT * from {output_table_name}")

  text_rows = read_output_table()

  # results_found is a set of every primary key we've search so far
  # This is to prevent duplicate documents/texts from showing up
  results_found = set()
  # reference_texts will be a list of dictionaries containing example user prompts and assistant responses (i.e. the text messages)
  reference_texts = []
  for c in combos:
      results = [
        row[primary_key] for row in text_rows if # Only apply filters if they are present in the current filter combination.
          (row[primary_key] not in results_found                              )  and
          ("topics"   not in c    or    re.search(c["topics"], row["topics"]) )  and
          ("tones"    not in c    or    re.search(c["tones"], row["tones"])   )  and
          ("client"   not in c    or    c["client"] == row["Client_Name"]     )  and
          ("ask"      not in c    or    c["ask"] == row["Ask_Type"]           )  and
          ("text_len" not in c    or    c["text_len"] == row["Text_Length"]   )
      ]
      # If no results were found, move onto the next filter combination. Otherwise, continue the process of considering these candidate results.
      if not results:
        continue
      results_found.update(results) # add the found primary key values to the results_found set
      # TODO: Perform a similarity search using the target_prompt defined beforehand. Filter for / use only the results we found earlier in this current iteration.
      # TODO: Then add all results returned by the similarity search to the reference_texts list. But only if their similarity score is greater than the score_threshold parameter.
      if 0 != 0: #TODO: size of result here, then formatting
          reference_texts.extend({"prompt": "Please write me a" + x[0].split(":\n\n", 1)[0][1:], "text": x[0].split(":\n\n", 1)[1], "score": x[-1]} for x in vs_search["result"]["data_array"] if x[-1] > score_threshold)
      # If we've found at least the number of desired documents, exit the loop and take the first doc_pool_size number of texts. The beginning of the reference_texts array will contain the texts that match the most important filters and the highest similarity scores.
      if len(reference_texts) >= doc_pool_size:
          reference_texts = reference_texts[:doc_pool_size]
          break
  # print(reference_texts)
  reference_texts

  # Wes 8. Query Endpoints

  # Randomize the order of the example texts. Unclear if this actually helps. But maybe it prevents the model from learning any ordering pattern we didn't intend for it to learn
  texts_to_use = random.sample(reference_texts, k=min(num_examples, len(reference_texts)))
  # We reinsert and separate the found documents into two separate dictionaries. This makes it easier to assemble the RAG prompt and pass them as string format variables to langchain
  ms_prompts = {}
  ms_texts = {}
  for num, content in enumerate(texts_to_use):
    ms_prompts[f"example_{num + 1}_p"] = content["prompt"]
    ms_texts[f"example_{num + 1}_t"] = content["text"]

  ##### INSERT PROMPT HERE #####
  # Llama-3 Prompt Styling
  # Base beginning structure of the RAG prompt
  rag_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"

  # Define the system prompt
  sys_prompt = """You are an expert copywriter who specializes in writing text messages for conservative candidates in the United States of America. Do not start your message with 'Dear', 'Subject', or 'Hello'. Try to grab the reader's attention in the first line. Do not explicitly use language such as 'Donate now' or '[DONATE]', instead use language like 'Rush', 'Support', or 'Chip in'. Do not make up facts or statistics. Do not use emojis or hashtags in your messages. Do not exactly copy the example text messages. Write the exact number of text messages asked for."""
  # Add instructions on how long or short a text should be depending on the text length we want the model to generate
  # Add specificity of specific ask type of the text message too
  # Try to make the model understand that the outputs we specifically are asking for should be this length
  if text_len == "short":
      sys_prompt += f" Your short {ask} text messages should be less than 160 characters in length, use less than 35 words, and have less than 2 sentences."
  elif text_len == "medium-length":
      sys_prompt += f" Your medium-length {ask} text messages should be between 160 and 400 characters in length, use between 35 to 70 words, and have between 3 to 5 sentences."
  elif text_len == "long":
      sys_prompt += f" Your long {ask} text messages should be more than 400 characters in length, use more than 70 words, and have more than 6 sentences."
  # combined_dict stores all of the string format variables used in the prompt and their values
  combined_dict = {}
  # Add bio and headline information if those are available
  if use_bio and client:
      sys_prompt += f""" Here is important biographical information about the conservative candidate you are writing for: {load_bio(client)}"""
  if headlines:
      sys_prompt += f""" Here is/are news headline(s) you should reference in your text messages: {headlines}"""
  # Add system_prompt to combined_dict
  combined_dict["system_prompt"] = sys_prompt

  # Then for every example document, we add the corresponding assistant and user lines
  # Triple brackets are used so the actual key name in the ms_prompts and ms_texts dictionaries can be inserted dynamically while also keeping the curly braces in the final string
  # So for example, if k = "apples" f"I like to eat {{{k}}}" would return the string "I like to eat {apples}"
  for k in ms_prompts.keys():
    ok = k.rsplit("_", 1)[0] + "_t"
    rag_prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{{{k}}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{{{ok}}}<|eot_id|>"

  # Add in the final component of the RAG prompt where we pass in the prompt/question we want to send to the model
  rag_prompt += "<|start_header_id|>user<|end_header_id|>\n\n{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
  # Combine all of the dictionaries with the string format keys and values for langchain parameter passing usage
  combined_dict = combined_dict | ms_prompts | ms_texts

  # Create the question prompt and add it to the combined_dict dictionary
  combined_dict["question"] = f"Please write me {num2words(num_outputs)} {text_len} {ask} text message(s) from {client}" + bool(topics)*f" about {topics}" + bool(tones)*f" written with an emphasis on {tones}"

  ##### END PROMPT INSERTION #####
  # print(rag_prompt)

  # Create the prompt template using langchain's PromptTemplate
  # Tell it that the input variables it should expect is everything in our combined_dict dictionary
  prompt = PromptTemplate(
    input_variables=list(combined_dict.keys()),
    template=rag_prompt
  )

  # Estimate the number of tokens our prompt is
  # This is important for querying the Llama-2 model only since it has a limit of 4096 tokens for its input and output combined
  # e.g. if our input is 4000 tokens, then we can only have 96 tokens for the output
  token_count = len( prompt.format( **combined_dict ) ) // 3
  # see note about environ in rag_only
  environ['DATABRICKS_HOST'] = "https://"+st.secrets['DATABRICKS_SERVER_HOSTNAME']
  environ['DATABRICKS_TOKEN'] = st.secrets["databricks_api_token"]
  dbrx_chat_model = ChatDatabricks(endpoint="databricks-dbrx-instruct", max_tokens=4096, temperature=model_temp)
  llama_3_chat_model = ChatDatabricks(endpoint="databricks-meta-llama-3-70b-instruct", max_tokens=4096, temperature=model_temp)
  mixtral_chat_model = ChatDatabricks(endpoint="databricks-mixtral-8x7b-instruct", max_tokens=4096, temperature=model_temp)

  # Assemble all of the LLM chains which makes it easier to invoke them and parse their outputs
  # This uses langchain's own pipe syntax to organize multiple components into a "pipe"
  dbrx_chain = ( prompt | dbrx_chat_model | StrOutputParser() )
  llama_3_chain = ( prompt | llama_3_chat_model | StrOutputParser() )
  mixtral_chain = ( prompt | mixtral_chat_model | StrOutputParser() )
  llm_chains = {"dbrx": dbrx_chain, "llama-3": llama_3_chain, "mixtral": mixtral_chain}
  if not token_count >= 4096: # Only use the llama-2 if we know the input prompt isn't greater than or equal to 4096 tokens (a weakness of llama-2)
    llama_chat_model = ChatDatabricks(endpoint="databricks-llama-2-70b-chat", max_tokens=4096-token_count, temperature=model_temp)
    llama_chain = ( prompt | llama_chat_model | StrOutputParser() )
    llm_chains["llama-2"] = llama_chain

  # For every LLM, query it with our prompt and print the outputs
  # Also save the outputs into a dictionary which we'll write to a delta table
  all_responses = {}
  all_responses["full_prompt"] = prompt.format(**combined_dict)
  for llm_name, llm_chain in llm_chains.items():
    print(f"#### {llm_name} OUTPUTS ####")
    inv_res = llm_chain.invoke(combined_dict)
    print(inv_res)
    all_responses[llm_name] = inv_res
    print()

  # Also query the SMC API llama-3 model
  print(f"#### SMC API OUTPUTS ####")
  url = "https://relay.stagwellmarketingcloud.io/google/v1/projects/141311124325/locations/us-central1/endpoints/2940118281928835072:predict"
  payload = {"instances": [
          {
              "prompt": prompt.format(**combined_dict),
              "temperature": model_temp,
              "max_tokens": 2048,
              "stop": ["<|eot_id|>", "<|end_of_text|>"]
          }
      ]}
  headers = {
    "Content-Type": "application/json",
    "smc-owner": "...",
    "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImZmYzU1ZmNiLTkwZTMtNGI4OS1iMmY0LTQ1Mjg0OWE3MWZiNCIsImlzcyI6IlNNQyIsImtleU5hbWUiOiJUYXJnZXRkVmljdG9yeSBNTVMiLCJraWQiOiI5M2M5OGRiMDVmZmUyNDI3NDZkM2IyYzYwMDIzNDYxNiIsIm9yZ0lkIjoiNjA0NTM3MjYtYWY4ZC00NjQ2LTk2ZTktNzRjNjQyMWZiNDI0In0.XNnsi6d_47yBLgHZwouoEtqC6IB-bfaLnGL6kB3Ldw9oXLCfEOuXygFGMhlH7ywTHowaoegPPygYiQ-Z78lsDQ"
  }
  response = requests.request("POST", url, json=payload, headers=headers)
  response_json = json.loads(response.text)
  response_text = response_json["predictions"][0].rsplit("Output:", 1)[-1].strip()
  all_responses["smc_api"] = response_text
  print(response_text)

  # Wes 9.

  # Let's save all of our LLM outputs to a delta table!
  # The table makes use of a Batch_Number column to mark which outputs were generated at the same time
  # There's also an Output_Datetime column which contains the actual datetime the outputs were created, which will be the same value for outputs within the same batch
  # But a batch number is easier to communicate to others and understand at a quick glance

  try: # If the table already exists, the new batch number should be one greater than the last one
    batch_num = 1 + sql_call(f"SELECT batch_number FROM {rag_output_table_name} ORDER BY batch_number DESC LIMIT 1")[0][0]
  except Exception as e: # If the table doesn't exist, the first batch will be batch number 1
    print("No batch number found, reseting batch number to 1.")
    batch_num = 1

  for key_that_is_source, value_that_is_contents in all_responses.items():
    sql_call(
      f"INSERT INTO {rag_output_table_name} ( batch_number,  output_source,  output_content,  output_datetime)\
                                     VALUES (:batch_number, :output_source, :output_content, :output_datetime)",
      {"batch_number": batch_num, "output_source": key_that_is_source, "output_content": value_that_is_contents, "output_datetime": datetime.now(z("US/Eastern"))}
    )
  print("Done :)")

def main() -> None:
  if st.button("wes button"):
    everything_from_wes()

  if not st.session_state.get('email'): #TODO: this line is of dubious usefulness. It's supposed to let you run cicero_prompter.py locally and stand-alone without cicero.py, however.
    st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  if 'use_count' not in st.session_state:
    st.session_state['use_count'] = count_from_activity_log_times_used_today(st.session_state["email"])
  use_count_limit = 100 #arbitrary but reasonable choice of limit
  if st.session_state['email'] in ["abrady@targetedvictory.com", "thall@targetedvictory.com", "test@example.com"]: # Give certain users nigh-unlimited uses.
    use_count_limit = 100_000_000
  if st.session_state['use_count'] >= use_count_limit:
    st.write(f"You cannot use this service more than {use_count_limit} times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
    exit_error(52) # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

  model_permissions = load_model_permissions(st.session_state['email']) #model_permissions stores model names as ***all lowercase***
  if presets["default"]["model"] not in model_permissions: #We want everyone to want to have access to this default, at least at time of writing this comment.
    model_permissions.insert(0, presets["default"]["model"])
  #NOTE: these model secrets have to begin the secrets.toml as, like:
  # models.gpt-revamp = ''
  # models.Context = ''
  # Or some other way of making a dict in toml
  models: dict[str,str] = { k:v for k, v in st.secrets['models'].items() if k.lower() in [m.lower() for m in model_permissions] } #filter for what the actual permissions are for the user.

  bios: dict[str, str] = load_bios()

  account_names = load_account_names()

  if not st.session_state.get("initted"):
    set_ui_to_preset("default")
    #Exploit the fact that the streamlit community cloud apparently regularly reruns our code invisibly somewhere in order to keep the endpoint alive during business hours, because a user disliked waiting.
    if 8 <= datetime.now(z("US/Eastern")).hour <= 19 and datetime.now(z("US/Eastern")).strftime("%A") not in ["Saturday", "Sunday"]:
      send(models[presets["default"]["model"]], st.secrets["databricks_api_token"], {}, dummy=True) # This line just tries to wake up the gpt-short-medium-long model slightly faster, therefore slightly conveniencing the user, probably. #possibly due to a streamlit community cloud bug, this line seems to cause our scale-to-zero model to get pinged often enough to always be awake, when the condition is met.
    st.session_state["initted"] = True
    st.rerun() #STREAMLIT-BUG-WORKAROUND: this rerun actually has nothing to do with initing, it's just convenient to do here, since we need to do it exactly once, on app startup. It prevents the expander from experiencing a streamlit bug (<https://github.com/streamlit/streamlit/issues/2360>) that is only present in the initial run state. Anyway, this rerun is really fast and breaks nothing (except the developer mode initial performance timer readout, which is now clobbered) so it's a good workaround.

  login_activity_counter_container = st.container()

  if st.button("Reset", help="Resets the UI elements to their default values. This button will also trigger cached data like the Candidate Bios and the news RSS feed to refresh. You can also just press F5 to refresh the page."):
    st.cache_data.clear()
    st.session_state["headline_search_function"] = None
    set_ui_to_preset("default")

  # setting default values for advanced parameters for our non-developer end-user
  num_beams: int = 1
  top_k: int = 50
  top_p: float = 1.0
  repetition_penalty: float = 1.2
  no_repeat_ngram_size: int = 4
  num_return_sequences: int = 5
  early_stopping: bool = False
  do_sample: bool = True
  output_scores: bool = False

  #For technical reasons (various parts of it update when other parts of it are changed, iirc) this can't go within the st.form

  with st.expander(r"$\textsf{\Large FOX NEWS HEADLINES}$"if st.session_state["developer_mode"] else r"$\textsf{\Large NEWS HEADLINES}$"):
    exact_match_query = st.text_input("Headline Search  \n*Returns headlines containing the search terms. Hit Enter to filter the headlines.*", key="exact_match_query")
    overdrive: bool = st.checkbox("Only search headlines from the last 3 days.", key="overdrive")
    h: list[str] = load_headlines(get_all=False) if not overdrive else load_headlines(get_all=False, past_days=3)
    if exact_match_query:
      h = only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(h, exact_match_query)
    headline = st.selectbox("Selected headlines will be added to your prompt below.", list(h), key="headline")

  st.text("") # Just for vertical spacing.

  with st.form('query_builder'):
    with st.sidebar:
      st.header("Settings")
      temperature : float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") #temperature: slider between 0 and 1, defaults to 0.7, float
      #character count max, min: int, cannot be negative or 0, starts at 40. floor divide by 4 to get token count to pass to model:
      target_charcount_min = st.number_input("Min Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_min")
      target_charcount_max = st.number_input("Max Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_max") #help="Short: <=160 | Medium: >160, <400 | Long: >=400"
      if st.session_state["developer_mode"]:
        with st.expander("Advanced Parameters"):
          num_beams = int( st.number_input("num_beams:", min_value=1, format='%d', step=1, key="num_beams", help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.") )
          top_k = int( st.number_input("top_k:", min_value=1, format='%d', step=1, key="top_k" , help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider."))
          top_p = st.number_input("top_p:", min_value=0.0, format='%f', key="top_p" , help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
          repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, max_value=2.0, format='%f', key="repetition_penalty" , help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
          no_repeat_ngram_size = int( st.number_input("no_repeat_ngram_size:", min_value=0, max_value=10, format='%d', step=1, key="no_repeat_ngram_size" , help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.") )
          num_return_sequences = int( st.number_input("num_return_sequences:", min_value=1, max_value=10, format='%d', step=1, key="num_return_sequences" , help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.") )
          early_stopping = st.checkbox("early_stopping", key="early_stopping" , help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
          do_sample = st.checkbox("do_sample", key="do_sample" , help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
          output_scores = st.checkbox("output_scores", key="output_scores" , help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
    model_name = presets["default"]["model"] #COULD: clean up this code to remove all of the logic related to this although I think we still want to save the model name and uri in the activity log) #str( st.selectbox(r"$\textsf{\Large COPYWRITING MODEL}$", models, key="model") )
    model_uri = models[model_name]
    account = st.selectbox("Account (required)", list(account_names), key="account")
    ask_type = str( st.selectbox("Ask Type", ['Hard Ask', 'Medium Ask', 'Soft Ask', 'Soft Ask Petition', 'Soft Ask Poll', 'Soft Ask Survey'], key="ask_type") )
    topics = st.multiselect("Topics", sorted([t for t, d in topics_big.items() if d["show in prompter?"]]), key="topics" )
    additional_topics = [x.strip() for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
    tone = st.multiselect("Tone", ['Agency', 'Apologetic', 'Candid', 'Exclusivity', 'Fiesty', 'Grateful', 'Not Asking For Money', 'Pleading', 'Quick Request', 'Secretive', 'Time Sensitive', 'Urgency'], key="tone") #, 'Swear Jar' will probably be in here some day, but we don't have "we need more swear jar data to make this tone better"
    generate_button = st.form_submit_button("Submit")

  if model_name != 'gpt-short-medium-long':
    text_length = ""
  else:
    if target_charcount_max <= 160:
      text_length = " short"
    elif target_charcount_max > 160 and target_charcount_max < 400:
      text_length = " medium"
    elif target_charcount_max >= 400:
      text_length = " long"

  #Composition and sending a request:
  did_a_query = False
  if generate_button:
    if account:
      did_a_query = True
      st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
      st.session_state['human-facing_prompt'] = (
        ((bios[account]+"\n\n") if "Bio" in topics and account in bios else "") +
        "Write a " + ask_type.lower() + text_length +
        " text for " + account +
        " about: " + list_to_bracketeds_string(
            sorted( external_topic_names_to_internal_topic_names_list_mapping(topics) + list_from_human_format_to_cicero_tone_format(additional_topics) )
            or ["No Hook"]
        ) +
        ( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sorted(list_from_human_format_to_cicero_tone_format(tone))) ) +
        (" {"+headline+"} " if headline else "")
      )
      prompt = "<|startoftext|> "+st.session_state['human-facing_prompt']+" <|body|>"
      st.session_state['developer-facing_prompt'] = prompt
      dict_prompt = {"prompt": [prompt],
                      "temperature": [temperature],
                      "max_new_tokens": [int(target_charcount_max) // 4],
                      "min_new_tokens": [int(target_charcount_min) // 4],
                      "num_beams": [num_beams],
                      "top_k": [top_k],
                      "top_p": [top_p],
                      "repetition_penalty": [repetition_penalty],
                      "no_repeat_ngram_size": [no_repeat_ngram_size],
                      "num_return_sequences": [num_return_sequences],
                      "early_stopping": [early_stopping],
                      "do_sample": [do_sample],
                      "output_scores": [output_scores]
                    }
      unpsycho_dict_prompt = {k:v[0] for (k,v) in dict_prompt.items()}
      try:
        GenerationConfig(**unpsycho_dict_prompt)# This validates the parameters, throwing an exception that displays to the user and explains the problem if the parameters are wrong.
        with st.spinner("Prompting the model.  Please alert the Optimization Team if this process takes longer than 1 minute."):
          outputs = send(model_uri, st.secrets["databricks_api_token"], dict_prompt)
        st.session_state['outputs'] = outputs
        if 'history' not in st.session_state: st.session_state['history'] = []
        st.session_state['history'] += outputs
        st.session_state['character_counts_caption'] = "Character counts: "+str([len(o) for o in outputs])
      except Exception as e:
        st.error(e)
        did_a_query = False
    else:
      st.error("***No account name is selected, so I can't send the request!***")

  # The idea is for these output elements to persist after one query button, until overwritten by the results of the next query.
  if 'human-facing_prompt' in st.session_state:
    st.caption(st.session_state['human-facing_prompt'].replace("$", r"\$"))
    if 'developer-facing_prompt' in st.session_state and st.session_state["developer_mode"]:
      st.caption("Developer Mode Message: the prompt passed to the model is: "+ st.session_state['developer-facing_prompt'].replace("$", r"\$"))

  st.error("WARNING! Outputs have not been fact checked. CICERO is not responsible for inaccuracies in deployed copy. Please check all *names*, *places*, *counts*, *times*, *events*, and *titles* (esp. military titles) for accuracy.  \nAll numbers included in outputs are suggestions only and should be updated. They are NOT analytically optimized to increase conversions (yet) and are based solely on frequency in past copy.", icon="⚠️")
  if 'outputs' in st.session_state:
    for output in st.session_state['outputs']:
      col1, col2 = st.columns([.95, .05])
      with col1:
        st.write( output.replace("$", r"\$") ) #this prevents us from entering math mode when we ask about money.
      if st.session_state.get("developer_mode"):
        with col2:
          if st.button("🖋️", key="🖋️"+output, help="Send down to Cicero"):
            _reply_one = "Here is a conservative fundraising text: [" + output + "] DO NOT immediately suggest revisions to the text. Directly ask the user what assistance they need with the text."
            reply_two = "Here is a conservative fundraising text: [" + output + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email."
            st.session_state['cicero_ai']=reply_two
            st.session_state['display_only_this_at_first_blush'] = "«"+output+"»"
    st.caption(st.session_state.get('character_counts_caption'))
    if st.session_state.get('cicero_ai'):
      if isinstance(st.session_state['cicero_ai'], int): # Arbitrary truthy value that isn't a string (so thus can't be from the responses above, which are text)
        cicero_rag_only.main(streamlit_key_suffix="_prompter")
      else:
        #clear previous chat history
        st.session_state.chat = None
        st.session_state.messages = None
        cicero_rag_only.grow_chat(streamlit_key_suffix="_prompter", alternate_content=st.session_state['cicero_ai'], display_only_this_at_first_blush=st.session_state['display_only_this_at_first_blush'])
        cicero_rag_only.main(streamlit_key_suffix="_prompter")
        st.session_state['cicero_ai'] = 2 # This sets the arbitrary value discussed above.

  st.error('**REMINDER!** Please tag all projects with "**optimization**" in the LABELS field in Salesforce.')

  with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
    st.header("History of replies:")
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)

  login_activity_counter_container.write(
    f"""You are logged in as {st.session_state['email']}{" (internally, "+str(st.experimental_user['email'])+")" if st.session_state["developer_mode"] else ""}. You have prompted {st.session_state['use_count']} time{'s' if st.session_state['use_count'] != 1 else ''} today, out of a limit of {use_count_limit}. {"You are in developer mode." if st.session_state["developer_mode"] else ""}"""
  )

  # Activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query.
  if did_a_query:
    dict_prompt.pop('prompt')
    no_prompt_dict_str = str(dict_prompt)
    write_to_activity_log_table( datetime=str(datetime.now()), useremail=st.session_state['email'], promptsent=prompt, responsegiven=json.dumps(outputs), modelparams=no_prompt_dict_str, modelname=model_name, modelurl=model_uri )

  # st.components.v1.html('<!--<script>//you can include arbitrary html and javascript this way</script>-->') #or, use st.markdown, if you want arbitrary html but javascript isn't needed.

if __name__ == "__main__": main()
