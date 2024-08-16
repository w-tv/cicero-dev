#!/usr/bin/env -S streamlit run

"""Cicero (the actual, historical man (it's really him))."""

import streamlit as st
from datetime import datetime, timedelta
import time
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import consul_show, is_dev, ssget, ssset, ssmut, get_base_url, popup, typesafe_selectbox
from cicero_types import Short_Model_Name, short_model_names, short_model_name_default, short_model_name_to_long_model_name
import bs4, requests, re # for some reason bs4 is how you import beautifulsoup smh smh

def pii_detector(input: str) -> list[str]:
  phone = re.findall(
    r"""((?:(?<![\d-])(?:\+?\d{1,3}[-.\s*]?)?(?:\(?\d{3}\)?[-.\s*]?)?\d{3}[-.\s*]?\d{4}(?![\d-]))|(?:(?<![\d-])(?:(?:\(\+?\d{2}\))|(?:\+?\d{2}))\s*\d{2}\s*\d{3}\s*\d{4}(?![\d-])))"""
  , input)
  email = re.findall(
    r"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    input,
    re.IGNORECASE,
  )
  credit_card = re.findall(r"((?:(?:\\d{4}[- ]?){3}\\d{4}|\\d{15,16}))(?![\\d])", input)
  street_address = re.findall(
    r"\d{1,4} [\w\s]{1,20}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\W?(?=\s|$)",
    input,
    re.IGNORECASE,
  )
  pii_list: list[str] = phone + email + credit_card + street_address
  return pii_list

@st.dialog(title='PII detected!', width="large")
def pii_dialog(input: str, pii_list: list[str], streamlit_key_suffix: str, keyword_arguments: dict[str, str|None]) -> None:
  st.write("Cicero noticed that there might be PII in your message!\n\nMessage:")
  st.code(input)
  st.write("Potential PII:")
  st.code(pii_list)
  st.write('Would you still like to submit the prompt?')
  col1, col2, _col3, _col4 = st.columns(spec=[.17, .23, .30, .30], gap='small', vertical_alignment='center')
  with col1:
    if st.button("Yes, submit"):
      ssset( "pii_interrupt_state", streamlit_key_suffix, (True, input, keyword_arguments) ) #the true means true, continue
      st.rerun()
  with col2:
    if st.button("No, keep editing"):
      ssset( "pii_interrupt_state", streamlit_key_suffix, (False, input, keyword_arguments) ) #the false means false, do not continue
      st.rerun()

def content_from_url(url: str) -> str:
  forbiddens = ["winred.com", "fed.gov", "example.com/bad"] #example.com/bad is supposed to let you test this code without the risk of going to an actual forbidden website if the forbidding code fails. # If testing this function: please note that due to the regex, 'winred.com' on its own is not captured as a url; only eg https://winred.com/ is.
  for forbade in forbiddens:
    if forbade in url.lower(): # This is just a string-contains, which could false-positive on, say, example.com/winred.com.txt, but that's probably fine. # It could also easily be beaten by a link shortener, but "it will never occur to them" 😄
      st.toast(f"Unfortunately, urls from {forbade} are not allowed. Continued without.") # This is a toast to make sure it doesn't overlap with the popup, as only one dialog is allowed at a time or streamlit throws a don't-do-that exception.
      return "" #early out, return nothing (not even the url).
  # from https://stackoverflow.com/questions/69593352/how-to-get-all-copyable-text-from-a-web-page-python/69594284#69594284
  response = requests.get(url,headers={'User-Agent': 'Mozilla/5.0'})
  soup = bs4.BeautifulSoup(response.text, 'html.parser')
  if b := soup.body:
    text = b.get_text(' ', strip=True)
    if len(text) > 4000:
      text = text[:4000]
    return text
  else:
    return "" # there is no content on the page, I guess, so the correct thing to return is the empty string.

def content_from_url_regex_match(m: re.Match[str]) -> str:
  count = ssmut(lambda x: (x or 0) + 1, "urls_we_have_expanded_right_now")
  if count == 1:
    new_str = content_from_url(m.group(0))
    if is_dev(): #Note: appears at top of page, since we're in a callback and thus run first thing in the run.
      st.expander("\n\nDeveloper Mode Message: url content").caption(new_str.replace("$", r"\$"))
  else:
    new_str = ""
    if count == 2:
      st.toast("1 website at a time please")
  return new_str

url_regex = r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""" # from https://gist.github.com/gruber/249502

def detect_url_content(s: str) -> bool:
  return False if re.search(pattern=url_regex, string=s) is None else True

def expand_url_content(s: str) -> str:
  """Expand the urls in a string to the content of their contents (placing said contents back into the same containing string."""
  return re.sub(pattern=url_regex, repl=content_from_url_regex_match, string=s)

def grow_chat(streamlit_key_suffix: str = "", alternate_content: str|None = None, account: str|None = None, short_model_name: Short_Model_Name = short_model_name_default) -> None:
  """Note that this function will do something special to the prompt if alternate_content is supplied.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).
  Random fyi: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""
  keyword_arguments = locals()
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)
  if streamlit_key_suffix=="_prompter":
    sys_prompt = "You are a helpful, expert copywriter who specializes in writing fundraising text messages and emails for conservative candidates and causes. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Do not mention that you are a helpful, expert copywriter."
  elif streamlit_key_suffix=="_corporate":
    sys_prompt = "You are a helpful, expert marketer. Do not mention that you are a helpful, expert marketer."
    #TODO: account #This field will be read from the cicero.ref_tables.corp_acc table, which currently doesn't exist. the idea is we create custom system prompts containing information about the client and some example material
  else:
    sys_prompt = "You are an expert copywriter who specializes in writing fundraising and engagement texts and emails for conservative political candidates in the United States of America. Make sure all messages are in English. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Focus on these five fundraising elements when writing content: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not make up facts or statistics. Do not mention that you are a helpful, expert copywriter. Do not use emojis or hashtags in your messages. Make sure each written message is unique. Write the exact number of messages asked for."
  if not st.session_state.get("chat"):
    st.session_state.chat = {}
  if not ssget("chat", streamlit_key_suffix):
    st.session_state.chat[streamlit_key_suffix] = ChatSession(model=short_model_name_to_long_model_name(short_model_name), system_message=sys_prompt, max_tokens=4096) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then this line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  chat = st.session_state.chat[streamlit_key_suffix] # Note that, as an object reference, updating and accessing chat will continue to update and access the same object.
  if not st.session_state.get("messages"): # We keep our own list of messages, I think because I found it hard to format the chat_history output when I tried once.
    st.session_state.messages = {}
  if not ssget("messages", streamlit_key_suffix):
    st.session_state.messages[streamlit_key_suffix] = []
  messages = st.session_state.messages[streamlit_key_suffix] # Note that, as an object reference, updating and accessing messages will continue to update and access the same object.
  if alternate_content:
    p = "Here is a conservative fundraising text: [" + alternate_content + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email. Only provide analysis once, unless the user asks for analysis again."
    display_p = "« " + alternate_content + " »"
  elif pii and pii[0]: #there was pii, and we are continuing
    p = pii[1]
    display_p = p
  else:
    p = st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
    display_p = p

  continue_prompt = True
  if possible_pii := pii_detector(p):
    pii_state = ssget("pii_interrupt_state", streamlit_key_suffix)
    if pii_state is None:
      st.session_state.pii_interrupt_state = {}
    if pii_state and pii_state[0]: #if the field is true, we continue
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since we're going to send this one and get a new circumstance later.
    else:
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since the dialog is about to set it, and this prevents funny business from x-ing the dialogue.
      pii_dialog(p, possible_pii, streamlit_key_suffix, keyword_arguments)
      continue_prompt = False

  if streamlit_key_suffix=="_corporate": #implement url content expansion, at this point only for the corp chat
    if detect_url_content(p):
      if "last_link_time" in st.session_state:
        time_difference = datetime.now() - st.session_state["last_link_time"]
        if time_difference < timedelta(seconds=27): # It's 27 because we don't want to alert the user if they just have to wait another second or two. The query already takes that long, probably.
          remaining_seconds = round( 30 - time_difference.total_seconds() )
          popup("Throttled!", f"Out of an abundance of caution, link reading is throttled to once every thirty seconds per user. Therefore your request has been delayed by {remaining_seconds} seconds. Sorry for the inconvenience. Please let Optimization know if this is a big problem.") # Festina lente! #Unfortunately I think an unreported bug in streamlit means this dialog only ever shows once per session. But that's ok in this case.
          time.sleep(remaining_seconds)
      st.session_state["last_link_time"] = datetime.now()
    p = expand_url_content(p)
    ssset("urls_we_have_expanded_right_now", 0) # Have to reset this value in this remote place for flow-control reasons :/

  if continue_prompt:
    old_chat = chat.chat_history.copy()
    while True: #databricks_genai_inference-BUG-WORKAROUND: it prompts with the entire chat history every time, without truncating history to fit the token limit even though this makes it ultimately useless as a chat session manager. Since I now have to manually manage the chat session as well! So, we just try removing messages until it works
      try:
        chat.reply(p)
        messages.append({"role": "user", "content": display_p})
        messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})
        st.session_state["activity_log_payload"] = {"user_email": st.session_state["email"], "prompter_or_chatbot": 'chatbot'+streamlit_key_suffix, "prompt_sent": p, "response_given": chat.last, "model_name": short_model_name, "model_url": chat.model, "model_parameters": str(chat.parameters), "system_prompt": chat.system_message, "base_url": get_base_url(), "used_similarity_search_backup": "no"}
        if not streamlit_key_suffix:
          st.session_state["outstanding_activity_log_payload"] = st.session_state["activity_log_payload"]
        break
      except FoundationModelAPIException as e:
        if e.message.startswith('{"error_code":"BAD_REQUEST","message":"Bad request: prompt token count'): # Find out if it's exactly the right error we know how to handle.
          if len(chat.chat_history) <= 2: # This means there is only the system prompt and the current user prompt left, which means the user prompt is simply too long.
            popup("Prompt too long.", "User prompt to chatbot too long, sorry. Try using a shorter one.")
            chat.chat_history = old_chat #remove failed prompt, and also restore all of the messages we probably popped off while trying to cull history.
            break
          else:
            consul_show(f"Truncating chat history from {len(chat.chat_history)} messages...")
            chat.chat_history = [chat.chat_history[0]]+chat.chat_history[3:-1]#remove one message-response pair from the start of history, preserving the system message at the beginning. Also remove the failed prompting we've just appended at the end with our other actions. This clause will repeat until the total prompt (the entire history) is small enough that the prompting goes through.
        elif e.message.startswith('{"error_code":"REQUEST_LIMIT_EXCEEDED","message":"REQUEST_LIMIT_EXCEEDED: Exceeded workspace rate limit for'): # Also we want to handle this one, actually.
          print("!!! chat rate limit hit; retrying...", e)
          chat.chat_history = old_chat #remove failed prompt. But, there is no break statement after this because we just want to try again. The rate-limit is 2 per second so there's a good chance this works.
        else: # I guess it's some other error, so crash 🤷
          raise e

def reset_chat(streamlit_key_suffix: str = "") -> None:
  if st.session_state.get("chat"):
    st.session_state["chat"][streamlit_key_suffix] = None
  if st.session_state.get("messages"):
    st.session_state["messages"][streamlit_key_suffix] = None
  if not streamlit_key_suffix: #The user has decided to reset the chat-page chat, so we won't force them to good/bad the last message, which they now can no longer see.
    st.session_state["outstanding_activity_log_payload"] = None # Don't force the user to up/down the cleared message if they reset the chat.

def display_chat(streamlit_key_suffix: str = "", account: str|None = None, short_model_name: Short_Model_Name = short_model_name_default) -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).

  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)"""
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)
  if pii and pii[0] is True: # We're in a pii situation and the user has chosen to press on. So we have to send that chat message before we display the chat history.
    grow_chat(**pii[2])
    ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
  if ssget("messages", streamlit_key_suffix):
    for message in st.session_state.messages[streamlit_key_suffix]:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\["))
  if st.session_state.get("outstanding_activity_log_payload") and not streamlit_key_suffix:
    emptyable = st.empty()
    with emptyable.container():
      _c1, c2, c3 = st.columns([.05, .06, .89], gap='small', vertical_alignment="center")
      with c2:
        st_feedback: int|None = st.feedback("thumbs", key=ssget("feedback", streamlit_key_suffix))
      c3.write("***Did Cicero understand your request? Let us know to continue chatting.***")
    if st_feedback is not None:
      emptyable.empty()
      user_feedback = "bad" if st_feedback == 0 else "good"
      ssmut(lambda x: x+1 if x else 1, "feedback", streamlit_key_suffix)
      st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix, None, account, short_model_name_default) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text...
      st.session_state["outstanding_activity_log_payload_fulfilled"] = st.session_state["outstanding_activity_log_payload"] | {"user_feedback": user_feedback}
      st.session_state["outstanding_activity_log_payload"] = None
  else:
    if pii and pii[0] is False: # We're in a pii situation and the user has chosen to press on. So we have to show them the message they just had.
      st.info("Message you were editing (may contain PII):")
      st.code(pii[1])
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
    st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix, None, account, short_model_name_default) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.)

def main(streamlit_key_suffix: str = "") -> None: # It's convenient to import cicero_chat in other files, to use its function in them, so we do a main() here so we don't run this code on startup.
  st.write('''**Chat freeform with Cicero directly ChatGPT-style!**  \nHere are some ideas: rewrite copy, make copy longer, convert a text into an email, or write copy based off a starter phrase/quote.''')
  account = st.text_input("Account") if streamlit_key_suffix=="_corporate" else None
  if is_dev():
    _uploaded_file = st.file_uploader(label="(CURRENTLY DOES NOTHING) Upload a file", type=['csv', 'xlsx', 'xls', 'txt', 'html'], accept_multiple_files=False, help='You can upload a file here for Cicero to analyze. Cicero currently supports these file types: csv, xlsx, xls, txt, and html.') #TODO: test out these files to make sure they actually work.
  model_name = typesafe_selectbox("Model", short_model_names, key="model_name") if is_dev() else short_model_name_default
  if st.button("Reset"):
    reset_chat(streamlit_key_suffix)
  display_chat(streamlit_key_suffix, account=account, short_model_name=model_name)

if __name__ == "__main__":
  main()
