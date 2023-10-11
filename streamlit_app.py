from collections import namedtuple
import altair as alt
import streamlit as st
from streamlit.components.v1 import html
import subprocess
from transformers import AutoTokenizer
import torch
import pandas as pd
import requests
import json

with st.sidebar:
  st.header("Options for the model:")
  st.caption("These controls can be optionally adjusted to influence the way that the model generates text, such as the length and variety of text the model will attempt to make the text display. Also, none of these controls are hooked up to anything yet, so they don't yet do anything!")
  temperature : float = st.slider("Textual variety (‘temperature’):", min_value=0.0, max_value=1.0, value=0.7) #temperature: slider between 0 and 1, defaults to 0.7, pass this value into prompt, float
  #character count max, min - must be int, cannot be negative or 0, divide by 4 and pass into prompt; integer input?:
  target_charcount_min = st.number_input("Target number of characters, minimum:", min_value=1, value=None, format='%d', step=1)
  target_charcount_max = st.number_input("Target number of characters, maximum:", min_value=1, value=None, format='%d', step=1)
  st.header("History of replies (higher = more recent):")

bespoke_title_element = '<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>'
st.markdown(bespoke_title_element, unsafe_allow_html=True)
bios : dict[str, str] = dict(pd.read_csv("Candidate_Bios.csv", index_col="ID").to_dict('split')['data'])
model_uri = st.secrets['model_uri']
databricks_api_token = st.secrets['databricks_api_token']

def create_tf_serving_json(data):
  return {'inputs': {name: data[name].tolist() for name in data.keys()} if isinstance(data, dict) else data.tolist()}

def send(model_uri, databricks_token, data):
  headers = {
    "Authorization": f"Bearer {databricks_token}",
    "Content-Type": "application/json",
  }
  data_json = json.dumps({'dataframe_records': data.to_dict(orient='records')}) if isinstance(data, pd.DataFrame) else create_tf_serving_json(data)
  response = requests.request(method='POST', headers=headers, url=model_uri, json=data_json)
  if response.status_code == 504:
    return send(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
  elif response.status_code != 200:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return response.json()

def tokenize_and_send(prompt):
  st.caption(prompt)
  prompt = "<|startoftext|> "+prompt+" <|body|>"
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(send(model_uri, databricks_api_token, text_ids))
  pure_output = output[16:-1] #I guess we don't like the first 16, and last 1, characters of this for some reason. Note: I have been informed that the first 16 and last 1 characters are, like "Response: { " and "}" or something.
  st.write(pure_output)
  with st.sidebar:
    # History bookkeeping, which only really serves to get around the weird way state is tracked in this app (the history widget won't just automatically update as we assign to the history variable):
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.session_state['history'].append(pure_output)
    st.dataframe( list(reversed( st.session_state['history'] )) ) # reversed for recent=higher #COULD: maybe should have advanced mode where they see all metadata associated with prompt. Also, this ui element can be styled in a special pandas way, I think, as described in the st documentation.
  st.caption("Character count: "+str(len(pure_output))+"\n\n*(This character count should usually be accurate, but if your target platform uses a different character encoding than this one, it may consider the text to have a different number of characters.)*")

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

account = st.selectbox("Account", list(bios)) #in case you're confused: list of a dict creates a list of the keys of the dict
ask_type = st.selectbox("Ask Type", ["Fundraising Hard Ask", "Fundraising Medium Ask", "Fundraising Soft Ask", "List Building"])
tone = st.multiselect("Tone", tone_indictators_sorted)
topics = st.multiselect("Topics", ["Bio", "GOP", "Control", "Dems", "Crime", "Military", "GovOverreach", "Religion"])
additional_topics = [x for x in st.text_input("Additional Topics (Example: Biden, Survey, Deadline)").split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
generate_button = st.button("Submit")
if st.button("Reset all fields"): st.runtime.legacy_caching.clear_cache() #let's see if this works

#TODOS: breaking news checkbox
#     Add reset button to page to clear all parameters, reset to defaults
#    allow for creation of presets (does not need to last between sessions) (for now)

if generate_button:
  button_prompt = ((bios[account]+"\n\n") if "Bio" in topics else "") +"Write a "+ask_type.lower()+" text for "+account+" about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) )
  tokenize_and_send(button_prompt)

# html('<!--<script>//you can include arbitrary html and javascript this way</script>-->')
