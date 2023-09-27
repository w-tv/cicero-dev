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
  if response.status_code != 200:
      raise Exception(f"Request failed with status {response.status_code}, {response.text}")
  return response.json()

tone_indictators_sorted = ["[Urgency]", "[Agency]", "[Exclusivity]"]

def sorted_by_tone(unsorted_tones: list[str]) -> list[str]:
  """For some reason (mnemonic?) the canonical ordering of these tone tags is [Urgency] [Agency] [Exclusivity]. They never appear in any other order, although they do appear in every subset. Anyway, this function implements that ordering, regardless of the order the user selected them."""
  sorted_tones = []
  for indicator in tone_indictators_sorted:
    if indicator in unsorted_tones: sorted_tones += indicator
  return sorted_tones

tone = st.multiselect("Tone", tone_indictators_sorted)

if prompt := st.chat_input():
  if tone:
    prompt += " emphasizing "+(" ".join(sorted_by_tone(tone)))
  st.write(prompt)
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(score_model(model_uri, databricks_api_token, text_ids))
  st.write(output[16:-1])
