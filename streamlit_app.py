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

model_uri = st.secrets['model_uri']
databricks_api_token = st.secrets['databricks_api_token']

st.cache_data(ttl="1h")
def load_bios() -> dict[str, str]:
  bios : dict[str, str] = dict(pd.read_csv("Candidate_Bios.csv", index_col="ID").to_dict('split')['data'])
  return bios
bios : dict[str, str] = load_bios()

st.cache_data(ttl="1h")
def load_rss():
  rss_dict = feedparser.parse("http://bothell.carpenter.org:21540")
  rss_df = pd.DataFrame( [ (e['title'], e['description'], e['content'][0]['value']) for e in rss_dict['entries'] ] )
  return rss_df
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
    "top_k": 50,
    "top_p" : 1.0,
    "repetition_penalty" : 1.5,
    "no_repeat_ngram_size" : 4,
    "num_return_sequences" : 4,
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

st.write(f"You are logged in as {st.experimental_user['email']} .")
# TODO: make all the preset/reset stuff use `col1, col2 = st.columns(2)` to space it out "inline" (in html parlance). Possibly also put all of that stuff in an st.form because it will be doing form-like stuff, I imagine.
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
  elif response.status_code != 200:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
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

with st.sidebar:
  st.header("Options for the model:")
  st.caption("These controls can be optionally adjusted to influence the way that the model generates text, such as the length and variety of text the model will attempt to make the text display.")
  temperature : float = st.slider("Textual variety (‘temperature’):", min_value=0.0, max_value=1.0, key="temperature") #temperature: slider between 0 and 1, defaults to 0.7, float
  #character count max, min: int, cannot be negative or 0, starts at 40. floor divide by 4 to get token count to pass to model:
  target_charcount_min = st.number_input("Target number of characters, minimum:", min_value=40, format='%d', step=1, key="target_charcount_min")
  target_charcount_max = st.number_input("Target number of characters, maximum:", min_value=40, format='%d', step=1, key="target_charcount_max")
  with st.expander("Advanced options"):
    num_beams = st.number_input("num_beams:", min_value=1, format='%d', step=1, key="num_beams", help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.")
    top_k = st.number_input("top_k:", min_value=1, format='%d', step=1, key="top_k" , help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider.")
    top_p = st.number_input("top_p:", min_value=0.0, format='%f', key="top_p" , help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
    repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, format='%f', key="repetition_penalty" , help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
    no_repeat_ngram_size = st.number_input("no_repeat_ngram_size:", min_value=0, format='%d', step=1, key="no_repeat_ngram_size" , help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.")
    num_return_sequences = st.number_input("num_return_sequences:", min_value=1, format='%d', step=1, key="num_return_sequences" , help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.")
    early_stopping = st.checkbox("early_stopping", key="early_stopping" , help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
    do_sample = st.checkbox("do_sample", key="do_sample" , help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
    output_scores = st.checkbox("output_scores", key="output_scores" , help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
  st.dataframe(rss_df.head())
  st.header("History of replies (higher = more recent):")

bespoke_title_element = '<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> CICERO</h1>'
st.markdown(bespoke_title_element, unsafe_allow_html=True)

account = st.selectbox("Account", list(bios), key="account" ) #in case you're confused: list of a dict creates a list of the keys of the dict
ask_type = st.selectbox("Ask Type", ["Fundraising Hard Ask", "Fundraising Medium Ask", "Fundraising Soft Ask", "List Building"], key="ask_type")
tone = st.multiselect("Tone", tone_indictators_sorted, key="tone")
topics = st.multiselect("Topics", ["Bio", "GOP", "Control", "Dems", "Crime", "Military", "GovOverreach", "Religion"], key="topics" )
additional_topics = [x for x in st.text_input("Additional Topics (Example: Biden, Survey, Deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
generate_button = st.button("Submit")

if generate_button:
  if account:
    human_facing_prompt = ((bios[account]+"\n\n") if "Bio" in topics else "") +"Write a "+ask_type.lower()+" text for "+account+" about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) )
    # The code block formerly known as "promptify_and_send():"
    st.caption(human_facing_prompt)
    prompt = "<|startoftext|> "+human_facing_prompt+" <|body|>"
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
    st.table(outputs)
    with st.sidebar:
      # History bookkeeping, which only really serves to get around the weird way state is tracked in this app (the history widget won't just automatically update as we assign to the history variable):
      if 'history' not in st.session_state: st.session_state['history'] = []
      st.session_state['history'] += outputs
      st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["outputs"])) ) # reversed for recent=higher #COULD: maybe should have advanced mode where they see all metadata associated with prompt. Also, this ui element can be styled in a special pandas way, I think, as described in the st documentation.
    st.caption("Character counts: "+str([len(o) for o in outputs])+"\n\n*(These character counts should usually be accurate, but if your target platform uses a different character encoding than this one, it may consider the text to have a different number of characters.)*")
  else:
    st.write("No account name is selected, so I can't send the request.")

#TODO: breaking news checkbox/modal dialogue
#COULD: make main and sidebar forms instead? might make juggling state easier https://docs.streamlit.io/library/advanced-features/forms

# html('<!--<script>//you can include arbitrary html and javascript this way</script>-->')
