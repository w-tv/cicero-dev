#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import sql_call_cacheless, consul_show, get_base_url

def grow_chat(streamlit_key_suffix: str = "", independent_rewrite: bool = False, alternate_content: str = "", display_only_this_at_first_blush: str|None = None) -> None:
  # the streamlit_key_suffix is only necessary because we use this code in two places #TODO: actually, it's not clear that we want to do that. And, the chat histories overlap, currently... So, maybe rethink this concept later. I don't even know why we have two of them. Maybe they were supposed to mutate in concept independently?
  short_model_name = st.session_state["the_real_dude_model_name"]
  long_model_name = st.session_state["the_real_dude_model"]
  sys_prompt = st.session_state["the_real_dude_system_prompt"]
  if not st.session_state.get("chat"):
    # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then the following line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
    st.session_state.chat = ChatSession(model=long_model_name, system_message=sys_prompt, max_tokens=4096)
  if not st.session_state.get("messages"): # We keep our own list of messsages, I think because I found it hard to format the chat_history output when I tried once. 
    st.session_state.messages = []
  p: str = alternate_content or st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
  if independent_rewrite and not st.session_state.messages:
    p = "Here is a conservative fundraising text or email: [" + p + "] Analyze the quality of the text or email based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, rewrite the text based off of your analysis. Keep the overall message the same, but feel free to change the sentence structure or tone."
  while True: #databricks_genai_inference-BUG-WORKAROUND: it prompts with the entire chat history every time, without truncating history to fit the token limit even though this makes it ultimately useless as a chat session manager. Since I now have to manually manage the chat session as well! So, we just try removing messages until it works
    try:
      st.session_state.chat.reply(p)
      st.session_state.messages.append({"role": "user", "content": display_only_this_at_first_blush or p})
      st.session_state.messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": st.session_state.chat.last})
      # Write to the chatbot activity log: (or, rather, tee up that work for later.)
      st.session_state["chatbot_activity_log_payload"] = {"user_email": st.session_state["email"], "prompter_or_chatbot": 'chatbot', "prompt_sent": p, "response_given": st.session_state.chat.last, "model_name": short_model_name, "model_url": st.session_state.chat.model, "model_parameters": str(st.session_state.chat.parameters), "system_prompt": st.session_state.chat.system_message, "base_url": get_base_url()}
      break
    except FoundationModelAPIException as e:
      if e.message.startswith('{"error_code":"BAD_REQUEST","message":"Bad request: prompt token count'): # Find out if it's exactly the right error we know how to handle.
        # Random info: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]
        if len(st.session_state.chat.chat_history) <= 2: # This means there is only the system prompt and the current user prompt left, which means the user prompt is simply too long.
          @st.experimental_dialog("Prompt too long.")
          def _() -> None:
            st.write("User prompt to chatbot too long, sorry. Try using a shorter one.")
            st.caption("Press enter or click the ❌︎ in the upper-right corner to close this message.")
          _()
          st.session_state.chat.chat_history.pop() #remove failed prompt
          break
        else:
          consul_show(f"Truncating chat history from {len(st.session_state.chat.chat_history)} messages...")
          st.session_state.chat.chat_history = [st.session_state.chat.chat_history[0]]+st.session_state.chat.chat_history[3:-1]#remove one message-response from the start of history, preserving the system message at the beginning. Also remove the failed prompt we've generated at the end. This clause will repeat until the prompt is small enough that the prompting goes through.
      else: # I guess it's some other error, so crash 🤷
        raise e

def reset_chat() -> None:
  st.session_state["chat"] = None
  st.session_state["messages"] = None

def display_chat(streamlit_key_suffix: str = "", independent_rewrite: bool = False) -> None:
  """*A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)"""
  # Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  if st.session_state.get("messages"):
    for message in st.session_state.messages:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\[")) #COULD: remove the \[ escaping, which is only useful for, what, markdown links? Which nobody uses.
  st.chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix, independent_rewrite) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second.

def main() -> None:
  options = st.radio(label='Design Options (Not our only options)', options=['Option 1', 'Option 2', 'Option 3'])
  st.markdown(
  """<style>
      div[class*="stRadio"] > label > div[data-testid="stMarkdownContainer"] > p {font-size: 24px;}
    </style>""", unsafe_allow_html=True)
  if options=='Option 1':
    st.markdown('This is where you can chat with Cicero directly! You can do things like:\n- Rewrite a Text\n- Write a text based off a seed phrase/quote\n- MORE!')
  
  if options=='Option 2':
    chat_type = st.radio(label='This is where you can chat with Cicero directly! You can do things like:', options=['Rewrite a Text/Email', 'Write a message based off a seed phrase/quote', 'MORE!'], horizontal=True)
    if chat_type == 'Rewrite a Text/Email':
      st.write("Paste the text or email you want rewritten into the box below.")
    if chat_type == 'Write a message based off a seed phrase/quote':
      st.write("Paste the phrase or quote into the box below.")
  
  if st.button("Reset (erase) chat"):
    reset_chat()
  display_chat(independent_rewrite=True)

if __name__ == "__main__": main()
