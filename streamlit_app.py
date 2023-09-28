from collections import namedtuple
import altair as alt
import pandas as pd
import streamlit as st
import subprocess
from transformers import AutoTokenizer
import torch
import pandas as pd
import requests
import json

st.title("💬 Cicero")
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

tone_indictators_sorted = ["[Urgency]", "[Agency]", "[Exclusivity]"]

def sorted_by_tone(unsorted_tones: list[str]) -> list[str]:
  """For some reason (mnemonic?) the canonical ordering of these tone tags is [Urgency] [Agency] [Exclusivity]. They never appear in any other order, although they do appear in every subset. Anyway, this function implements that ordering, regardless of the order the user selected them."""
  sorted_tones = []
  for indicator in tone_indictators_sorted:
    if indicator in unsorted_tones: sorted_tones.append(indicator)
  return sorted_tones

account = st.selectbox("Account", ["Tim Scott", "Steve Scalise"])
ask_type = st.selectbox("Ask type", ["fundraising hard ask text", "list building text", "fundraising medium ask text", "fundraising soft ask text", "other text"])
tone = st.multiselect("Tone", tone_indictators_sorted)
topics = st.text_input("Topics (write them like so: [GOP] [Control] [Dems] [Crime] [Military])", tone_indictators_sorted)

if prompt := st.chat_input("Or, compose a full message here."):
prompt = "Write a "ask_type+" for "++prompt+
  if tone:
    prompt += " emphasizing "+(" ".join(sorted_by_tone(tone)))
  st.write(prompt)
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(score_model(model_uri, databricks_api_token, text_ids))
  st.write(output[16:-1])
