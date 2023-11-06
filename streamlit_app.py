from streamlit.components.v1 import html
from collections import namedtuple
import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import subprocess
import requests
import json
import os
import feedparser
from databricks import sql #spooky that this is not the same name as the pypi package databricks-sql-connector, but is the way to refer to the same thing
from datetime import datetime, date

use_experimental_features = False
model_uri = st.secrets['model_uri']
databricks_api_token = st.secrets['databricks_api_token']

def count_from_activity_log_times_used_today() -> int: #this goes by whatever the datetime default timezone is because we don't expect the exact boundary to matter much.
  with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These secrets should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      return cursor.execute(
        f"SELECT COUNT(*) FROM activity_log WHERE useremail = %(useremail)s AND datetime LIKE '{date.today()}%%'",
        {'useremail': st.experimental_user['email']}
      ).fetchone()[0]

def write_to_activity_log_table(datetime: str, useremail: str, promptsent: str, responsegiven: str, modelparams: str):
  with sql.connect(server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"), http_path=os.getenv("DATABRICKS_HTTP_PATH"), access_token=os.getenv("databricks_api_token")) as connection: #These should be in the root level of the .streamlit/secrets.toml
    with connection.cursor() as cursor:
      cursor.execute("CREATE TABLE IF NOT EXISTS main.default.activity_log ( datetime string, useremail string, promptsent string, responsegiven string )")
      return cursor.execute( #I'm not even sure what this returns but you're welcome to that, I guess.
        "INSERT INTO main.default.activity_log VALUES (%(datetime)s, %(useremail)s, %(promptsent)s, %(responsegiven)s, %(modelparams)s)",
        {'datetime': datetime, 'useremail': useremail, 'promptsent': promptsent, 'responsegiven': responsegiven, 'modelparams': modelparams} #this probably could be a kwargs, but I couldn't figure out how to do that neatly the particular way I wanted so whatever, you just have to change this 'signature' three different places in this function if you want to change it.
      )

use_count = count_from_activity_log_times_used_today() # I thought this function would be slow, but so far it's actually fast enough to just run it every input cycle.
use_count_limit = 100 #arbitrary but reasonable choice of limit
if use_count >= use_count_limit:
  st.write("You cannot use this service more than 100 times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
  exit() # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

bespoke_title_element = '<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>'
st.markdown(bespoke_title_element, unsafe_allow_html=True)

@st.cache_data(ttl="1h")
def load_bios() -> dict[str, str]:
  bios : dict[str, str] = dict(pd.read_csv("Candidate_Bios.csv", index_col="ID").to_dict('split')['data'])
  return bios
bios : dict[str, str] = load_bios()

@st.cache_data(ttl="1h")
def load_account_names() -> list[str]:
  return pd.read_csv("Client_List.csv")['ACCOUNT_NAME']
account_names = load_account_names()

@st.cache_data(ttl="1h")
def load_rss():
  try:
    rss_dict = feedparser.parse("http://bothell.carpenter.org:21540")
    rss_df = pd.DataFrame( [ (e['title'], e['description'], e['content'][0]['value']) for e in rss_dict['entries'] ] )
  except Exception as e:
    rss_df = pd.DataFrame(str(e))
  return rss_df
if use_experimental_features:
  rss_df : pd.DataFrame = load_rss()
#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
presets = {
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
    "account" : None,
    "ask_type": "Fundraising Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
  },
}

def set_ui_to_preset(preset_name: str):
  preset = presets[preset_name]
  for i in preset: #this iterates over the keys
    st.session_state[i] = preset[i]

if not st.session_state.get("initted"):
  set_ui_to_preset("default")
  st.session_state["initted"] = True

login_activity_counter_container = st.container()

if st.button("Reset", help="Resets the UI elements to their default values. This button will also trigger cached data like the Candidate Bios and the news RSS feed to refresh. You can also just press F5 to refresh the page."):
  st.cache_data.clear()
  set_ui_to_preset("default")

def create_tf_serving_json(data):
  return {'inputs': {name: data[name].tolist() for name in data.keys()} if isinstance(data, dict) else data.tolist()}

def send(model_uri, databricks_token, data) -> list[str]:
  headers = {
    "Authorization": f"Bearer {databricks_token}",
    "Content-Type": "application/json",
  }
  ds_dict = {'dataframe_split': data.to_dict(orient='split')} if isinstance(data, pd.DataFrame) else create_tf_serving_json(data)
  data_json = json.dumps(ds_dict, allow_nan=True)
  response = requests.request(method='POST', headers=headers, url=model_uri, data=data_json)
  if response.status_code == 504:
    return send(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
  elif response.status_code == 404 and response.json()["error_code"] == "RESOURCE_DOES_NOT_EXIST":
    return ["Encountered 404 error \"RESOURCE_DOES_NOT_EXIST\" when trying to query the model. This usually means the model endpoint has been moved. Please contact the team in charge of model serving to rectify the situation."]
  elif response.status_code != 200:
    return [f"Request failed with status {response.status_code}, {response.text}"]
  return response.json()["predictions"][0]["0"]

tone_indictators_sorted = ["Urgency", "Agency", "Exclusivity"]

def sortedUAE(unsorted_tones: list[str]) -> list[str]:
  """For some reason (mnemonic?) the canonical ordering of these tone tags is Urgency Agency Exclusivity. They never appear in any other order, although they do appear in every subset. Anyway, this function implements that ordering, regardless of the order the user selected them."""
  sorted_tones = []
  for indicator in tone_indictators_sorted:
    if indicator in unsorted_tones: sorted_tones.append(indicator)
  return sorted_tones

def list_to_bracketeds_string(l: list[str]) -> str:
  s = ""
  is_first_item = True
  for i in l:
    s += " " if not is_first_item else "" #malarkey to space only between bracketeds, not before or after
    is_first_item = False
    s += ("["+i.strip().replace(" ", "_")+"]")
  return s

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

with st.form('query_builder'):
  with st.sidebar:
    st.header("Settings")
    temperature : float = st.slider("Output Variability:", min_value=0.0, max_value=1.0, key="temperature") #temperature: slider between 0 and 1, defaults to 0.7, float
    #character count max, min: int, cannot be negative or 0, starts at 40. floor divide by 4 to get token count to pass to model:
    target_charcount_min = st.number_input("Min Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_min")
    target_charcount_max = st.number_input("Max Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_max")
    if st.experimental_user['email'] == "achang@targetedvictory.com":
      with st.expander("Advanced Parameters"):
        num_beams = st.number_input("num_beams:", min_value=1, format='%d', step=1, key="num_beams", help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.")
        top_k = st.number_input("top_k:", min_value=1, format='%d', step=1, key="top_k" , help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider.")
        top_p = st.number_input("top_p:", min_value=0.0, format='%f', key="top_p" , help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
        repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, max_value=2.0, format='%f', key="repetition_penalty" , help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
        no_repeat_ngram_size = st.number_input("no_repeat_ngram_size:", min_value=0, max_value=10, format='%d', step=1, key="no_repeat_ngram_size" , help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.")
        num_return_sequences = st.number_input("num_return_sequences:", min_value=1, max_value=10, format='%d', step=1, key="num_return_sequences" , help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.")
        early_stopping = st.checkbox("early_stopping", key="early_stopping" , help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
        do_sample = st.checkbox("do_sample", key="do_sample" , help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
        output_scores = st.checkbox("output_scores", key="output_scores" , help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
    if use_experimental_features:
      st.dataframe(rss_df.head())

  account = st.selectbox("Account", [""]+list(account_names), key="account" ) #For some reason, in the current version of streamlit, st.selectbox ends up returning the first value if the index has value is set to None via the key in the session_state, which is a bug, but anyway we work around it using this ridiculous workaround. This does leave a first blank option in there. But whatever.
  ask_type = st.selectbox("Ask Type", ["Fundraising Hard Ask", "Fundraising Medium Ask", "Fundraising Soft Ask", "List Building"], key="ask_type")
  topics = st.multiselect("Topics", ["Bio", "GOP", "Control", "Dems", "Crime", "Military", "GovOverreach", "Religion"], key="topics" )
  additional_topics = [x for x in st.text_input("Additional Topics (Example: Biden, Survey, Deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
  tone = st.multiselect("Tone", tone_indictators_sorted, key="tone")
  generate_button = st.form_submit_button("Submit")

did_a_query = False
if generate_button:
  if account:
    did_a_query = True
    use_count+=1 #this is just an optimization for the front-end display of the query count
    st.session_state['human-facing_prompt'] = (
      ((bios[account]+"\n\n") if "Bio" in topics and account in bios else "") +
      "Write a "+ask_type.lower()+
      " text for "+account+
      " about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+
      ( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) )
    )
    prompt = "<|startoftext|> "+st.session_state['human-facing_prompt']+" <|body|>"
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
    df_prompt = pd.DataFrame(dict_prompt)
    outputs = send(model_uri, databricks_api_token, df_prompt)
    st.session_state['outputs_df'] = pd.DataFrame(outputs, columns=["Model outputs (double click any output to expand it)"]) #Styling this doesn't seem to work, for some reason. Well, whatever.
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.session_state['history'] += outputs
    st.session_state['character_counts_caption'] = "Character counts: "+str([len(o) for o in outputs])

  else:
    st.write("***No account name is selected, so I can't send the request!***")

# The idea is for these output elements to persist after one query button, until overwritten by the results of the next query.
if 'human-facing_prompt' in st.session_state: st.caption(st.session_state['human-facing_prompt'])
if 'outputs_df' in st.session_state: st.dataframe(st.session_state['outputs_df'], hide_index=True, use_container_width=True)
if 'character_counts_caption' in st.session_state: st.caption(st.session_state['character_counts_caption'])

with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
  st.header("History of replies (higher = more recent):")
  if 'history' not in st.session_state: st.session_state['history'] = []
  st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)

login_activity_counter_container.write(f"You are logged in as {st.experimental_user['email']} . You have queried {use_count} {'time' if use_count == 1 else 'times'} today, out of a limit of {use_count_limit}.")

#activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query
if did_a_query:
  no_prompt_dict = str(dict_prompt.pop('prompt'))
  write_to_activity_log_table(datetime=str(datetime.now()), useremail=st.experimental_user['email'], promptsent=prompt, responsegiven=json.dumps(outputs), modelparams=no_prompt_dict)

# html('<!--<script>//you can include arbitrary html and javascript this way</script>-->')
