#!/usr/bin/env -S streamlit run

"""Cicero (the actual, historical man (it's really him))."""

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile
from datetime import datetime, timedelta
import time
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import catstr, is_dev, ssget, ssset, ssmut, sspop, get_base_url, popup, load_account_names, sql_call, sql_call_cacheless
from cicero_types import Short_Model_Name, short_model_names, short_model_name_default, short_model_name_to_long_model_name
import bs4, requests, re # for some reason bs4 is how you import beautifulsoup smh smh
from pathlib import Path
from io import StringIO
import pandas as pd
from docx import Document

def pii_detector(input: str) -> list[str]:
  phone = re.findall(
    r"""\d?[- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}"""
  , input)
  email = re.findall(
    r"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    input,
    re.IGNORECASE,
  )
  credit_card = re.findall(r"((?:(?:\\d{4}[- ]?){3}\\d{4}|\\d{15,16}))(?![\\d])", input)
  street_address = re.findall(
    r"\d{1,4} (?:\w+ ){0,4}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\b",
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
      return "(document unavailable, url not supported)" #early out. We remove the url itself so that Cicero can't make up ("hallucinate") things based on its name.
  # from https://stackoverflow.com/questions/69593352/how-to-get-all-copyable-text-from-a-web-page-python/69594284#69594284
  try:
    response = requests.get(url,headers={'User-Agent': 'Mozilla/5.0'})
  except Exception as e:
    return f"(document unavailable, error {e})"
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
    ssset("last_url_content", new_str.replace("$", r"\$")) #diagnostic we want to print elsewhere on the page (later)
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

def grow_chat(streamlit_key_suffix: str = "", alternate_content: str|UploadedFile|None = None, account: str|None = None, short_model_name: Short_Model_Name = short_model_name_default) -> None:
  """Note that this function will do something special to the prompt if alternate_content is supplied.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).
  Random fyi: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""
  keyword_arguments = locals()
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)
  if streamlit_key_suffix=="_prompter":
    sys_prompt = "You are a helpful, expert copywriter who specializes in writing fundraising text messages and emails for conservative candidates and causes. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Do not mention that you are a helpful, expert copywriter."
  elif streamlit_key_suffix=="_corporate":
    sys_prompt = "You are a helpful, expert marketer. Do not mention that you are a helpful, expert marketer."+" The system interfacing you can expand links into document contents, after the user enters them but before you see them; but do not mention this unless it is relevant."
  else:
    sys_prompt = "You are an expert copywriter who specializes in writing fundraising and engagement texts and emails for conservative political candidates in the United States of America. Make sure all messages are in English. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Focus on these five fundraising elements when writing content: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not make up facts or statistics. Do not mention that you are a helpful, expert copywriter. Do not use emojis or hashtags in your messages. Make sure each written message is unique. Write the exact number of messages asked for."
  if not ssget("chat", streamlit_key_suffix):
    ssset( "chat", streamlit_key_suffix, ChatSession(model=short_model_name_to_long_model_name(short_model_name), system_message=sys_prompt, max_tokens=4096) ) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then this line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  chat = st.session_state.chat[streamlit_key_suffix] # Note that, as an object reference, updating and accessing chat will continue to update and access the same object.
  if not ssget("messages", streamlit_key_suffix):
    st.session_state.messages[streamlit_key_suffix] = [] # We keep our own list of messages, I think because I found it hard to format the chat_history output when I tried once.
  messages = st.session_state.messages[streamlit_key_suffix] # Note that, as an object reference, updating and accessing messages will continue to update and access the same object.
  if alternate_content:
    if isinstance(alternate_content, UploadedFile): # I think this is broken because of our dependencies. Possibly up to and including the Python language itself. It can be worked around. Or, maybe databricks will eventually implement their own file-upload thing (I guess that's on their roadmap.
      file_ext = Path(str(alternate_content.name)).suffix
      match file_ext: #todo: delete this? or at least the st.write statements in it?
        case '.txt' | '.html' :
          stringio = StringIO(alternate_content.getvalue().decode("utf-8")) # convert file-like BytesIO object to a string based IO
          string_data = stringio.read() # read file as string
          st.write(string_data)
          p = string_data
        case '.docx':
          docx_text = '\n'.join([para.text for para in Document(alternate_content).paragraphs])
          st.write(docx_text)
          p = docx_text
        case '.csv':
          x = pd.read_csv(alternate_content, nrows=10)
          st.dataframe( x )
          p = str(x)
        case '.xls' | '.xlsx':
          st.dataframe( x := pd.read_excel(alternate_content, nrows=10) )
          p = str(x)
        case _:
          x = "Cicero does not currently support this file type!"
          st.write(x)
          p = x
      display_p = f"「 {p} 」"
    else:
      p = "Here is a conservative fundraising text: [" + alternate_content + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email. Only provide analysis once, unless the user asks for analysis again."
      display_p = "« " + alternate_content + " »"
  elif pii and pii[0]: #there was pii, and we are continuing
    p = pii[1]
    display_p = p
  else:
    p = st.session_state["user_input_for_chatbot_this_frame"+streamlit_key_suffix]
    display_p = p
  
  #detect concerning elements:
  winred_concern = "winred.com" in p.lower()
  fec_concern = "fec.gov" in p.lower()
  
  #implement url content expansion, at this point only for the corp chat and devs
  hit_readlink_time_limit = False
  if streamlit_key_suffix=="_corporate" or is_dev():
    if detect_url_content(p):
      if "last_link_time" in st.session_state:
        time_difference = datetime.now() - st.session_state["last_link_time"]
        if time_difference < timedelta(seconds=27): # It's 27 because we don't want to alert the user if they just have to wait another second or two. The query already takes that long, probably.
          hit_readlink_time_limit = True
          remaining_seconds = round( 30 - time_difference.total_seconds() )
          popup("Throttled!", f"Link reading is currently limited to once every 30 seconds per user.  Cicero has delayed your request by {remaining_seconds} seconds.  Contact the Cicero Team for more info.", show_x_instruction=False) # Festina lente! #Unfortunately I think an unreported bug in streamlit means this dialog only ever shows once per session. But that's ok in this case.
          time.sleep(remaining_seconds)
      st.session_state["last_link_time"] = datetime.now()
    p = expand_url_content(p)
    ssset("urls_we_have_expanded_right_now", 0) # Have to reset this value in this remote place for flow-control reasons :/

  # detect pii
  continue_prompt = True
  if possible_pii := pii_detector(p):
    pii_state = ssget("pii_interrupt_state", streamlit_key_suffix)
    if pii_state is None: #TODO: this can be refactored to use the new ss-family of functions and be way clearer about what it does.
      st.session_state.pii_interrupt_state = {}
    if pii_state and pii_state[0]: #if the field is true, we continue
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since we're going to send this one and get a new circumstance later.
    else:
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since the dialog is about to set it, and this prevents funny business from x-ing the dialogue.
      pii_dialog(p, possible_pii, streamlit_key_suffix, keyword_arguments)
      continue_prompt = False

  if continue_prompt:
    old_chat = chat.chat_history.copy()
    while True:
      try:
        chat.reply(p)
        messages.append({"role": "user", "content": display_p})
        messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})
        st.session_state["activity_log_payload"] = {"user_email": st.session_state["email"], "prompter_or_chatbot": 'chatbot'+streamlit_key_suffix, "prompt_sent": p, "response_given": chat.last, "model_name": short_model_name, "model_url": chat.model, "model_parameters": str(chat.parameters), "system_prompt": chat.system_message, "base_url": get_base_url(), "used_similarity_search_backup": "no"} | ({"user_feedback": "not asked", "user_feedback_satisfied": "not asked"} if streamlit_key_suffix == "_prompter" else {"user_feedback": "not received", "user_feedback_satisfied": "not received"} if streamlit_key_suffix == "_corporate" else {"user_feedback": "not received", "user_feedback_satisfied": "not asked"}) | {"hit_readlink_time_limit": hit_readlink_time_limit} | {"pii_concern": bool(pii and pii[0]), "winred_concern": winred_concern, "fec_concern": fec_concern}
        if not streamlit_key_suffix == "_prompter":
          ssset("outstanding_activity_log_payload", streamlit_key_suffix, st.session_state["activity_log_payload"])
        break
      except FoundationModelAPIException as e:
        if e.message.startswith('{"error_code":"REQUEST_LIMIT_EXCEEDED","message":"REQUEST_LIMIT_EXCEEDED: Exceeded workspace rate limit for'): # Could: test to see if this Exception ever happens still, and remove this code if not.
          print("!!! chat rate limit hit; retrying...", e)
          chat.chat_history = old_chat #remove failed prompt. But, there is no break statement after this because we just want to try again. The rate-limit is 2 per second so there's a good chance this works.
        else: # I guess it's some other error, so crash 🤷
          raise e

def reset_chat(streamlit_key_suffix: str = "") -> None:
  ssset("chat", streamlit_key_suffix, None)
  ssset("messages", "streamlit_key_suffix", None)
  ssset("outstanding_activity_log_payload", streamlit_key_suffix, None) # Don't force the user to up/down the cleared message if they reset the chat.
  ssset("outstanding_activity_log_payload2", streamlit_key_suffix, None)

def cicero_feedback_widget(streamlit_key_suffix: str, feedback_suffix: str, feedback_message: str) -> None:
  """ '' is the feedback suffix we started with, so probably the one you want to use.
  This function returns nothing, and (tees up a state that) writes to the activity log. It also manipulates the session state to remove the session state that leads to its running."""
  st_feedback: int|None = None # This is "declared" up here to appease possibly-unbound analysis.
  emptyable = st.empty()
  ss_feedback_key = "feedback" + streamlit_key_suffix + feedback_suffix
  with emptyable.container():
    _c1, c2, c3 = st.columns([.05, .06, .89], gap='small', vertical_alignment="center")
    with c2:
      st_feedback = st.feedback( "thumbs", key=catstr(ssget("feedback", ss_feedback_key), ss_feedback_key) )
    c3.write(feedback_message)
  if st_feedback is not None:
    emptyable.empty()
    user_feedback = "bad" if st_feedback == 0 else "good"
    ssmut(lambda x: x+1 if x else 1, "feedback", ss_feedback_key) # We have to do this, or the feedback widget will get stuck on its old value.

    o = ssget("outstanding_activity_log_payload", streamlit_key_suffix)
    o2 = ssget("outstanding_activity_log_payload2", streamlit_key_suffix)
    if o and o2:
      print("!! Cicero internal error: you are in an invalid state somehow! You have both outstandings {o=},{o2=}")
    elif o:
      st.session_state["activity_log_update"] = o | {"user_feedback"+feedback_suffix: user_feedback}
      if streamlit_key_suffix == "_corporate":
        ssset("outstanding_activity_log_payload2", streamlit_key_suffix, o)
      ssset("outstanding_activity_log_payload", streamlit_key_suffix, None)
    elif o2:
      st.session_state["activity_log_update2"] = o2 | {"user_feedback"+feedback_suffix: user_feedback}
      ssset("outstanding_activity_log_payload2", streamlit_key_suffix, None)
    else:
      print("!! Cicero internal warning: you are in an invalid state somehow? You are using the feedback widget but have neither outstandings {o=},{o2=}")

def display_chat(streamlit_key_suffix: str = "", account: str|None = None, short_model_name: Short_Model_Name = short_model_name_default) -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).

  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)"""
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)
  if pii and pii[0] is True: # We're in a pii situation and the user has chosen to press on. So we have to send that chat message before we display the chat history.
    grow_chat(**pii[2])
    ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
  if ms := ssget("messages", streamlit_key_suffix):
    for message in ms:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"].replace("$", r"\$").replace("[", r"\["))
  if (s := sspop("last_url_content")) and is_dev():
    st.expander("Developer Mode Message (will disappear on next page load): url content").caption(s)
  if ssget("outstanding_activity_log_payload", streamlit_key_suffix):
    cicero_feedback_widget(streamlit_key_suffix, "", "***Did Cicero understand your request? Let us know to continue chatting.***")
  if ssget("outstanding_activity_log_payload2", streamlit_key_suffix):
    cicero_feedback_widget(streamlit_key_suffix, "_satisfied", "***Are you satisfied with this output? Let us know to continue chatting.***")
  if not ( ssget("outstanding_activity_log_payload", streamlit_key_suffix) or ssget("outstanding_activity_log_payload2", streamlit_key_suffix) ):
    if pii and pii[0] is False: # We're in a pii situation and the user has chosen to press on. So we have to show them the message they just had.
      st.info("Message you were editing (may contain PII):")
      st.code(pii[1])
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
    st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix, None, account, short_model_name_default) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text...

def main(streamlit_key_suffix: str = "") -> None: # It's convenient to import cicero_chat in other files, to use its function in them, so we do a main() here so we don't run this code on startup.
  st.write('''**Chat freeform with Cicero directly ChatGPT-style!**  \nHere are some ideas: rewrite copy, make copy longer, convert a text into an email, or write copy based off a starter phrase/quote.''')
  account = st.text_input("Account") if streamlit_key_suffix=="_corporate" else None
  if is_dev():
    account = st.selectbox("Account (required)", load_account_names(), key="account") if streamlit_key_suffix!="_corporate" else None
    if account != None:
      texts_from_account = sql_call_cacheless(
        f"""WITH t AS ( -- first (conceptually first) we need to actually get the data, because we can't just tablesample on a query directly I guess idk why not
          SELECT DISTINCT clean_text FROM cicero.text_data.gold_text_outputs WHERE client_name = '{account}'
        ) SELECT * FROM t TABLESAMPLE (100 PERCENT) LIMIT 5 -- tablesample randomizes, then the limit 5 is taken; see https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-qry-select-sampling.html for more info (like why we can't just use (5 ROWS) (not random) (at least as of 2024-09-14)
        """
      )
      texts_from_account_list = []
      for row in texts_from_account:
        texts_from_account_list.append(row[0])
      texts_from_account_str = ' | '.join(texts_from_account_list)
      st.write(texts_from_account_str)
    # TODO: get the clean texts into the prompt, and edit the prompt such that its like, hey here are some references texts to look at
    uploaded_file = st.file_uploader(label="Upload a file", type=['csv', 'docx', 'html', 'txt', 'xls', 'xlsx'], accept_multiple_files=False)
    if uploaded_file is not None and not ssget("chat_file_uploader"):
      ssmut(lambda x: x+1 if x else 1, "chat_file_uploader")
      file_ext = Path(str(uploaded_file.name)).suffix
      st.write(f"You uploaded a {file_ext} file!")
      grow_chat(streamlit_key_suffix, uploaded_file, account, short_model_name_default)
  model_name = st.selectbox("Model", short_model_names, key="model_name") if is_dev() else short_model_name_default
  if st.button("Reset"):
    reset_chat(streamlit_key_suffix)
  display_chat(streamlit_key_suffix, account=account, short_model_name=model_name)

if __name__ == "__main__":
  main()
