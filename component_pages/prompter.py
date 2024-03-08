#!/usr/bin/env -S streamlit run

"""Post hoc ergo prompter hoc?"""

import streamlit as st
import pandas as pd
import requests
import json
from databricks import sql # Spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing.
from datetime import datetime, date
import faiss
from sentence_transformers import SentenceTransformer # Weird that this is how you reference the sentence-transformers package on pypi, too. Well, whatever.
#COULD: use https://pypi.org/project/streamlit-profiler/ for profiling
from transformers import GenerationConfig
from typing import TypedDict


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
def load_model_permissions(useremail: str|None) -> list[str]:
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      results = cursor.execute(
        "SELECT DISTINCT modelname FROM models.default.permissions WHERE useremail = %(useremail)s", {'useremail': useremail}
      ).fetchall()
      return [result[0].lower() for result in results]

@st.cache_data() #Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
def count_from_activity_log_times_used_today(useremail: str|None = st.experimental_user['email']) -> int: #this goes by whatever the datetime default timezone is because we don't expect the exact boundary to matter much.
  try: # This can fail if the table doesn't exist (at least not yet, as we create it on insert if it doesn't exist), so it's nice to have a default
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        return cursor.execute(
          f"SELECT COUNT(*) FROM main.default.activity_log WHERE useremail = %(useremail)s AND datetime LIKE '{date.today()}%%'",
          {'useremail': useremail}
        ).fetchone()[0]
  except Exception as e:
    print("There was an exception in count_from_activity_log_times_used_today, so I'm just returning a value of 0. Here's the exception:", str(e))
    return 0

def write_to_activity_log_table(datetime: str, useremail: str|None, promptsent: str, responsegiven: str, modelparams: str) -> int:
  """The most sensical thing for this function to return is the closest thing to a result value that an insert command produces: the .rowcount variable of the cursor, which is "the number of rows that the last .execute*() [...] affected (for DML statements like UPDATE or INSERT)." <https://peps.python.org/pep-0249/#rowcount>. However, that PEP also states that "The attribute is -1 in case no .execute*() has been performed on the cursor or the rowcount of the last operation is cannot be determined by the interface." And the implementation of databricks-sql-connector seems to have taken this liberty to, indeed, always return -1. So this return value is useless."""
  with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      cursor.execute("CREATE TABLE IF NOT EXISTS main.default.activity_log (datetime string, useremail string, promptsent string, responsegiven string, modelparams string)")
      return cursor.execute(
        "INSERT INTO main.default.activity_log VALUES (%(datetime)s, %(useremail)s, %(promptsent)s, %(responsegiven)s, %(modelparams)s)",
        {'datetime': datetime, 'useremail': useremail, 'promptsent': promptsent, 'responsegiven': responsegiven, 'modelparams': modelparams} #this probably could be a kwargs, but I couldn't figure out how to do that neatly the particular way I wanted so whatever, you just have to change this 'signature' four times in this function if you want to change it.
      ).rowcount

@st.cache_data()
def load_bios() -> dict[str, str]:
  bios : dict[str, str] = dict(pd.read_csv("Candidate_Bios.csv", index_col="ID").to_dict('split')['data'])
  return bios

@st.cache_data()
def load_account_names() -> list[str]:
  return list(pd.read_csv("Client_List.csv")['ACCOUNT_NAME'])

@st.cache_data()
def load_headlines(get_all:bool=False, past_days:int=7) -> list[str]:
  try: # This can fail if the table doesn't exist (at least not yet, as we create it on insert if it doesn't exist), so it's nice to have a default
    with sql.connect(server_hostname=st.secrets["DATABRICKS_SERVER_HOSTNAME"], http_path=st.secrets["DATABRICKS_HTTP_PATH"], access_token=st.secrets["databricks_api_token"]) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
      with connection.cursor() as cursor:
        results = cursor.execute(
          "SELECT DISTINCT headline FROM cicero.default.headline_log" if get_all else
          f"""WITH SortedHeadlines AS (
                SELECT
                    datetime,
                    headline,
                    ROW_NUMBER() OVER (PARTITION BY headline ORDER BY datetime DESC, headline) AS row_num
                FROM
                    cicero.default.headline_log
                )
              SELECT
                headline
              FROM
                SortedHeadlines
              WHERE
                row_num = 1
                AND datetime >= NOW() - INTERVAL {past_days} DAY
              ORDER BY
                datetime DESC, headline;
          """ # The (arbitrary) requirement is that we return results from the last 7 days, and this is the easiest way to do it. Might not be the most performant query, but it works. COULD: review performance, see if there are any alternative queries that could be faster.
        ).fetchall()
        return [result[0] for result in results]
  except Exception as e:
    print("There was an exception in load_headlines, so I'm just returning this. Here's the exception:", str(e))
    return ["There was an exception in load_headlines, so I'm just returning this. Here's the exception: "+str(e)]

@st.cache_data()
def sort_headlines_semantically(headlines: list[str], query: str, number_of_results_to_return:int=1) -> list[str]:
  """This does a bunch of gobbledygook no one understands. But the important thing is that it returns to you a function that will return to you the top k news results for a given query."""
  model = SentenceTransformer("BAAI/bge-large-en-v1.5")
  faiss_title_embedding = model.encode(headlines)
  faiss.normalize_L2(faiss_title_embedding)
  # Index1DMap translates search results to IDs: https://faiss.ai/cpp_api/file/IndexIDMap_8h.html#_CPPv4I0EN5faiss18IndexIDMapTemplateE ; The IndexFlatIP below builds index.
  index_content = faiss.IndexIDMap(faiss.IndexFlatIP(len(faiss_title_embedding[0])))
  index_content.add_with_ids(faiss_title_embedding, range(len(headlines)))
  query_vector = model.encode([query])
  faiss.normalize_L2(query_vector)
  top_results = index_content.search(query_vector, number_of_results_to_return)
  ids = top_results[1][0].tolist()
  similarities = top_results[0][0].tolist() # COULD: return this, for whatever we want.
  results = [headlines[i] for i in ids]
  return results

#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
presets: dict[ str, dict[str, float|int|bool|str|list[str]|None] ] = {
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
    "model": "Context",
    "account" : None,
    "ask_type": "Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
    "semantic_query": "",
    "headline": None,
    "overdrive": False,
    "exact_match": False
  },
}

def set_ui_to_preset(preset_name: str) -> None:
  preset = presets[preset_name]
  for i in preset: #this iterates over the keys
    st.session_state[i] = preset[i]

def list_from_cicero_tone_format_to_human_format(l: list[str]) -> list[str]:
  return [x.replace("_", " ").title() for x in l]
def list_from_human_format_to_cicero_tone_format(l: list[str]) -> list[str]:
  return [x.replace(" ", "_").lower() for x in l]
def list_to_bracketeds_string(l: list[str]) -> str:
  return " ".join([f"[{i}]" for i in l])

def main() -> None:

  if 'use_count' not in st.session_state:
    st.session_state['use_count'] = count_from_activity_log_times_used_today()
  use_count_limit = 100 #arbitrary but reasonable choice of limit
  if st.experimental_user['email'] in ["abrady@targetedvictory.com", "thall@targetedvictory.com" "test@example.com"]: # Give certain users nigh-unlimited uses.
    use_count_limit = 100_000_000
  if st.session_state['use_count'] >= use_count_limit:
    st.write(f"You cannot use this service more than {use_count_limit} times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
    exit() # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

  model_permissions = load_model_permissions(st.experimental_user['email']) #model_permissions stores model names as ***all lowercase***
  if "context" not in model_permissions: #We want everyone to want to have access to default, at least at time of writing this comment.
    model_permissions.insert(0, "Context")
  #NOTE: these model secrets have to be in the secrets.toml as, like:
  # models.Default = ''
  # models.Context = ''
  # Or some other way of making a dict in toml
  models: dict[str,str] = { k:v for k, v in st.secrets['models'].items() if k.lower() in [m.lower() for m in model_permissions] } #filter for what the actual permissions are for the user.

  st.error('REMINDER! Please tag all projects with "optimization" in the LABELS field in Salesforce.')

  bios : dict[str, str] = load_bios()

  account_names = load_account_names()

  headlines : list[str] = load_headlines(get_all=False) #COULD: if we don't need to allow the user this list all the time, we could move this line to the expander, in some kind of `if` statement, possibly a checkbox, to save maybe 2 seconds on app load times. (Unfortunately, the expansion state of the expander is not programmatically available to `if` upon. Also, we do kind of want the user to be able to access this list all the time, without sorting or searching necessarily being in play.)
  headlines_overdrive : list[str] = load_headlines(get_all=False, past_days=3)

  if not st.session_state.get("initted"):
    set_ui_to_preset("default")
    st.session_state["initted"] = True
    st.rerun() #STREAMLIT-BUG-WORKAROUND: this rerun actually has nothing to do with initing, it's just convenient to do here, since we need to do it exactly once, on app startup. It prevents the expander from experiencing a streamlit bug (<https://github.com/streamlit/streamlit/issues/2360>) that is only present in the initial run state. Anyway, this rerun is really fast and breaks nothing (except the developer mode initial performance timer readout, which is now gone) so it's a good workaround.

  login_activity_counter_container = st.container()

  if st.button("Reset", help="Resets the UI elements to their default values. This button will also trigger cached data like the Candidate Bios and the news RSS feed to refresh. You can also just press F5 to refresh the page."):
    st.cache_data.clear()
    st.session_state["headline_search_function"] = None
    set_ui_to_preset("default")

  def send(model_uri: str, databricks_token: str, data: pd.DataFrame) -> list[str]:
    headers = {
      "Authorization": f"Bearer {databricks_token}",
      "Content-Type": "application/json",
    }
    # As we were flailing around trying to get the model to work, we made the parameter format logic needlessly complicated.
    ds_dict = {'dataframe_split': data.to_dict(orient='split')}
    data_json = json.dumps(ds_dict, allow_nan=True)

    response = requests.request(method='POST', headers=headers, url=model_uri, data=data_json)
    if response.status_code == 504:
      return send(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
    elif response.status_code == 404 and response.json()["error_code"] == "RESOURCE_DOES_NOT_EXIST":
      raise Exception("Encountered 404 error \"RESOURCE_DOES_NOT_EXIST\" when trying to query the model. This usually means the model endpoint has been moved. Please contact the team in charge of model serving to rectify the situation.")
    elif response.status_code != 200:
      if response.json()["error_code"] == "BAD_REQUEST":
        raise Exception(response.json()["message"])
      else:
        raise Exception(f"Request failed with status {response.status_code}, {response.text}")
    return response.json()["predictions"][0]["0"]

  # setting default values for advanced parameters for our non-developer end-user
  num_beams=1
  top_k=50
  top_p=1.0
  repetition_penalty=1.2
  no_repeat_ngram_size=4
  num_return_sequences=5
  early_stopping=False
  do_sample=True
  output_scores=False

  def only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(l: list[str], s: str) -> list[str]: return [s for s in l if s.lower().find(semantic_query.lower()) != -1]

  #For technical reasons (various parts of it update when other parts of it are changed, iirc) this can't go within the st.form

  with st.expander(r"$\textsf{\Large FOX NEWS HEADLINES}$"if st.session_state["developer_mode"] else r"$\textsf{\Large NEWS HEADLINES}$"):
    semantic_query = st.text_input("Semantic Search  \n*Returns headlines matching the meaning of the search terms, not necessarily exact matches. Must hit Enter.*  \n*Example: searching for `border' will also return headlines for 'immigration', 'migrants', 'border crossings', 'deportation', etc.*", key="semantic_query")
    col1, col2 = st.columns(2) #this column setup arguably looks worse than the default, and we've already blown the vertical-single-screen idea when you open this expander, so maybe you don't have to keep this formatting idk.
    with col1:
      exact_match: bool = st.checkbox("Use exact match instead of semantic match.", key="exact_match") #an option for persnickety people ohoho
    with col2:
      overdrive: bool = st.checkbox("Only search headlines from the last 3 days.", key="overdrive")
    h = headlines if not overdrive else headlines_overdrive
    if semantic_query:
      if exact_match:
        headlines_sorted = only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(h, semantic_query)
      else:
        headlines_sorted = sort_headlines_semantically(h, semantic_query, 10) # The limit of 10 is arbitrary. No need to let the user change it.
    else:
      headlines_sorted = h # I forget if this is actually sorted in any way by default. Possibly date?
    headline = st.selectbox("Selected headlines will be added to your prompt below.", [""]+list(headlines_sorted), key="headline") #STREAMLIT-BUG-WORKAROUND: see other [""] STREAMLIT-BUG-WORKAROUND in file.

  st.text("") # Just for vertical spacing.

  with st.form('query_builder'):
    with st.sidebar:
      st.header("Settings")
      temperature : float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") #temperature: slider between 0 and 1, defaults to 0.7, float
      #character count max, min: int, cannot be negative or 0, starts at 40. floor divide by 4 to get token count to pass to model:
      target_charcount_min = st.number_input("Min Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_min")
      target_charcount_max = st.number_input("Max Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_max")
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
    model_name = str( st.selectbox(r"$\textsf{\Large COPYWRITING MODEL}$", models, key="model") )
    model_uri = models[model_name]
    account = st.selectbox("Account (required)", [""]+list(account_names), key="account" ) #STREAMLIT-BUG-WORKAROUND: For some reason, in the current version of streamlit, st.selectbox ends up returning the first value if the index has value is set to None via the key in the session_state, which is a bug (<https://github.com/streamlit/streamlit/issues/7649>), but anyway we work around it using this ridiculous workaround. This does leave a first blank option in there. But whatever.
    ask_type = str( st.selectbox("Ask Type", ['Hard Ask', 'Medium Ask', 'Soft Ask', 'Soft Ask Petition', 'Soft Ask Poll', 'Soft Ask Survey'], key="ask_type") )
    topics = st.multiselect("Topics", sorted([t for t, d in topics_big.items() if d["show in prompter?"]]), key="topics" )
    additional_topics = [x.strip() for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
    tone = st.multiselect("Tone", ['Agency', 'Apologetic', 'Candid', 'Exclusivity', 'Fiesty', 'Grateful', 'Not Asking For Money', 'Pleading', 'Quick Request', 'Secretive', 'Swear Jar', 'Time Sensitive', 'Urgency'], key="tone")
    generate_button = st.form_submit_button("Submit")

  #Composition and sending a request:
  did_a_query = False
  if generate_button:
    if account:
      did_a_query = True
      st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
      st.session_state['human-facing_prompt'] = (
        ((bios[account]+"\n\n") if "Bio" in topics and account in bios else "") +
        "Write a "+ask_type.lower()+
        " text for "+account+
        " about: "+list_to_bracketeds_string(
            sorted( external_topic_names_to_internal_topic_names_list_mapping(topics) + list_from_human_format_to_cicero_tone_format(additional_topics) )
            or ["No Hook"]
        )+
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
        df_prompt = pd.DataFrame(dict_prompt)
        outputs = send(model_uri, st.secrets["databricks_api_token"], df_prompt)
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
    st.caption(st.session_state['human-facing_prompt'])
    if 'developer-facing_prompt' in st.session_state and st.session_state["developer_mode"]:
      st.caption("Developer Mode Message: the prompt passed to the model is: "+ st.session_state['developer-facing_prompt'])

  st.error("WARNING! Outputs have not been fact checked. CICERO is not responsible for inaccuracies in deployed copy. Please check all *names*, *places*, *counts*, *times*, *events*, and *titles* (esp. military titles) for accuracy.  \nAll numbers included in outputs are suggestions only and should be updated. They are NOT analytically optimized to increase conversions (yet) and are based solely on frequency in past copy.", icon="⚠️")
  if 'outputs' in st.session_state:
    for output in st.session_state['outputs']:
      col1, col2, col3 = st.columns([.94, .03, .03])
      #TODO: unimplemented draft version
      with col1:
        st.write("```"+output+"```") # I put this in markdown code block here just so that messages which contain two dollar signs ("I need $10. Can you give me $10?") don't enter latex mode in the middle.
      with col2:
        st.button("⧉", key="⧉"+output, help="Copy to system clipboard (ctrl-c)") #use https://github.com/mmz-001/st-copy-to-clipboard for this if we want it.
      with col3:
        if st.button("📝", key="📝"+output, help="Send down to scratchpad"):
          st.session_state["scratchpad"] = output
  if 'character_counts_caption' in st.session_state: st.caption(st.session_state['character_counts_caption'])

  with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
    st.header("History of replies:")
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)

  login_activity_counter_container.write( f"You are logged in as {st.experimental_user['email']} . You have queried {st.session_state['use_count']} {'time' if st.session_state['use_count'] == 1 else 'times'} today, out of a limit of {use_count_limit}."+(" You are in developer mode." if st.session_state["developer_mode"] else "") )

  scratchpad = st.text_area("Scratchpad", st.session_state.get("scratchpad") or "", help="This text area does nothing to the prompter; it's only here to allow you to paste outputs here and edit them slightly, for your own convenience.")
  st.caption(f"Scratchpad character count: {len(scratchpad)}. (CTRL-ENTER in the box above to recalculate character count.)")
  #activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query
  if did_a_query:
    dict_prompt.pop('prompt')
    no_prompt_dict_str = str(dict_prompt)
    write_to_activity_log_table(datetime=str(datetime.now()), useremail=st.experimental_user['email'], promptsent=prompt, responsegiven=json.dumps(outputs), modelparams=no_prompt_dict_str)

  # st.components.v1.html('<!--<script>//you can include arbitrary html and javascript this way</script>-->') #or, use st.markdown, if you want arbitrary html but javascript isn't needed.
if __name__ == "__main__": main()
