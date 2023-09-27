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

st.title("💬 Chatbot")
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

if prompt := st.chat_input():
  st.write(prompt)
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(score_model(model_uri, databricks_api_token, text_ids))
  st.write(output[16:-1])
