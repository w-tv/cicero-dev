#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession
from os import environ

def main() -> None:
    # For some reason this is how databricks wants me to provide these secrets for this API. #COULD: I'm fairly certain st already puts these in the environ, so we could save these lines if we changed the secrets variable names slightly... on the other hand, this is more explicit I guess.
    environ['DATABRICKS_HOST'] = "https://"+st.secrets['DATABRICKS_SERVER_HOSTNAME']
    environ['DATABRICKS_TOKEN'] = st.secrets["databricks_api_token"]

    def clear_chat() -> None:
        st.session_state.generated = []
        st.session_state.past = []
        st.session_state.messages = []
        st.session_state.user_text = ""

    if not st.session_state.get("chat"): st.session_state.chat = ChatSession(model="databricks-dbrx-instruct", system_message="You are a helpful, expert copywriter who specializes in writing text messages and emails for conservative candidates. When responding, don't mention any part of the preceding sentence. Do not mention that you are a helpful, expert copywriter.", max_tokens=3000)
    chat = st.session_state.chat
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    def query_api(example_prompt: str) -> str:
        chat.reply(example_prompt)
        reveal_type(chat)
        reveal_type(chat.last)
        return chat.last

    # TODO: create a function that queries the model, and then query the model in here, and then just do the markdown stuff, maybe that will work
    if prompt := st.chat_input("How can I help?", key=1):
        api_reply = query_api(prompt)
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt.replace("$", r"\$"))
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.write(api_reply.replace("$", r"\$"))
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": api_reply})

if __name__ == "__main__": main()
