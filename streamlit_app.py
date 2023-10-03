from collections import namedtuple
import altair as alt
import streamlit as st
import subprocess
from transformers import AutoTokenizer
import torch
import pandas as pd
import requests
import json

bespoke_title_element = '<h1><img src="https://targetedvictory.com/wp-content/uploads/2019/07/favicon.png" alt="💬" style="display:inline-block; height:1em; width:auto;"> Cicero</h1>'
st.markdown(bespoke_title_element, unsafe_allow_html=True)
st.markdown('<script>alert();</script>', unsafe_allow_html=True)
st.caption("It's pronounced ‘Kickero’")
model_uri = 'https://dbc-ca8d208b-aaa9.cloud.databricks.com/serving-endpoints/pythia/invocations'
databricks_api_token = 'dapi360d025c9e135c809de05abbf3196a06'

def create_tf_serving_json(data):
  return {'inputs': {name: data[name].tolist() for name in data.keys()} if isinstance(data, dict) else data.tolist()}

def score_model(model_uri, databricks_token, data):
  headers = {
    "Authorization": f"Bearer {databricks_token}",
    "Content-Type": "application/json",
  }
  data_json = json.dumps({'dataframe_records': data.to_dict(orient='records')}) if isinstance(data, pd.DataFrame) else create_tf_serving_json(data)
  response = requests.request(method='POST', headers=headers, url=model_uri, json=data_json)
  if response.status_code == 504:
    return score_model(model_uri, databricks_token, data) #we recursively call this until the machine wakes up.
  elif response.status_code != 200:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return response.json()

def tokenize_and_send(prompt):
  st.write(prompt)
  prompt = "<|startoftext|> "+prompt+" <|body|>"
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(score_model(model_uri, databricks_api_token, text_ids))
  st.write(output[16:-1]) #I guess we don't like the first 16, and last 1, characters of this for some reason. Note: I have been informed that the first 16 and last 1 characters are, like "Response: { " and "}" or something.

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

account = st.selectbox("Account", ["Tim Scott", "Steve Scalise"])
ask_type = st.selectbox("Ask type", ["fundraising hard ask text", "fundraising medium ask text", "fundraising soft ask text", "list building text", "other text"])
tone = st.multiselect("Tone", tone_indictators_sorted)
topics = st.multiselect("Topics", ["GOP", "Control", "Dems", "Crime", "Military", "GovOverreach", "Religion"])
additional_topics = [x for x in st.text_input("Additional topics (free text entry, separated by commas. Example: China, State of the Race, Match)").split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
generate_button = st.button("Generate a message based on the above by clicking this button!")

#TODO: add bio dict and add the bio to context before prompt. In tokenize_and_send I guess. Maybe rename that to "fluff and send".
#TODO: breaking news checkbox
if generate_button:
  button_prompt = "Write a "+ask_type+" for "+account+" about: "+list_to_bracketeds_string(topics+additional_topics or ["No_Hook"])+( "" if not tone else " emphasizing "+ list_to_bracketeds_string(sortedUAE(tone)) )
  tokenize_and_send(button_prompt)
