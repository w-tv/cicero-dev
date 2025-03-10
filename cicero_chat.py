#!/usr/bin/env -S streamlit run

"""Cicero (the actual, historical man (it's really him))."""

import streamlit as st
from datetime import datetime, timedelta
import time
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import catstr, admin_box, get_list_value_of_column_in_table, is_admin, sql_call, ssget, ssset, ssmut, sspop, get_base_url, popup, load_account_names, sql_call_cacheless
from cicero_types import Short_Model_Name, short_model_names, short_model_name_default, short_model_name_to_long_model_name, voices_corporate, voices_noncorporate, Voice, voice_default, Chat_Suffix, chat_suffix_default
from cicero_video_brief_system_prompt import nice_text_to_html, video_brief_system_prompt
import bs4 # for some reason bs4 is how you import beautifulsoup
import requests
import re
from pathlib import Path
from io import StringIO
import pandas as pd
from docx import Document
from typing import assert_never, Literal

def pii_detector(input: str) -> dict[str, list[object]]:
  """Check for phone numbers, email addresses, credit card numbers, and street addresses in the text, and return a dict of what of those we've found.
  It's important, for the assumptions of the caller of this function, that if no pii is found, then this function returns an empty (and thus falsy) dict.
  re.findall seems to be declared (in typeshed I guess) with a return type of `list[Any]`, which I consider ultimately bad practice although there are probably overwhelming practical reasons in this case to declare it so. So, anyway, that's why we treat it (and, therefore, this function) as though it returns `list[object]`. Possibly you could consider this a TYPESHED-BUG-WORKAROUND, although it would probably take multiple typing PEPs to fix the assumptions of the type system that produce this corner case. Possibly even dependent typing (but probably not). We could also have done some str calls to return list[str], but it didn't end up mattering.
  Actually checking for all phone number types ( such as those covered by https://en.wikipedia.org/wiki/List_of_country_calling_codes ) would be extremely arduous and possibly lead to unwanted to false-positives with other numbers. So we basically just check for american phone numbers and maybe some other ones that happen to have a similar form. (We also don't check for phone numbers that exclude area code.) Similar story with credit card numbers and the various forms in https://en.wikipedia.org/wiki/Payment_card_number#Structure . We also purposefully do not exclude the non-issuable Social Security numbers ( https://en.wikipedia.org/wiki/Social_Security_number#Valid_SSNs ), so that example SSNs can be detected for testing purposes."""
  phone = re.findall(r"(?<!\d)\d?[- ]?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}(?!\d)", input)
  email = re.findall(
    r"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)",
    input,
    re.IGNORECASE,
  )
  credit_card = re.findall(r"(?<!\d)(?:(?:\d{4}[- ]?){3}\d{4}|\d{15,16})(?!\d)", input)
  street_address = re.findall(
    r"\d{1,4} (?:\w+ ){0,4}(?:street|st|avenue|ave|road|rd|highway|hwy|square|sq|trail|trl|drive|dr|court|ct|park|parkway|pkwy|circle|cir|boulevard|blvd)\b",
    input,
    re.IGNORECASE,
  )
  ssn = re.findall(r"(?<!\d)\d{3}[- ]?\d{2}?[- ]?\d{4}(?!\d)", input)
  return ( {}
    | {'phone': phone} if phone else {}
    | {'email': email} if email else {}
    | {'credit card': credit_card} if credit_card else {}
    | {'street address': street_address} if street_address else {}
    | {'social security number': ssn} if ssn else {}
  )

@st.dialog(title='PII detected!', width="large")
def pii_dialog(input: str, pii_list: object, streamlit_key_suffix: str, keyword_arguments: dict[str, str|None]) -> None:
  st.write("Cicero noticed that there might be PII in your message!\n\nMessage:")
  st.code(input)
  st.write("Potential PII:")
  st.write(pii_list)
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
    text = text[:8000] # Limit text to 8000 (arbitrary limit) because more text = longer processing time (perhaps avoidably).
    return text
  else:
    return "(document appears to Cicero to be empty; if you don't expect the document to be empty, please copy-and-paste in directly. TELL THE USER TO COPY AND PASTE THE CONTENT INTO THE CHATBOT DIRECTLY, USING THOSE EXACT WORDS, AND ALSO EXPLAINING THAT IT LOOKS EMPTY TO YOU LIKELY DUE TO TECHNICAL LIMITATIONS)" # there is no content on the page, I guess, so the correct thing to return is this explicit empty indicator

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

def grow_chat(streamlit_key_suffix: Chat_Suffix, alternate_content: str|Literal[True]|None = None, account: str = "No account", short_model_name: Short_Model_Name = short_model_name_default, voice: Voice = voice_default, expand_links: bool = True) -> None:
  """Note that this function will do something special to the prompt if alternate_content is supplied.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).
  Random fyi: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""
  keyword_arguments = locals()
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)

  # determine what the prompt content will be
  if alternate_content:
    if alternate_content is True:
      content = ssget("chat_file_uploader")
      file_ext = Path(str(content.name)).suffix
      match file_ext: #todo: delete this? or at least the st.write statements in it?
        case '.txt' | '.html' | '.htm' :
          stringio = StringIO(content.getvalue().decode("utf-8")) # convert file-like BytesIO object to a string based IO
          string_data = stringio.read() # read file as string
          p = string_data
        case '.docx':
          docx_text = '\n'.join([para.text for para in Document(content).paragraphs])
          p = docx_text
        case '.csv':
          x = pd.read_csv(content, nrows=10)
          st.dataframe( x )
          p = str(x)
        case '.xls' | '.xlsx':
          st.dataframe( x := pd.read_excel(content, nrows=10) )
          p = str(x)
        case _:
          x = "Error: Cicero does not currently support this file type!"
          p = x
      display_p = f"「 {p} 」"
    else:
      p = "Here is a conservative fundraising text: [" + alternate_content + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email. Only provide analysis once, unless the user asks for analysis again."
      display_p = "« " + alternate_content + " »"
  elif pii and pii[0]: #there was pii, and we are continuing
    p = pii[1]
    display_p = p
  else:
    p = ssget("user_input_for_chatbot_this_frame"+streamlit_key_suffix)
    display_p = p

  #detect concerning elements:
  winred_concern = "winred.com" in p.lower()
  fec_concern = "fec.gov" in p.lower()

  # URL content expansion
  hit_readlink_time_limit = False
  if expand_links and detect_url_content(p):
    if llt := ssget("last_link_time"):
      time_difference = datetime.now() - llt
      if time_difference < timedelta(seconds=27): # It's 27 because we don't want to alert the user if they just have to wait another second or two. The query already takes that long, probably.
        hit_readlink_time_limit = True
        remaining_seconds = round( 30 - time_difference.total_seconds() )
        popup("Throttled!", f"Link reading is currently limited to once every 30 seconds per user.  Cicero has delayed your request by {remaining_seconds} seconds.  Contact the Cicero Team for more info.", show_x_instruction=False) # Festina lente! #Unfortunately I think an unreported (TODO) bug in streamlit means this dialog only ever shows once per session. But that's ok in this case.
        time.sleep(remaining_seconds)
    ssset("last_link_time", datetime.now())
    p = expand_url_content(p)
  ssset("urls_we_have_expanded_right_now", 0) # Have to reset this value in this remote place for flow-control reasons :/

  # detect pii
  continue_prompt = True
  if possible_pii := pii_detector(p):
    pii_state = ssget("pii_interrupt_state", streamlit_key_suffix)
    if pii_state is None: #TODO: this can be refactored to be clearer about what it does.
      ssset("pii_interrupt_state", {})
    if pii_state and pii_state[0]: #if the field is true, we continue
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since we're going to send this one and get a new circumstance later.
    else:
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, "", {}] ) #reset the field, since the dialog is about to set it, and this prevents funny business from x-ing the dialogue.
      pii_dialog(p, possible_pii, streamlit_key_suffix, keyword_arguments)
      continue_prompt = False

  #set the system prompt based on various variables
  if voice != voice_default:
    sys_prompt = sql_call("SELECT voice_description from cicero.default.voice_map WHERE voice_id = :voice", {"voice": voice})[0][0]
  else:
    match streamlit_key_suffix:
      case "_prompter":
        sys_prompt = "You are a helpful, expert copywriter who specializes in writing fundraising text messages and emails for conservative candidates and causes. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Do not mention that you are a helpful, expert copywriter."
      case "_corporate":
        sys_prompt = "You are a helpful, expert marketer. Do not mention that you are a helpful, expert marketer."+" The system interfacing you can expand links into document contents, after the user enters them but before you see them; but do not mention this unless it is relevant."
      case "": #regular chatbot
        sys_prompt = "You are an expert copywriter who specializes in writing fundraising and engagement texts and emails for conservative political candidates in the United States of America. Make sure all messages are in English. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. The content you will be asked to write is more punchy, unhinged, and engaging than normal marketing material. Focus on these five fundraising elements when writing content: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not make up facts or statistics. Do not mention that you are a helpful, expert copywriter. Do not use emojis or hashtags in your messages. Make sure each written message is unique. Write the exact number of messages asked for."
      case "_video_brief":
        sys_prompt = video_brief_system_prompt
      case _ as unreachable:
        assert_never(unreachable)
  if streamlit_key_suffix not in ("_corporate", "_video_brief") :
    # Add context for current events as an addendum on all sys_prompts except corporate:
    sys_prompt += "\nHere is some context on the current political landscape: Donald Trump defeated Incumbent Vice President Kamala Harris in the 2024 election and was sworn in as the 47th president on January 20, 2025, marking a historic comeback as the first president since Grover Cleveland to serve nonconsecutive terms. His running mate, JD Vance, was sworn in as Vice President at that time. Republicans secured a 52-seat majority in the Senate and retained control of the House, achieving a governing trifecta for the first time since 2018. It is now February 2025. Since taking office, Trump has been actively pursuing his policy agenda, implementing a series of executive orders and policies focused on immigration and border security, and pursuing a conservative agenda on issues such as trade, foreign policy, and government reform, with the support of Elon Musk's DOGE, which aims to root out waste and inefficiency in the federal government. His administration has also been embroiled in controversy over its handling of USAID, DEI policies, and cabinet nominations, and has faced numerous legal challenges and investigations, setting the stage for a contentious and potentially transformative presidency.\n"
  if not ssget("chat", streamlit_key_suffix):
    # Get some sample texts from the account, perhaps similar to the current prompt. (We only do this for the first prompt. & it's after the chat check so we don't wait for this query every time.)
    if account != "No account":
      texts_from_account = sql_call_cacheless( # TODO: can we collapse topic_reporting.default and cicero.text_data into the same thing? If so, which one should we use here?
        """ -- I got this from the Databricks AI, it seems to mostly do the job.
          WITH QueryTopics AS (
            SELECT rt.Tag_Name
            FROM cicero.ref_tables.ref_tags rt
            WHERE :prompt RLIKE rt.Regex_Pattern
            AND rt.Enabled = TRUE -- Unclear if we should honor Enabled in this query…
          ),
          MatchingTexts(text, count) AS (
            SELECT gto.Clean_Text, COUNT(*)
            FROM cicero.text_data.gold_text_outputs gto
            JOIN cicero.ref_tables.ref_tags rt ON gto.Clean_Text RLIKE rt.Regex_Pattern
            JOIN QueryTopics qt ON rt.Tag_Name = qt.Tag_Name
            WHERE client_name = :account
            AND rt.Enabled = TRUE
            GROUP BY gto.Clean_Text
          )
          SELECT DISTINCT text, count FROM MatchingTexts ORDER BY count DESC LIMIT 5;
        """,
        {"account": account, "prompt": p}
      )
      sys_prompt += f"\n(Here are some example texts from the client; you can use them as inspiration but do not copy them directly nor mention their existence: {' | '.join(row[0] for row in texts_from_account)} )"
    ssset( "chat", streamlit_key_suffix, ChatSession(model=short_model_name_to_long_model_name(short_model_name), system_message=sys_prompt, max_tokens=4096) ) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then this line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  chat = ssget("chat", streamlit_key_suffix) # Note that, as an object reference, updating and accessing chat will continue to update and access the same object.
  if not ssget("messages", streamlit_key_suffix):
    ssset("messages", streamlit_key_suffix, []) # We keep our own list of messages, I think because I found it hard to format the chat_history output when I tried once.
  messages = ssget("messages", streamlit_key_suffix) # Note that, as an object reference, updating and accessing messages will continue to update and access the same object.

  if continue_prompt:
    old_chat = chat.chat_history.copy()
    while True:
      try:
        chat.reply(p)
        messages.append({"role": "user", "content": display_p})
        messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})
        ssset(
          "activity_log_payload",
          {"user_email": ssget("email"), "prompter_or_chatbot": 'chatbot'+streamlit_key_suffix, "prompt_sent": p, "response_given": chat.last, "model_name": short_model_name, "model_url": chat.model, "model_parameters": str(chat.parameters), "system_prompt": chat.system_message, "base_url": get_base_url(), "used_similarity_search_backup": "no"} | ({"user_feedback": "not asked", "user_feedback_satisfied": "not asked"} if streamlit_key_suffix == "_prompter" else {"user_feedback": "not received", "user_feedback_satisfied": "not received"} if streamlit_key_suffix == "_corporate" else {"user_feedback": "not asked", "user_feedback_satisfied": "not received"}) | {"hit_readlink_time_limit": hit_readlink_time_limit} | {"pii_concern": bool(pii and pii[0]), "winred_concern": winred_concern, "fec_concern": fec_concern, "voice": voice, "account": account}
        )
        if streamlit_key_suffix == "_corporate":
          ssset("outstanding_activity_log_payload", streamlit_key_suffix, ssget("activity_log_payload"))
        elif streamlit_key_suffix == "":
          ssset("outstanding_activity_log_payload2", streamlit_key_suffix, ssget("activity_log_payload"))
        elif streamlit_key_suffix == "_prompter":
          pass # note that "_prompter" is deliberately absent, because we don't require anything from it. (I guess, also it can't even appear here, because it's in the other tab.)
        elif streamlit_key_suffix == "_video_brief":
          pass #TODO: should we ask for feedback on the video briefs? I lean no.
        else:
          assert_never(streamlit_key_suffix)

        # Double-prompting we only do on occasion
        # The double-prompting makes the error handling less efficient than it theoretically could be, but whatver.
        if voice == "Arvind":
          admin_box("Developer Mode Message: double-prompting: the original machine response", chat.last)
          chat.reply("Make the first sentence more concise, shocking, and unhinged") # we don't have to display this part.
          messages.pop() # remove the previous last message, now that we have the new one
          messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})

        break #leave the retry loop, having been successful with everything.
      except FoundationModelAPIException as e:
        if "API request timed out" in e.message or e.message.startswith('{"error_code":"REQUEST_LIMIT_EXCEEDED","message":"REQUEST_LIMIT_EXCEEDED: Exceeded workspace rate limit for'): # Could: test to see if this Exception ever happens still, and remove this code if not.
          print("!!! chat rate limit or api timeout hit; retrying...", e)
          chat.chat_history = old_chat.copy() #remove failed prompt. But, there is no break statement after this because we just want to try again. The rate-limit is 2 per second so there's a good chance this works.
        else: # I guess it's some other error, so crash 🤷
          raise e

def reset_chat(streamlit_key_suffix: Chat_Suffix) -> None:
  sspop("chat", streamlit_key_suffix)
  sspop("messages", streamlit_key_suffix)
  sspop("outstanding_activity_log_payload", streamlit_key_suffix) # Don't force the user to up/down the cleared message if they reset the chat.
  sspop("outstanding_activity_log_payload2", streamlit_key_suffix)

def cicero_feedback_widget(streamlit_key_suffix: Chat_Suffix, feedback_suffix: str, feedback_message: str) -> None:
  """ '' is the feedback suffix we started with, so probably the one you want to use.
  This function returns nothing, and (tees up a state that) writes to the activity log. It also manipulates the session state to remove the session state that leads to its running."""
  # The code that controls the feedback widget and logging is all over the place (in this file, and also in cicero.py). Would be a fine thing to refactor. But it's easy enough to leave it as-is for now. We have higher priorities, and this works the way it is.
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
      ssset("activity_log_update", o | {"user_feedback"+feedback_suffix: user_feedback})
      if streamlit_key_suffix == "_corporate":
        ssset("outstanding_activity_log_payload2", streamlit_key_suffix, o)
      sspop("outstanding_activity_log_payload", streamlit_key_suffix)
    elif o2:
      ssset("activity_log_update2", o2 | {"user_feedback"+feedback_suffix: user_feedback})
      sspop("outstanding_activity_log_payload2", streamlit_key_suffix)
    else:
      print("!! Cicero internal warning: you are in an invalid state somehow? You are using the feedback widget but have neither outstandings {o=},{o2=}")

def display_chat(streamlit_key_suffix: Chat_Suffix, account: str = "No account", short_model_name: Short_Model_Name = short_model_name_default, voice: Voice = voice_default, expand_links: bool = True) -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).

  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)

  the computer knows something we don't
  we must let it make management decisions
  —Alex Chang"""
  pii = ssget("pii_interrupt_state", streamlit_key_suffix)
  if pii and pii[0] is True: # We're in a pii situation and the user has chosen to press on. So we have to send that chat message before we display the chat history.
    grow_chat(**pii[2])
    ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
  needback: bool = is_admin() and bool(ssget("outstanding_activity_log_payload", streamlit_key_suffix) or ssget("outstanding_activity_log_payload2", streamlit_key_suffix)) #TODO(urgent): this is a prototype version that requires you to refresh the page. For this feature to actually work, I'll have to include logic in the activity log discharger that rewrites the contents of the chat to the right thing (which will have to be in a container).
  if ms := ssget("messages", streamlit_key_suffix):
    for message in ms:
      with st.chat_message(message["role"], avatar=message.get("avatar")):
        if streamlit_key_suffix == "_video_brief" and message["role"] == "assistant":
          html_content = nice_text_to_html(message["content"])
          st.download_button("Download this output", data=html_content, mime="text/html")
          #st.html("<iframe>"+html_content+"<iframe>") #TODO: figure out how to get this to play nice with the rest of the page...
        else:
          message_core = message["content"].replace("$", r"\$").replace("[", r"\[")
          if needback:
            st.markdown('<span style="user-select: none;">'+message_core+'</div>', unsafe_allow_html=True)
          else:
            st.markdown(message_core)
  if needback:
    st.success("Please give feedback to enable copying the text. (And to make Cicero better!)")
  if (s := sspop("last_url_content")):
    admin_box("Admin Mode Message (will disappear on next page load): url content", s)
  if ssget("outstanding_activity_log_payload", streamlit_key_suffix):
    cicero_feedback_widget(streamlit_key_suffix, "", "***Did Cicero understand your request? Let us know to continue chatting.***")
  if ssget("outstanding_activity_log_payload2", streamlit_key_suffix):
    cicero_feedback_widget(streamlit_key_suffix, "_satisfied", "***Like this output?  Let us know to continue chatting.***")
  if not ( ssget("outstanding_activity_log_payload", streamlit_key_suffix) or ssget("outstanding_activity_log_payload2", streamlit_key_suffix) ):
    if pii and pii[0] is False: # We're in a pii situation and the user has chosen to press on. So we have to show them the message they just had.
      st.info("Message you were editing (may contain PII):")
      st.code(pii[1])
      ssset( "pii_interrupt_state", streamlit_key_suffix, [None, ""] )
    st.container().chat_input(on_submit=grow_chat, key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, args=(streamlit_key_suffix, None, account, short_model_name, voice, expand_links) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text...

def main(streamlit_key_suffix: Chat_Suffix = chat_suffix_default) -> None: # It's convenient to import cicero_chat in other files, to use its function in them, so we do a main() here so we don't run this code on startup.
  st.write("**Chat freeform with Cicero directly ChatGPT-style!**")
  match streamlit_key_suffix:
    case "":
      st.write("Here are some ideas: rewrite copy, make copy longer, convert a text into an email, or write copy based off a starter phrase/quote.")
    case "_corporate":
      st.write("Here are some ideas: write a press release based off of a news article (feel free to paste in the link), generate multiple versions of a draft pitch, convert one type of content into another, provide examples of good final products.")
    case _:
      pass #deliberately non-exhaustive
  #could: use session state for all of these controls instead of doing all this argument passing of voice, etc...
  accessable_voices: tuple[Voice, ...] = (voice_default,) # I wouldn't have written the code this way were it not for a shocking(ly intended) weakness in pyright: https://github.com/microsoft/pyright/issues/9173
  ds = voices_corporate if streamlit_key_suffix == "_corporate" else voices_noncorporate
  accessable_voices += tuple(d for d in get_list_value_of_column_in_table("voices", "cicero.ref_tables.user_pods") if d in ds and d != voice_default)
  if is_admin(): # Admins get to see all voices, although (for clarity's sake) only the voices per the type of chat.
    accessable_voices = ds
  voice = st.selectbox("Voice (you must reset the chat for a change to this to take effect)", accessable_voices)
  account = st.selectbox("Use historical messages from this account:", ("No account",)  + load_account_names(), key="account") if streamlit_key_suffix != "_corporate" else st.text_input("Account")
  expand_links = st.checkbox("Expand links", value=True) if is_admin() else True
  model_name = st.selectbox("Model", short_model_names, key="model_name") if is_admin() else short_model_name_default
  st.file_uploader(label="Upload a file", key="chat_file_uploader", type=['csv', 'docx', 'html', 'htm', 'txt', 'xls', 'xlsx'], accept_multiple_files=False, on_change=grow_chat, args=(streamlit_key_suffix, True, account, model_name, voice, expand_links)) if is_admin() else None #note: this seems like a DRY violation to me... #TODO: file upload currently lets people bypass good/bad rating. However, we could hide it when in the asking-for-rating state, if that is deemed a good idea.
  if st.button("Clear conversion"):
    reset_chat(streamlit_key_suffix)
  display_chat(streamlit_key_suffix, account=account, short_model_name=model_name, voice=voice, expand_links=expand_links)

if __name__ == "__main__":
  main()
