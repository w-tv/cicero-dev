#!/usr/bin/env -S streamlit run

import streamlit as st
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import consul_show, get_base_url, popup

def grow_chat(streamlit_key_suffix: str = "", alternate_content: str = "") -> None:
  """Note that this function will do something special to the prompt if alternate_content is supplied.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).
  Random fyi: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""
  short_model_name = st.session_state["the_real_dude_model_name"]
  long_model_name = st.session_state["the_real_dude_model"]
  sys_prompt = st.session_state["the_real_dude_system_prompt"] if streamlit_key_suffix else "You are an expert copywriter who specializes in writing fundraising and engagement texts and emails for conservative political candidates in the United States of America. Make sure all messages are in English. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Focus on these five fundraising elements when writing content: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not make up facts or statistics. Do not mention that you are a helpful, expert copywriter. Do not use emojis or hashtags in your messages. Make sure each written message is unique. Write the exact number of messages asked for."
  if not st.session_state.get("chat"):
    st.session_state.chat = {}
  if not st.session_state.get("chat").get(streamlit_key_suffix):
    st.session_state.chat[streamlit_key_suffix] = ChatSession(model=long_model_name, system_message=sys_prompt, max_tokens=4096) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then this line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  chat = st.session_state.chat[streamlit_key_suffix] # Note that, as an object reference, updating and accessing chat will continue to update and access the same object.
  if not st.session_state.get("messages"): # We keep our own list of messages, I think because I found it hard to format the chat_history output when I tried once.
    st.session_state.messages = {}
  if not st.session_state.get("messages").get(streamlit_key_suffix): 
    st.session_state.messages[streamlit_key_suffix] = []
  messages = st.session_state.messages[streamlit_key_suffix] # Note that, as an object reference, updating and accessing messages will continue to update and access the same object.
  if alternate_content:
    p = "Here is a conservative fundraising text: [" + alternate_content + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email. Only provide analysis once, unless the user asks for analysis again."
    display_p = "« " + alternate_content + " »"
  else:
    p = st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
    display_p = p
  old_chat = chat.chat_history.copy()
  while True: #databricks_genai_inference-BUG-WORKAROUND: it prompts with the entire chat history every time, without truncating history to fit the token limit even though this makes it ultimately useless as a chat session manager. Since I now have to manually manage the chat session as well! So, we just try removing messages until it works
    try:
      chat.reply(p)
      messages.append({"role": "user", "content": display_p})
      messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})
      st.session_state["activity_log_payload"] = {"user_email": st.session_state["email"], "prompter_or_chatbot": 'chatbot', "prompt_sent": p, "response_given": chat.last, "model_name": short_model_name, "model_url": chat.model, "model_parameters": str(chat.parameters), "system_prompt": chat.system_message, "base_url": get_base_url()}
      if not streamlit_key_suffix:
        st.session_state["outstanding_activity_log_payload"] = st.session_state["activity_log_payload"]
      break
    except FoundationModelAPIException as e:
      if e.message.startswith('{"error_code":"BAD_REQUEST","message":"Bad request: prompt token count'): # Find out if it's exactly the right error we know how to handle.
        if len(chat.chat_history) <= 2: # This means there is only the system prompt and the current user prompt left, which means the user prompt is simply too long.
          popup("Prompt too long.", "User prompt to chatbot too long, sorry. Try using a shorter one.")
          chat.chat_history = old_chat #remove failed prompt, and also restore all of the message we probably popped off while trying to cull history.
          break
        else:
          consul_show(f"Truncating chat history from {len(chat.chat_history)} messages...")
          chat.chat_history = [chat.chat_history[0]]+chat.chat_history[3:-1]#remove one message-response pair from the start of history, preserving the system message at the beginning. Also remove the failed prompting we've just appended at the end with our other actions. This clause will repeat until the total prompt (the entire history) is small enough that the prompting goes through.
      else: # I guess it's some other error, so crash 🤷
        raise e

def reset_chat(streamlit_key_suffix: str = "") -> None:
  if st.session_state.get("chat"):
    st.session_state["chat"][streamlit_key_suffix] = None
  if st.session_state.get("messages"):
    st.session_state["messages"][streamlit_key_suffix] = None
  if not streamlit_key_suffix: #The user has decided to reset the chat-page chat, so we won't force them to good/bad the last message, which they now can no longer see.
    st.session_state["outstanding_activity_log_payload"] = None # Don't force the user to up/down the cleared message if they reset the chat.

def display_chat(streamlit_key_suffix: str = "") -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).

  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)"""
  if st.session_state.get("messages") and st.session_state.get("messages").get(streamlit_key_suffix):
    for message in st.session_state.messages[streamlit_key_suffix]:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\["))
  if st.session_state.get("outstanding_activity_log_payload") and not streamlit_key_suffix:
    emptyable = st.empty()
    with emptyable.container():
      c1, c2, c3, c4 = st.columns([.04,.04,.01,.92], gap='small', vertical_alignment="center")
      user_feedback = "good" if c1.button("👍︎", key="👍"+streamlit_key_suffix) else "bad" if c2.button("👎︎", key="👎"+streamlit_key_suffix) else None
      c3.write('')
      c4.write("***Did Cicero understand your request? Let us know to continue chatting.***")
    if user_feedback:
      emptyable.empty()
      st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix,) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text...
      st.session_state["outstanding_activity_log_payload_fulfilled"] = st.session_state["outstanding_activity_log_payload"] | {"user_feedback": user_feedback}
      st.session_state["outstanding_activity_log_payload"] = None
  else:
    st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix,) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.)

def main() -> None: # It's convenient to import cicero_chat in other files, to use its function in them, so we do a main() here so we don't run this code on startup.
  st.write('''**Chat freeform with Cicero directly ChatGPT-style!**  \nHere are some ideas: rewrite copy, make copy longer, convert a text into an email, or write copy based off a starter phrase/quote.''')
  if st.button("Reset"):
    reset_chat()
  display_chat()

if __name__ == "__main__":
  main()