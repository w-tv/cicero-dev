from collections import namedtuple
import altair as alt
import pandas as pd
import streamlit as st


import subprocess

# Define the library you want to install
# library_name = "transformers"  # Change this to the library you want to install

# try:
#     # Run pip install command
#     subprocess.check_call(["pip", "install", library_name])
#     print(f"{library_name} installed successfully!")
# except subprocess.CalledProcessError as e:
#     print(f"Error installing {library_name}: {e}")
# except Exception as e:
#     print(f"An error occurred: {e}")

    # Define the library you want to install
# library_name = "torch"  # Change this to the library you want to install

# try:
#     # Run pip install command
#     subprocess.check_call(["pip", "install", library_name])
#     print(f"{library_name} installed successfully!")
# except subprocess.CalledProcessError as e:
#     print(f"Error installing {library_name}: {e}")
# except Exception as e:
#     print(f"An error occurred: {e}")

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

# for msg in st.session_state.messages:
#   st.chat_message(msg["role"]).write(msg["content"])
if prompt := st.chat_input():
  # st.session_state.messages.append({"role": "user", "content": prompt})
  # st.chat_message("user").write(prompt)
  tokenizer = AutoTokenizer.from_pretrained("EleutherAI/pythia-160m-deduped")
  text_ids = tokenizer.encode(prompt, return_tensors = 'pt')
  output = str(score_model(model_uri, databricks_api_token, text_ids))
  st.write(output[16:-1])


# First
import streamlit as st
# with st.sidebar:
#     openai_api_key = st.text_input("OpenAI API Key", key="chatbot_api_key", type="password")
#     "[Get an OpenAI API key](https://platform.openai.com/account/api-keys)"
#     "[View the source code](https://github.com/streamlit/llm-examples/blob/main/Chatbot.py)"
#     "[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/streamlit/llm-examples?quickstart=1)"

# st.title("💬 Chatbot")
# if "messages" not in st.session_state:
#     st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]

# for msg in st.session_state.messages:
#     st.chat_message(msg["role"]).write(msg["content"])

# if prompt := st.chat_input():
#     if not openai_api_key:
#         st.info("Please add your OpenAI API key to continue.")
#         st.stop()


  # st.session_state.messages.append({"role": "user", "content": prompt})
  # st.chat_message("user").write(prompt)
  # response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=st.session_state.messages)
  # msg = response.choices[0].message
  # st.session_state.messages.append(msg)
  # st.chat_message("assistant").write(msg.content)
