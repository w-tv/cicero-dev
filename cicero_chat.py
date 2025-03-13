#!/usr/bin/env -S streamlit run

"""Cicero (the actual, historical man (it's really him))."""

import streamlit as st
from databricks_genai_inference import ChatSession, FoundationModelAPIException
from cicero_shared import are_experimental_features_enabled, catstr, admin_box, get_list_value_of_column_in_table, is_admin, pii_detector, sql_call, ssget, ssset, ssmut, sspop, get_base_url, load_account_names, sql_call_cacheless
from cicero_types import Short_Model_Name, short_model_names, short_model_name_default, short_model_name_to_long_model_name, Chat_Suffix, chat_suffix_default
from cicero_video_brief_system_prompt import nice_text_to_html, video_brief_system_prompt
import bs4 # for some reason bs4 is how you import beautifulsoup
import requests
import re
from pathlib import Path
from io import StringIO
import pandas as pd
from docx import Document
from typing import assert_never, Literal

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
  new_str = content_from_url(m.group(0))
  ssmut(lambda x: (x or "")+'\n\n\n'+new_str.replace("$", r"\$"), "last_url_content") #diagnostic we want to print elsewhere on the page (later)
  return new_str

url_regex = r"""(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""" # from https://gist.github.com/gruber/249502

def expand_url_content(s: str) -> str:
  """Expand the urls in a string to the content of their contents (placing said contents back into the same containing string."""
  return re.sub(pattern=url_regex, repl=content_from_url_regex_match, string=s)

voice_map = sql_call("SELECT * FROM cicero.default.voice_map WHERE enabled = TRUE")

def grow_chat(streamlit_key_suffix: Chat_Suffix, alternate_content: tuple[Literal['normal', 'analyze', 'file', 'resurrect'], str]|None = None, account: str = "No account", short_model_name: Short_Model_Name = short_model_name_default, voice: str = "Default", expand_links: bool = True) -> None:
  """Note that this function will do something special to the prompt (possibly ignoring it) if the first field of the alternate_content tuple is anything but 'normal'.
  Also, the streamlit_key_suffix is only necessary because we use this code in two places. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).
  Random fyi: chat.history is an alias for chat.chat_history (you can mutate chat.chat_history but not chat.history, btw). Internally, it's, like: [{'role': 'system', 'content': 'You are a helpful assistant.'}, {'role': 'user', 'content': 'Knock, knock.'}, {'role': 'assistant', 'content': "Hello! Who's there?"}, {'role': 'user', 'content': 'Guess who!'}, {'role': 'assistant', 'content': "Okay, I'll play along! Is it a person, a place, or a thing?"}]"""

  # determine what the prompt content will be
  match alternate_content:
    case None:
      p = ssget("user_input_for_chatbot_this_frame"+streamlit_key_suffix)
      display_p = p
    case 'normal', payload:
      p = payload
      display_p = p
    case 'resurrect', _:
      p = ssget("resurrect_box"+streamlit_key_suffix)
      display_p = p
    case 'file', _:
      content = ssget("chat_file_uploader")
      file_ext = Path(str(content.name)).suffix
      match file_ext:
        case '.txt' | '.html' | '.htm' :
          stringio = StringIO(content.getvalue().decode("utf-8")) # convert file-like BytesIO object to a string based IO
          p = stringio.read() # read file as string
        case '.docx':
          p = '\n'.join([para.text for para in Document(content).paragraphs]) # read the docx file as string, by extracting the text from each paragraph (I suppose)
        case '.csv':
          x = pd.read_csv(content, nrows=10) # I guess we put only 10 in for testing purposes probably, and likely (TODO) we should just use all rows. (same for excel below)
          st.dataframe(x) # I guess we put this in here for a little visual feedback
          p = str(x)
        case '.xls' | '.xlsx':
          st.dataframe( x := pd.read_excel(content, nrows=10) )
          p = str(x)
        case _:
          p = "Error: Cicero does not currently support this file type!"
      display_p = f"「 {p} 」"
    case 'analyze', payload:
      p = "Here is a conservative fundraising text: [" + payload + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email. Only provide analysis once, unless the user asks for analysis again."
      display_p = "« " + payload + " »"
    case _, _:
      assert_never(alternate_content)

  #detect concerning elements:
  winred_concern = "winred.com" in p.lower()
  fec_concern = "fec.gov" in p.lower()

  # URL content expansion
  if expand_links:
    p = expand_url_content(p)

  #set the system prompt based on various variables
  if voice != "Default":
    sys_prompt = [v["voice_description"] for v in voice_map if v["voice_id"] == voice][0]
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

  old_chat = chat.chat_history.copy()
  while True:
    try:
      chat.reply(p)
      messages.append({"role": "user", "content": display_p})
      messages.append({"avatar": "assets/CiceroChat_800x800.jpg", "role": "assistant", "content": chat.last})
      ssset(
        "activity_log_payload",
        {"user_email": ssget("email"), "prompter_or_chatbot": 'chatbot'+streamlit_key_suffix, "prompt_sent": p, "response_given": chat.last, "model_name": short_model_name, "model_url": chat.model, "model_parameters": str(chat.parameters), "system_prompt": chat.system_message, "base_url": get_base_url(), "used_similarity_search_backup": "no"} | ({"user_feedback": "not asked", "user_feedback_satisfied": "not asked"} if streamlit_key_suffix == "_prompter" else {"user_feedback": "not asked", "user_feedback_satisfied": "not received"}) | {"hit_readlink_time_limit": False} | {"pii_concern": bool(pii_detector(p)), "winred_concern": winred_concern, "fec_concern": fec_concern, "voice": voice, "account": account}
      )
      match streamlit_key_suffix:
        case "" | "_corporate":
          ssset("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix, ssget("activity_log_payload"))
        case "_prompter":
          pass # "_prompter" is deliberately absent, because we don't require anything from it; also it can't even appear here, because it's in the other tab.
        case "_video_brief":
          pass #TODO: should we ask for feedback on the video briefs? I lean no.
        case _:
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
  # We don't force the user to up/down the cleared message if they reset the chat; therefore we do this line:
  sspop("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix)

def cicero_feedback_widget(streamlit_key_suffix: Chat_Suffix, feedback_message: str) -> None:
  """This function returns nothing, and (tees up a state that) writes to the activity log. It also manipulates the session state to remove the session state that leads to its running."""
  # The code that controls the feedback widget and logging is all over the place (in this file, and also in cicero.py). Would be a fine thing to refactor. But it's easy enough to leave it as-is for now. We have higher priorities, and this works the way it is.
  feedback_suffix = "_satisfied"
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
    if o := ssget("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix):
      ssset("activity_log_update", o | {"user_feedback"+feedback_suffix: user_feedback})
      sspop("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix)


def display_chat(streamlit_key_suffix: Chat_Suffix, account: str = "No account", short_model_name: Short_Model_Name = short_model_name_default, voice: str = "Default", expand_links: bool = True) -> None:
  """Display chat messages from history on app reload; this is how we get the messages to display, and then the chat box.
  The streamlit_key_suffix is only necessary because we use this code in two places. But that does make it necessary, for every widget in this function. If streamlit_key_suffix is "", we infer we're in the chat page, and if otherwise we infer we're being used on a different page (so far, the only thing that does this is prompter).

  *A computer can never be held accountable. Therefore a computer must never make a management decision.*[꙳](https://twitter.com/bumblebike/status/832394003492564993)

  the computer knows something we don't
  we must let it make management decisions
  —Alex Chang"""
  needback: bool = are_experimental_features_enabled() and bool(ssget("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix)) #TODO: this is a prototype version that requires you to refresh the page. If we decide to actually have this feature, then for this feature to actually work, I'll have to include logic in the activity log discharger that rewrites the contents of the chat to the right thing (which will have to be in a container).
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
  if ssget("if this is truthy, the user owes us some feedback; the update will use this object", streamlit_key_suffix):
    cicero_feedback_widget(streamlit_key_suffix, "***Like this output?  Let us know to continue chatting.***")
  else:

    if are_experimental_features_enabled():
      result = sql_call_cacheless(
        "SELECT prompt_sent FROM cicero.default.activity_log WHERE user_email == :user_email ORDER BY timestamp DESC",
        {"user_email": ssget('email')}
      )
      st.selectbox("(Optional) use a previous prompt (will be sent to current chat):", [""] + [row[0] for row in result], key="resurrect_box"+streamlit_key_suffix, on_change=grow_chat, args=(streamlit_key_suffix, ('resurrect', ''), account, short_model_name, voice, expand_links))

    st.container().chat_input(key="user_input_for_chatbot_this_frame"+streamlit_key_suffix, on_submit=grow_chat, args=(streamlit_key_suffix, None, account, short_model_name, voice, expand_links) ) #Note that because it's a callback, the profiler will not catch grow_chat here. However, it takes about a second. (Update: maybe it's about 4 seconds, now? That's in the happy path, as well.) #Without the container, this UI element floats BELOW the pyinstrument profiler now, which is inconvenient. But also we might want it to float down later, if we start using streaming text...

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
  relevant_table_enablement_column = "chatbot_corporate" if streamlit_key_suffix == "_corporate" else "chatbot_political"
  accessable_voices = ["Default"] + (["Kellyanne Surrogate"] if streamlit_key_suffix == "" else []) + [v["voice_id"] for v in voice_map if v[relevant_table_enablement_column] is True and (is_admin() or v["voice_id"] in get_list_value_of_column_in_table("voices", "cicero.ref_tables.user_pods"))] # We don't need to check for the voice being enabled in the voice_map, because we already did that in the SQL query.
  voice = st.selectbox("Voice (you must reset the chat for a change to this to take effect)", accessable_voices)
  account = st.selectbox("Use historical messages from this account:", ("No account",)  + load_account_names(), key="account") if streamlit_key_suffix != "_corporate" else st.text_input("Account")
  expand_links = st.checkbox("Expand links", value=True) if are_experimental_features_enabled() else True
  model_name = st.selectbox("Model", short_model_names, key="model_name") if are_experimental_features_enabled() else short_model_name_default
  st.file_uploader(label="Upload a file", key="chat_file_uploader", type=['csv', 'docx', 'html', 'htm', 'txt', 'xls', 'xlsx'], accept_multiple_files=False, on_change=grow_chat, args=(streamlit_key_suffix, True, account, model_name, voice, expand_links)) if are_experimental_features_enabled() else None #note: this seems like a DRY violation to me... #TODO: file upload currently lets people bypass good/bad rating. However, we could hide it when in the asking-for-rating state, if that is deemed a good idea.
  if st.button("Clear conversion"):
    reset_chat(streamlit_key_suffix)
  display_chat(streamlit_key_suffix, account=account, short_model_name=model_name, voice=voice, expand_links=expand_links)

if __name__ == "__main__":
  main()
