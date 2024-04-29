#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession
from os import environ

def grow_chat() -> None:
  if not st.session_state.get("chat"):
    st.session_state.chat = ChatSession(model="databricks-dbrx-instruct", system_message="You are a helpful, expert copywriter who specializes in writing text messages and emails for conservative candidates. When responding, don't mention any part of the preceding sentence. Do not mention that you are a helpful, expert copywriter.", max_tokens=3000)
  chat = st.session_state.chat
  if "messages" not in st.session_state:
      st.session_state.messages = []
  p = st.session_state.user_input_for_chatbot_this_frame
  chat.reply(p)
  st.session_state.messages.append({"role": "user", "content": p})
  st.session_state.messages.append({"avatar": 'https://upload.wikimedia.org/wikipedia/commons/4/41/Cicero.PNG', "role": "assistant", "content": chat.last}) #another possible avatar is '📜' #TODO: replace this wikipedia link with a local link(?)

def clear_chat() -> None:
  st.session_state.generated = []
  #st.session_state.past = []
  st.session_state.messages = []
  #st.session_state.user_text = ""

def main() -> None:
  # For some reason this is how databricks wants me to provide these secrets for this API. #COULD: I'm fairly certain st already puts these in the environ, so we could save these lines if we changed the secrets variable names slightly... on the other hand, this is more explicit I guess.
  environ['DATABRICKS_HOST'] = "https://"+st.secrets['DATABRICKS_SERVER_HOSTNAME']
  environ['DATABRICKS_TOKEN'] = st.secrets["databricks_api_token"]
  if st.session_state.get("messages"):
    for message in st.session_state.messages:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$"))

  st.chat_input( "How can I help?", on_submit=grow_chat, key="user_input_for_chatbot_this_frame" )

if __name__ == "__main__": main()
