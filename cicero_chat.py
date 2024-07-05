#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import consul_show, get_base_url, popup

def grow_chat(streamlit_key_suffix: str = "", alternate_content: str = "") -> None:
  """Note that this function will do something special to the prompt if there are no messages yet.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places.
  Random info: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""
  short_model_name = st.session_state["the_real_dude_model_name"]
  long_model_name = st.session_state["the_real_dude_model"]
  sys_prompt = st.session_state["the_real_dude_system_prompt"]
  if not st.session_state.get("chat"):
    st.session_state.chat = ChatSession(model=long_model_name, system_message=sys_prompt, max_tokens=4096) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then this line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  if not st.session_state.get("messages"): # We keep our own list of messages, I think because I found it hard to format the chat_history output when I tried once. 
    st.session_state.messages = []
  p: str = alternate_content or st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
  if not st.session_state.messages:
    display_p = "« "+p+" »"
    p = "Here is a conservative fundraising text: [" + p + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email."
  else:
    display_p = p
  old_chat = st.session_state.chat.chat_history.copy()
  while True: #databricks_genai_inference-BUG-WORKAROUND: it prompts with the entire chat history every time, without truncating history to fit the token limit even though this makes it ultimately useless as a chat session manager. Since I now have to manually manage the chat session as well! So, we just try removing messages until it works
    try:
      st.session_state.chat.reply(p)
      st.session_state.messages.append({"role": "user", "content": display_p})
      st.session_state.messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": st.session_state.chat.last})
      st.session_state["activity_log_payload"] = {"user_email": st.session_state["email"], "prompter_or_chatbot": 'chatbot', "prompt_sent": p, "response_given": st.session_state.chat.last, "model_name": short_model_name, "model_url": st.session_state.chat.model, "model_parameters": str(st.session_state.chat.parameters), "system_prompt": st.session_state.chat.system_message, "base_url": get_base_url()}
      st.session_state["outstanding_activity_log_payload"] = st.session_state["activity_log_payload"]
      break
    except FoundationModelAPIException as e:
      if e.message.startswith('{"error_code":"BAD_REQUEST","message":"Bad request: prompt token count'): # Find out if it's exactly the right error we know how to handle.
        if len(st.session_state.chat.chat_history) <= 2: # This means there is only the system prompt and the current user prompt left, which means the user prompt is simply too long.
          popup("Prompt too long.", "User prompt to chatbot too long, sorry. Try using a shorter one.")
          st.session_state.chat.chat_history = old_chat #remove failed prompt, and also restore all of the message we probably popped off while trying to cull history.
          break
        else:
          consul_show(f"Truncating chat history from {len(st.session_state.chat.chat_history)} messages...")
          st.session_state.chat.chat_history = [st.session_state.chat.chat_history[0]]+st.session_state.chat.chat_history[3:-1]#remove one message-response pair from the start of history, preserving the system message at the beginning. Also remove the failed prompting we've just appended at the end with our other actions. This clause will repeat until the total prompt (the entire history) is small enough that the prompting goes through.
      else: # I guess it's some other error, so crash 🤷
        raise e

def reset_chat() -> None:
  st.session_state["chat"] = None
  st.session_state["messages"] = None
  #TODO: should this also clear st.session_state.get("outstanding_activity_log_payload")? Right now it still forces the user to up/down it.

def display_chat(streamlit_key_suffix: str = "") -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function.
  Known issue: if you click fast enough, you can get significant UI ghosting on this page.
  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)"""
  if st.session_state.get("messages"):
    for message in st.session_state.messages:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\["))
  if st.session_state.get("outstanding_activity_log_payload"):
    c1, c2, c3 = st.columns([.04,.04,.92])
    user_feedback = "good" if c1.button("👍︎", key="👍"+streamlit_key_suffix) else "bad" if c2.button("👎︎", key="👎"+streamlit_key_suffix) else None
    c3.write("***Was this output what you were looking for?***")
    if user_feedback:
      st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix,) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text... #The container is not related to the ghosting, by the way. The ghosting happens either way.
      st.session_state["outstanding_activity_log_payload_fulfilled"] = st.session_state["outstanding_activity_log_payload"] | {"user_feedback": user_feedback}
      st.session_state["outstanding_activity_log_payload"] = None
  else:
    st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix,) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.)

st.markdown('This is where you can chat with Cicero directly! You can do things like: rewrite a text, write a text based off a seed phrase/quote, fall in love, and SO MUCH MORE!')
if st.button("Reset (erase) chat"):
  reset_chat()
display_chat()
