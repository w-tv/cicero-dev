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

#Make default state, and other presets, so we can manage presets and resets.
st.session_state.presets = {
  "default": {
    {"top_k": 50},
  },
}
st.session_state.current_preset = st.session_state.presets.default

with st.sidebar:
  st.header("Options for the model:")
  st.caption("These controls can be optionally adjusted to influence the way that the model generates text, such as the length and variety of text the model will attempt to make the text display.")
  temperature : float = st.slider("Textual variety (‘temperature’):", min_value=0.0, max_value=1.0, value=0.7) #temperature: slider between 0 and 1, defaults to 0.7, float
  #character count max, min: int, cannot be negative or 0, I guess it has to be above about 40. floor divide by 4 to get token count to pass to model:
  target_charcount_min = st.number_input("Target number of characters, minimum:", min_value=40, value=160, format='%d', step=1)
  target_charcount_max = st.number_input("Target number of characters, maximum:", min_value=40, value=80, format='%d', step=1)
  with st.expander("Advanced options (not yet hooked up)"):
    #TODO: not hooked up yet
    num_beams = st.number_input("num_beams:", min_value=1, value=1, format='%d', step=1, help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.")
    top_k = st.number_input("top_k:", min_value=1, value=st.session_state.current_preset, format='%d', step=1, help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider.")
    top_p = st.number_input("top_p:", min_value=0.0, value=1.0, format='%f', help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
    repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, value=1.5, format='%f', help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
    no_repeat_ngram_size = st.number_input("no_repeat_ngram_size:", min_value=0, value=4, format='%d', step=1, help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.")
    num_return_sequences = st.number_input("num_return_sequences:", min_value=1, value=4, format='%d', step=1, help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.")
    early_stopping = st.checkbox("early_stopping", value=False, help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
    do_sample = st.checkbox("do_sample", value=True, help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
    output_scores = st.checkbox("output_scores", value=False, help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
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
  ds_dict = {'dataframe_split': data.to_dict(orient='split')} if isinstance(data, pd.DataFrame) else create_tf_serving_json(data)
  data_json = json.dumps(ds_dict, allow_nan=True)
  response = requests.request(method='POST', headers=headers, url=model_uri, data=data_json)
  if response.status_code == 504:
    return send(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
  elif response.status_code != 200:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return response.json()

def promptify_and_send(prompt):
  st.caption(prompt)
  prompt = "<|startoftext|> "+prompt+" <|body|>"
  dict_prompt = {"prompt": [prompt],
                  "temperature": [temperature],
                  "max_new_tokens": [int(target_charcount_max) // 4],
                  "min_new_tokens": [int(target_charcount_min) // 4],
                  "num_beams": [1],
                  "top_k": [100],
                  "top_p": [0.9],
                  "repetition_penalty": [1.5],
                  "no_repeat_ngram_size": [4],
                  "num_return_sequences": [4],
                  "early_stopping": [True],
                  "do_sample": [True],
                  "output_scores": [False]
                }
  df_prompt = pd.DataFrame(dict_prompt)
  output = str(send(model_uri, databricks_api_token, df_prompt))
  pure_output = output[16:-1]
  st.write(pure_output)
  with st.sidebar:
    # History bookkeeping, which only really serves to get around the weird way state is tracked in this app (the history widget won't just automatically update as we assign to the history variable):
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.session_state['history'].append(pure_output)
    st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["outputs"])) ) # reversed for recent=higher #COULD: maybe should have advanced mode where they see all metadata associated with prompt. Also, this ui element can be styled in a special pandas way, I think, as described in the st documentation.
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
ask_type = st.selectbox("Ask Type", ["Fundraising Hard Ask", "Fundraising Medium Ask", "Fundraising Soft Ask", "List Building"], key="ask_type")
tone = st.multiselect("Tone", tone_indictators_sorted)
topics = st.multiselect("Topics", ["Bio", "GOP", "Control", "Dems", "Crime", "Military", "GovOverreach", "Religion"])
additional_topics = [x for x in st.text_input("Additional Topics (Example: Biden, Survey, Deadline)").split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
generate_button = st.button("Submit")
if st.button("Reset all fields"): st.rerun() #COULD: implement later, along with presets. The user currently just has to f5

#TODOS: breaking news checkbox
#     Add reset button to page to clear all parameters, reset to defaults #this is how: https://discuss.streamlit.io/t/change-the-state-of-an-item-from-code/1429/4 also https://docs.streamlit.io/library/api-reference/layout/st.container but I'm not sure that has a empty() method on it you can call... I guess vs code autocomplete would know.
#    allow for creation of presets (does not need to last between sessions) (for now)

if generate_button:
  button_prompt = ((bios[account]+"\n\n") if "Bio" in topics else "") +"Write a "+ask_type.lower()+" text for "+account+" about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) )
  promptify_and_send(button_prompt)

# html('<!--<script>//you can include arbitrary html and javascript this way</script>-->')
