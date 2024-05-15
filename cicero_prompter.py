#!/usr/bin/env -S streamlit run

"""Post hoc ergo prompter hoc?"""

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date
#COULD: use https://pypi.org/project/streamlit-profiler/ for profiling
from transformers import GenerationConfig
from typing import Literal, Iterable, TypedDict, TypeVar
from zoneinfo import ZoneInfo as z
from cicero_shared import assert_always, exit_error, load_account_names, sql_call, sql_call_cacheless, topics_big, Row
import cicero_rag_only

from num2words import num2words
from itertools import chain, combinations
from functools import reduce
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatDatabricks
from langchain.schema.output_parser import StrOutputParser

import re
import random
from os import environ

def external_topic_names_to_internal_topic_names_list_mapping(external_topic_names: list[str]) -> list[str]:
  return [topics_big[e]["internal name"] for e in external_topic_names]

@st.cache_data()
def load_model_permissions(useremail: str) -> list[str]:
  results = sql_call("SELECT DISTINCT modelname FROM models.default.permissions WHERE useremail = :useremail", {'useremail': useremail})
  return [result[0].lower() for result in results]

def ensure_existence_of_activity_log() -> None:
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.activity_log (datetime string, useremail string, promptsent string, responsegiven string, modelparams string, modelname string, modelurl string, pod string)")

@st.cache_data() #STREAMLIT-BUG-WORKAROUND: Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
def count_from_activity_log_times_used_today(useremail: str) -> int: #this goes by whatever the datetime default timezone is because we don't expect the exact boundary to matter much.
  ensure_existence_of_activity_log()
  return int( sql_call(f"SELECT COUNT(*) FROM cicero.default.activity_log WHERE useremail = :useremail AND datetime LIKE '{date.today()}%%'", {'useremail': useremail})[0][0] )

def write_to_activity_log_table(datetime: str, useremail: str, promptsent: str, responsegiven: str, modelparams: str, modelname: str, modelurl: str) -> None:
  """Write the arguments into the activity_log table. If you change the arguments this function takes, you must change the sql_call in the function and in ensure_existence_of_activity_log. It wasn't worth generating them programmatically. (You must also change the caller function of this function, of course.)"""
  keyword_arguments = locals() # This is a dict of the arguments passed to the function. It must be called at the top of the function, because if it is called later then it will list any other local variables as well. (The docstring isn't included; I guess it's the __doc__ attribute of the enclosing function, not a local variable. <https://docs.python.org/3.11/glossary.html#term-docstring>)
  ensure_existence_of_activity_log()
  sql_call_cacheless(
    "WITH tmp(pod) AS (SELECT user_pod FROM cicero.default.user_pods WHERE user_email ilike :useremail)\
    INSERT INTO cicero.default.activity_log\
            ( datetime,  useremail,  promptsent,  responsegiven,  modelparams,  modelname,  modelurl,  pod)\
      SELECT :datetime, :useremail, :promptsent, :responsegiven, :modelparams, :modelname, :modelurl,  pod FROM tmp",
    keyword_arguments
  )

@st.cache_data()
def load_bios() -> dict[str, str]:
  return {row["candidate"]:row["bio"] for row in sql_call("SELECT candidate, bio FROM cicero.default.ref_bios")}

@st.cache_data()
def load_bio(candidate: str) -> str:
  return str( sql_call("SELECT bio FROM cicero.default.ref_bios WHERE candidate = :candidate", locals())[0][0] )

@st.cache_data()
def load_headlines(get_all: bool = False, past_days: int = 7) -> list[str]:
   # The (arbitrary) requirement is that we return results from the last 7 days by default.
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.headline_log (datetime string, headline string)")
  results = sql_call(
    "SELECT headline FROM cicero.default.headline_log " +
    (f"WHERE datetime >= NOW() - INTERVAL {past_days} DAY " if not get_all else "") +
    "GROUP BY headline ORDER BY min(datetime) DESC"
  )
  return [result[0] for result in results]

#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
class PresetsPayload(TypedDict):
  temperature: float
  target_charcount_min: int
  target_charcount_max: int
  num_beams: int
  top_k: int
  top_p: float
  repetition_penalty: float
  no_repeat_ngram_size: int
  num_return_sequences: int
  early_stopping: bool
  do_sample: bool
  output_scores: bool
  model: str
  account: str | None
  ask_type: str
  tone: list[str]
  topics: list[str]
  additional_topics: str
  exact_match_query: str
  headline: str | None
  overdrive: bool
  num_outputs: int

presets: dict[str, PresetsPayload] = {
  "default": {
    "temperature": 0.7,
    "target_charcount_min": 80,
    "target_charcount_max": 160,
    "num_beams" : 1,
    "top_k" : 50,
    "top_p" : 1.0,
    "repetition_penalty" : 1.2,
    "no_repeat_ngram_size" : 4,
    "num_return_sequences" : 5,
    "early_stopping" : False,
    "do_sample" : True,
    "output_scores" : False,
    "model": "gpt-short-medium-long",
    "account" : None,
    "ask_type": "Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
    "exact_match_query": "",
    "headline": None,
    "overdrive": False,
    "num_outputs": 5
  },
}

def set_ui_to_preset(preset_name: str) -> None:
  preset = presets[preset_name]
  for key, value in preset.items():
    st.session_state[key] = value

def list_from_cicero_tone_format_to_human_format(l: list[str]) -> list[str]:
  return [x.replace("_", " ").title() for x in l]
def list_from_human_format_to_cicero_tone_format(l: list[str]) -> list[str]:
  return [x.replace(" ", "_").lower() for x in l]
def list_to_bracketeds_string(l: list[str]) -> str:
  return " ".join([f"[{i}]" for i in l])

def only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(l: list[str], s: str) -> list[str]:
  return [x for x in l if s.lower() in x.lower()]

def execute_prompting(account: str, ask_type: str, topics: list[str], additional_topics: list[str], tones: list[str], text_len: Literal["short", "medium", "long", ""], headline: str|None, num_outputs: int, model_temperature: float = 0.8, use_bio: bool = True) -> tuple[str, list[str]]:
  score_threshold = 0.5 # Document Similarity Score Acceptance Threshold
  doc_pool_size = 10 # Document Pool Size
  num_examples = 10 # Number of Documents to Use as Examples
  assert_always(num_examples <= doc_pool_size, "You can't ask to provide more examples than there are documents in the pool! Try again with a different value.")
  num_outputs = 5 # Number of Texts the Model Should Generate
  output_table_name = "models.lovelytics.gold_text_outputs" # Text Output Table Name
  ref_tag_name = "models.lovelytics.ref_tags" # Tags Table Name #TODO: possibly use topic_tags = set(x["Tag_Name"] for x in spark.read.table(ref_tag_name).filter(col("Tag_Type") == "Topic").select("Tag_Name").collect()) etc etc logic. Probably this gets address when Wes emails me a second diff.
  rag_output_table_name = "models.lovelytics.rag_outputs" # RAG Outputs Table Name
  primary_key = "PROJECT_NAME" # Index Table Primary Key Name
  topic_weight = 4 # Topic Filter Weight
  tone_weight = 1 # Tone Filter Weight
  client_weight = 6 # Client Filter Weight (client is a synonym for account)
  ask_weight = 2 # Ask Type Weight
  text_len_weight = 4 # Text Length Weight

  topics_str = ", ".join(topics)
  tones_str = ", ".join(tones)

  # Create a target prompt that is used during the vector index similarity search to score retrieved texts.
  target_prompt = f"A {text_len} {ask_type} text message from {account}" + f" about {topics_str}"*bool(topics) + f" written with an emphasis on {tones_str}"*bool(tones)

  #### Create All Possible Filter Combinations and Sort By Importance ###

  ### Tag importance from most important to least
  # Topics (Tp)
  # Account/Client Name (C)
  # Ask Type (A)
  # Tone (To)
  # Ask Length (L)
  ### Example Priority Ordering
  # Tp, C, A, To, L
  # Tp, C, A, To
  # Tp, C, A, L
  # Tp, C, A
  # Tp, C, To, L
  # Tp, C, To
  # Tp, C, L
  # Tp, C

  # Used to generate powersets of filters
  T = TypeVar('T') # Could: Changed in version 3.12: Syntactic support for generics is new in Python 3.12.
  def powerset(iterable: Iterable[T], start: int = 0) -> Iterable[tuple[T]]: #TODO: once the code is mostly working, muck about with this and its types. (Need the code to be working to make sure it continues to work after the transformations lol.)
    "powerset([1,2,3]) → () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    assert 0 <= start <= len(s) #TODO: is this check necessary? Or will it just return () in "bad" cases?
    return chain.from_iterable(combinations(s, r) for r in range(start, len(s)+1))

  # Generate the powersets (i.e. each combination of items) for both topics and tones
  # Normally, the set starts with length of 0, but for performance purposes either start with 1 or 0, depending on if the list is empty
  # e.g. the powerset of [a, b] would be [(), (a), (b), (a, b)] but by starting with length 1 we only need to consider [(a), (b), (a, b)]
  # We only start with length 0 if there are no topics or tones. This is to make sure we at least generate filter combinations using the other three filter types
  # The topic/tone combinations are joined together with (, .*){1,} which is a regex pattern that means
  # match at least one time the pattern of a comma and space followed by any character zero or more times
  # So a(, .*){1,}b would mean: in the search space look for a, then at least one or more characters, and then b
  # This would match the string a, b and a, c, d, e, f, g, b
  # And would not match the string acdb
  # ^(?=.*\btopic\b)(?=.*\btopic\b).*$ regex for matching
  topic_sets = [("topics", "(, .*){1,}".join(x), topic_weight * len(x)) for x in powerset(sorted(topics), start=min(1, len(topics)))]
  tone_sets = [("tones", "(, .*){1,}".join(x), tone_weight * len(x)) for x in powerset(sorted(tones), start=min(1, len(tones)))]
  combos = set()
  # Iterate through each pairing of topics and tones
  for tp in topic_sets:
    for to in tone_sets:
      # Generate every combination between client, ask type, text length, topic, and tone
      # This means that for each topic set and tone set, we're generating every possible combination between those and the client, ask, and length
      temp_arr = [("client", account, client_weight), ("ask", ask_type, ask_weight), ("text_len", text_len, text_len_weight)]
      # But only add the topics and tones if they exist i.e. are not an empty string
      if tp[-1] != 0:
        temp_arr.append(tp)
      if to[-1] != 0:
        temp_arr.append(to)
      # Then update the set of filter combinations. A set is used to remove any duplicate filter combinations
      # Note that each filter tag (e.g. client, a topic set) has it's own weight value that dictate the filter's importance
      # Higher weight filters will be used first
      # When the sets of all filters are generated, their combined weight is summed together using the reduce function
      combos.update((x, reduce(lambda a, b: a+b[2], x, 0))  if len(x) != 0 else (x, 0) for x in powerset(temp_arr))
  # Then, the filters are sorted by their weight in descending order
  # So higher weight filter combinations are first in the array which means any documents with those filters will be considered first
  combos = [{y[0]: y[1] for y in x[0]} for x in sorted(combos, key=lambda a: a[1], reverse=True)]

  ### Find as Many Relevant Documents as Possible ###

  @st.cache_data()
  def read_output_table() -> list[Row]:
    return sql_call(f"SELECT * from {output_table_name}")

  text_rows = read_output_table()

  # results_found is a set of every primary key we've search so far
  # This is to prevent duplicate documents/texts from showing up
  results_found = set()
  # reference_texts will be a list of dictionaries containing example user prompts and assistant responses (i.e. the text messages)
  reference_texts : list[dict[str, str]] = []
  for c in combos:
      results = [
        row[primary_key] for row in text_rows if # Only apply filters if they are present in the current filter combination.
          (row[primary_key] not in results_found                              )  and
          ("topics"   not in c    or    re.search(c["topics"], row["topics"]) )  and
          ("tones"    not in c    or    re.search(c["tones"], row["tones"])   )  and
          ("client"   not in c    or    c["client"] == row["Client_Name"]     )  and
          ("ask"      not in c    or    c["ask"] == row["Ask_Type"]           )  and
          ("text_len" not in c    or    c["text_len"] == row["Text_Length"]   )
      ]
      # If no results were found, move onto the next filter combination. Otherwise, continue the process of considering these candidate results.
      if not results:
        continue
      results_found.update(results) # add the found primary key values to the results_found set
      # TODO: probably put faiss back in here.
      # TODO: Perform a similarity search using the target_prompt defined beforehand. Filter for / use only the results we found earlier in this current iteration.
      # TODO: Then add all results returned by the similarity search to the reference_texts list. But only if their similarity score is greater than the score_threshold parameter.
      if 0 != 0: #TODO: size of result here, then formatting
          reference_texts.extend({"prompt": "Please write me a" + x[0].split(":\n\n", 1)[0][1:], "text": x[0].split(":\n\n", 1)[1], "score": x[-1]} for x in vs_search["result"]["data_array"] if x[-1] > score_threshold)
      # If we've found at least the number of desired documents, exit the loop and take the first doc_pool_size number of texts. The beginning of the reference_texts array will contain the texts that match the most important filters and the highest similarity scores.
      if len(reference_texts) >= doc_pool_size:
          reference_texts = reference_texts[:doc_pool_size]
          break

  ### Query Endpoints ###

  # Randomize the order of the example texts. If you pass in the texts in some order, such as short, medium, and long, if you ask for a short, it is more likely to write a short, then medium, then long
  texts_to_use = random.sample(reference_texts, k=min(num_examples, len(reference_texts)))
  # We reinsert and separate the found documents into two separate dictionaries. This makes it easier to assemble the RAG prompt and pass them as string format variables to langchain
  ms_prompts = {}
  ms_texts = {}
  for num, content in enumerate(texts_to_use):
    ms_prompts[f"example_{num + 1}_p"] = content["prompt"]
    ms_texts[f"example_{num + 1}_t"] = content["text"]

  ##### INSERT PROMPT HERE #####
  # Llama-3 Prompt Styling
  # Base beginning structure of the RAG prompt
  rag_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"

  # Define the system prompt
  sys_prompt = """You are an expert copywriter who specializes in writing text messages for conservative candidates in the United States of America. Do not start your message with 'Dear', 'Subject', or 'Hello'. Try to grab the reader's attention in the first line. Do not explicitly use language such as 'Donate now' or '[DONATE]', instead use language like 'Rush', 'Support', or 'Chip in'. Do not make up facts or statistics. Do not use emojis or hashtags in your messages. Do not exactly copy the example text messages. Write the exact number of text messages asked for."""
  # Add instructions on how long or short a text should be depending on the text length we want the model to generate
  # Add specificity of specific ask type of the text message too
  # Try to make the model understand that the outputs we specifically are asking for should be this length
  if text_len == "short":
      sys_prompt += f" Your short {ask_type} text messages should be less than 160 characters in length, use less than 35 words, and have less than 2 sentences."
  elif text_len == "medium":
      sys_prompt += f" Your medium-length {ask_type} text messages should be between 160 and 400 characters in length, use between 35 to 70 words, and have between 3 to 5 sentences."
  elif text_len == "long":
      sys_prompt += f" Your long {ask_type} text messages should be more than 400 characters in length, use more than 70 words, and have more than 6 sentences."
  # combined_dict stores all of the string format variables used in the prompt and their values
  combined_dict = {}
  # Add bio and headline information if those are available
  if use_bio and account:
      sys_prompt += f""" Here is important biographical information about the conservative candidate you are writing for: {load_bio(account)}"""
  if headline:
      sys_prompt += f""" Here is/are news headline(s) you should reference in your text messages: {headline}"""
  # Add system_prompt to combined_dict
  combined_dict["system_prompt"] = sys_prompt

  # Then for every example document, we add the corresponding assistant and user lines
  # Triple brackets are used so the actual key name in the ms_prompts and ms_texts dictionaries can be inserted dynamically while also keeping the curly braces in the final string
  # So for example, if k = "apples" f"I like to eat {{{k}}}" would return the string "I like to eat {apples}"
  for k in ms_prompts.keys():
    ok = k.rsplit("_", 1)[0] + "_t"
    rag_prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{{{k}}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{{{ok}}}<|eot_id|>"

  # Add in the final component of the RAG prompt where we pass in the prompt/question we want to send to the model
  rag_prompt += "<|start_header_id|>user<|end_header_id|>\n\n{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
  # Combine all of the dictionaries with the string format keys and values for langchain parameter passing usage
  combined_dict = combined_dict | ms_prompts | ms_texts

  # Create the question prompt and add it to the combined_dict dictionary
  combined_dict["question"] = f"Please write me {num2words(num_outputs)} {text_len} {ask_type} text message(s) from {account}" + bool(topics)*f" about {topics_str}" + bool(tones)*f" written with an emphasis on {tones_str}"

  ##### END PROMPT INSERTION #####
  # print(rag_prompt)

  # Create the prompt template using langchain's PromptTemplate
  # Tell it that the input variables it should expect is everything in our combined_dict dictionary
  prompt = PromptTemplate(
    input_variables=list(combined_dict.keys()),
    template=rag_prompt
  )

  # Estimate the number of tokens our prompt is
  # This is important for querying the Llama-2 model only since it has a limit of 4096 tokens for its input and output combined
  # e.g. if our input is 4000 tokens, then we can only have 96 tokens for the output
  token_count = len( prompt.format( **combined_dict ) ) // 3
  # see note about environ in rag_only
  environ['DATABRICKS_HOST'] = "https://"+st.secrets['DATABRICKS_SERVER_HOSTNAME']
  environ['DATABRICKS_TOKEN'] = st.secrets["databricks_api_token"]
  # TODO: connect model temperature to Output Variance slider
  dbrx_chat_model = ChatDatabricks(endpoint="databricks-dbrx-instruct", max_tokens=4096, temperature=model_temperature)
  llama_3_chat_model = ChatDatabricks(endpoint="databricks-meta-llama-3-70b-instruct", max_tokens=4096, temperature=model_temperature)
  mixtral_chat_model = ChatDatabricks(endpoint="databricks-mixtral-8x7b-instruct", max_tokens=4096, temperature=model_temperature)

  # Assemble all of the LLM chains which makes it easier to invoke them and parse their outputs
  # This uses langchain's own pipe syntax to organize multiple components into a "pipe"
  dbrx_chain = ( prompt | dbrx_chat_model | StrOutputParser() )
  llama_3_chain = ( prompt | llama_3_chat_model | StrOutputParser() )
  mixtral_chain = ( prompt | mixtral_chat_model | StrOutputParser() )
  llm_chains = {"dbrx": dbrx_chain, "llama-3": llama_3_chain, "mixtral": mixtral_chain}
  if not token_count >= 4096: # Only use the llama-2 if we know the input prompt isn't greater than or equal to 4096 tokens (a weakness of llama-2)
    llama_chat_model = ChatDatabricks(endpoint="databricks-llama-2-70b-chat", max_tokens=4096-token_count, temperature=model_temperature)
    llama_chain = ( prompt | llama_chat_model | StrOutputParser() )
    llm_chains["llama-2"] = llama_chain

  # For every LLM, query it with our prompt and print the outputs
  # Also save the outputs into a dictionary which we'll write to a delta table
  all_responses = {}
  all_responses["full_prompt"] = prompt.format(**combined_dict)
  for llm_name, llm_chain in llm_chains.items():
    print(f"#### {llm_name} OUTPUTS ####")
    inv_res = llm_chain.invoke(combined_dict)
    print(inv_res)
    all_responses[llm_name] = inv_res
    print()

  # We'll leave the code here commented out, in case we get a new API to use from SMC
  # print(f"#### SMC API OUTPUTS ####")
  # url = "https://relay.stagwellmarketingcloud.io/google/v1/projects/141311124325/locations/us-central1/endpoints/2940118281928835072:predict"
  # payload = {"instances": [
  #         {
  #             "prompt": prompt.format(**combined_dict),
  #             "temperature": model_temperature,
  #             "max_tokens": 2048,
  #             "stop": ["<|eot_id|>", "<|end_of_text|>"]
  #         }
  #     ]}
  # headers = {
  #   "Content-Type": "application/json",
  #   "smc-owner": "...",
  #   "Authorization": "Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImZmYzU1ZmNiLTkwZTMtNGI4OS1iMmY0LTQ1Mjg0OWE3MWZiNCIsImlzcyI6IlNNQyIsImtleU5hbWUiOiJUYXJnZXRkVmljdG9yeSBNTVMiLCJraWQiOiI5M2M5OGRiMDVmZmUyNDI3NDZkM2IyYzYwMDIzNDYxNiIsIm9yZ0lkIjoiNjA0NTM3MjYtYWY4ZC00NjQ2LTk2ZTktNzRjNjQyMWZiNDI0In0.XNnsi6d_47yBLgHZwouoEtqC6IB-bfaLnGL6kB3Ldw9oXLCfEOuXygFGMhlH7ywTHowaoegPPygYiQ-Z78lsDQ"
  # }
  # response = requests.request("POST", url, json=payload, headers=headers)
  # response_json = json.loads(response.text)
  # response_text = response_json["predictions"][0].rsplit("Output:", 1)[-1].strip()
  # all_responses["smc_api"] = response_text
  # print(response_text)

  print("The table makes use of a Batch_Number column to mark which outputs were generated at the same time")
  # There's also an Output_Datetime column which contains the actual datetime the outputs were created, which will be the same value for outputs within the same batch
  # But a batch number is easier to communicate to others and understand at a quick glance

  try: # If the table already exists, the new batch number should be one greater than the last one
    batch_num = 1 + sql_call(f"SELECT batch_number FROM {rag_output_table_name} ORDER BY batch_number DESC LIMIT 1")[0][0]
  except Exception as e: # If the table doesn't exist, the first batch will be batch number 1
    print("No batch number found, resetting batch number to 1.")
    batch_num = 1

  print("Let's save all of our LLM outputs to a delta table!")
  for key_that_is_source, value_that_is_contents in all_responses.items():
    sql_call(
      f"INSERT INTO {rag_output_table_name} ( batch_number,  output_source,  output_content,  output_datetime)\
                                     VALUES (:batch_number, :output_source, :output_content, :output_datetime)",
      {"batch_number": batch_num, "output_source": key_that_is_source, "output_content": value_that_is_contents, "output_datetime": datetime.now(z("US/Eastern"))}
    )
  print("Done :)")
  return target_prompt, list(all_responses.values())

def main() -> None:

  if not st.session_state.get('email'): #TODO: this line is of dubious usefulness. It's supposed to let you run cicero_prompter.py locally and stand-alone without cicero.py, however.
    st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  if 'use_count' not in st.session_state:
    st.session_state['use_count'] = count_from_activity_log_times_used_today(st.session_state["email"])
  use_count_limit = 100 #arbitrary but reasonable choice of limit
  if st.session_state['email'] in ["abrady@targetedvictory.com", "thall@targetedvictory.com", "test@example.com"]: # Give certain users nigh-unlimited uses.
    use_count_limit = 100_000_000
  if st.session_state['use_count'] >= use_count_limit:
    st.write(f"You cannot use this service more than {use_count_limit} times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
    exit_error(52) # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

  model_permissions = load_model_permissions(st.session_state['email']) #model_permissions stores model names as ***all lowercase***
  if presets["default"]["model"] not in model_permissions: #We want everyone to want to have access to this default, at least at time of writing this comment.
    model_permissions.insert(0, presets["default"]["model"])
  #NOTE: these model secrets have to begin the secrets.toml as, like:
  # models.gpt-revamp = ''
  # models.Context = ''
  # Or some other way of making a dict in toml
  models: dict[str,str] = { k:v for k, v in st.secrets['models'].items() if k.lower() in [m.lower() for m in model_permissions] } #filter for what the actual permissions are for the user.

  bios: dict[str, str] = load_bios()

  account_names = load_account_names()

  if not st.session_state.get("initted"):
    set_ui_to_preset("default")
    st.session_state["initted"] = True
    st.rerun() #STREAMLIT-BUG-WORKAROUND: this rerun actually has nothing to do with initing, it's just convenient to do here, since we need to do it exactly once, on app startup. It prevents the expander from experiencing a streamlit bug (<https://github.com/streamlit/streamlit/issues/2360>) that is only present in the initial run state. Anyway, this rerun is really fast and breaks nothing (except the developer mode initial performance timer readout, which is now clobbered) so it's a good workaround.

  login_activity_counter_container = st.container()

  if st.button("Reset", help="Resets the UI elements to their default values. This button will also trigger cached data like the Candidate Bios and the news RSS feed to refresh. You can also just press F5 to refresh the page."):
    st.cache_data.clear()
    set_ui_to_preset("default")

  # setting default values for advanced parameters for our non-developer end-user
  # only used for fine-tuned models
  # num_beams: int = 1
  # top_k: int = 50
  # top_p: float = 1.0
  # repetition_penalty: float = 1.2
  # no_repeat_ngram_size: int = 4
  # num_return_sequences: int = 5
  # early_stopping: bool = False
  # do_sample: bool = True
  # output_scores: bool = False

  #For technical reasons (various parts of it update when other parts of it are changed, iirc) this can't go within the st.form

  with st.expander(r"$\textsf{\Large NEWS HEADLINES}$"):
    exact_match_query = st.text_input("Headline Search  \n*Returns headlines containing the search terms. Hit Enter to filter the headlines.*", key="exact_match_query")
    overdrive: bool = st.checkbox("Only search headlines from the last 3 days.", key="overdrive")
    h: list[str] = load_headlines(get_all=False) if not overdrive else load_headlines(get_all=False, past_days=3)
    if exact_match_query:
      h = only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(h, exact_match_query)
    headline = st.selectbox("If a headline is selected here, it will be added to your prompt below.", list(h), key="headline")

  st.text("") # Just for vertical spacing.

  with st.form('query_builder'):
    # with st.sidebar:
      # if st.session_state["developer_mode"]:
        # only used for fine-tuned models
        # with st.expander("Advanced Parameters"):
        #   num_beams = int( st.number_input("num_beams:", min_value=1, format='%d', step=1, key="num_beams", help="Number of beams for beam search. 1 means no beam search. Beam search is a particular strategy for generating text that the model can elect to use or not use. It can use more or fewer beams in the beam search, as well. More beams basically means it considers more candidate possibilities.") )
        #   top_k = int( st.number_input("top_k:", min_value=1, format='%d', step=1, key="top_k" , help="The number of highest probability vocabulary tokens to keep for top-k-filtering. In other words: how many likely words the model will consider."))
        #   top_p = st.number_input("top_p:", min_value=0.0, format='%f', key="top_p" , help="A decimal number, not merely an integer. If set to < 1, only the smallest set of most probable tokens with probabilities that add up to top_p or higher are kept for generation. In other words: if you reduce this number below 1, the model will consider fewer possibilities.")
        #   repetition_penalty = st.number_input("repetition_penalty:", min_value=1.0, max_value=2.0, format='%f', key="repetition_penalty" , help="A decimal number, not merely an integer. The parameter for repetition penalty. 1.0 means no penalty. In other words: if you increase this parameter, the model will be less likely to repeat itself.")
        #   no_repeat_ngram_size = int( st.number_input("no_repeat_ngram_size:", min_value=0, max_value=10, format='%d', step=1, key="no_repeat_ngram_size" , help="If set to > 0, all ngrams (essentially, continuous sequences of words or word-parts) of that size can only occur once. In other words: if you set this parameter to a number greater than 0, any string of words can only occur in the output at most that many times.") )
        #   num_return_sequences = int( st.number_input("num_return_sequences:", min_value=1, max_value=10, format='%d', step=1, key="num_return_sequences" , help="The number of independently computed returned sequences for each element in the batch. In other words: how many responses you want the model to generate.") )
        #   early_stopping = st.checkbox("early_stopping", key="early_stopping" , help="Controls the stopping condition for beam-based methods, like beam-search. It accepts the following values: True, where the generation stops as soon as there are num_beams complete candidates; False, where an heuristic is applied and the generation stops when is it very unlikely to find better candidates; \"never\", where the beam search procedure only stops when there cannot be better candidates (canonical beam search algorithm). In other words: if the model is using beam search (see num_beams, above), then if this box is checked the model will spend less time trying to improve its beams after it generates them. If num_beams = 1, this checkbox does nothing either way. There is no way to select \"never\" using this checkbox, as that setting is just a waste of time.")
        #   do_sample = st.checkbox("do_sample", key="do_sample" , help="Whether or not to use sampling ; use greedy decoding otherwise. These are two different strategies the model can use to generate text. Greedy is probably much worse, and you should probably always keep this box checked.")
        #   output_scores = st.checkbox("output_scores", key="output_scores" , help="Whether or not to return the prediction scores. See scores under returned tensors for more details. In other words: This will not only give you back responses, like normal, it will also tell you how likely the model thinks the response is. Usually useless, and there's probably no need to check this box.")
    
    
    model_name = presets["default"]["model"] #COULD: clean up this code to remove all of the logic related to this although I think we still want to save the model name and uri in the activity log)
    model_uri = models[model_name]
    account = st.selectbox("Account (required)", list(account_names), key="account")
    ask_type = str( st.selectbox("Ask Type", ['Hard Ask', 'Medium Ask', 'Soft Ask', 'Soft Ask Petition', 'Soft Ask Poll', 'Soft Ask Survey'], key="ask_type") ).lower()
    topics = st.multiselect("Topics", sorted([t for t, d in topics_big.items() if d["show in prompter?"]]), key="topics" )
    length_select = st.selectbox("Length", ['Short', 'Medium', 'Long'], key='lengths')
    additional_topics = [x.strip() for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
    tones = st.multiselect("Tones", ['Agency', 'Apologetic', 'Candid', 'Exclusivity', 'Fiesty', 'Grateful', 'Not Asking For Money', 'Pleading', 'Quick Request', 'Secretive', 'Time Sensitive', 'Urgency'], key="tone") #TODO: , 'Swear Jar' will probably be in here some day, but we don't have "we need more swear jar data to make this tone better"
    num_outputs : int = st.slider("Number of outputs", min_value=1, max_value=10, key="num_outputs")
    temperature: float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") if st.session_state["developer_mode"] else 0.7
    # target_charcount_min = st.number_input("Min Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_min")
    # target_charcount_max = st.number_input("Max Target Characters:", min_value=40, format='%d', step=1, key="target_charcount_max") #help="Short: <=160 | Medium: >160, <400 | Long: >=400"
    generate_button = st.form_submit_button("Submit")

  # if model_name != 'gpt-short-medium-long': #TODO: is this still useful?
  #   text_length: Literal["short", "medium", "long", ""] = "" #TODO: presumably I have to narrow this to
  # else:
  #   if target_charcount_max <= 160: #TODO: would be cleaner to just pass the target_charcount_max into the function, instead of this string
  #     text_length = "short"
  #   elif target_charcount_max > 160 and target_charcount_max < 400:
  #     text_length = "medium"
  #   elif target_charcount_max >= 400:
  #     text_length = "long"

  #Composition and sending a request:
  did_a_query = False
  if generate_button:
    if not account:
      st.error("***No Account is selected, so I can't send the request!***")
    else:
      did_a_query = True
      st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
      use_bio=("Bio" in topics and account in bios)
      #TODO: does this use the internal or external topic names?
      sorted( external_topic_names_to_internal_topic_names_list_mapping(topics) )
      list_from_human_format_to_cicero_tone_format(additional_topics)
      list_from_human_format_to_cicero_tone_format(tones) #TODO: does this need: `or ["No Hook"]`
      promptsent, outputs = execute_prompting(account, ask_type, topics, additional_topics, tones, length_select, headline, num_outputs, temperature, use_bio, )
      st.session_state['outputs'] = outputs
      if 'history' not in st.session_state: st.session_state['history'] = []
      st.session_state['history'] += outputs
      st.session_state['character_counts_caption'] = "Character counts: "+str([len(o) for o in outputs])

  # The idea is for these output elements to persist after one query button, until overwritten by the results of the next query.
  if 'human-facing_prompt' in st.session_state:
    st.caption(st.session_state['human-facing_prompt'].replace("$", r"\$"))
    if 'developer-facing_prompt' in st.session_state and st.session_state["developer_mode"]:
      st.caption("Developer Mode Message: the prompt passed to the model is: "+ st.session_state['developer-facing_prompt'].replace("$", r"\$"))

  st.error("WARNING! Outputs have not been fact checked. CICERO is not responsible for inaccuracies in deployed copy. Please check all *names*, *places*, *counts*, *times*, *events*, and *titles* (esp. military titles) for accuracy.  \nAll numbers included in outputs are suggestions only and should be updated. They are NOT analytically optimized to increase conversions (yet) and are based solely on frequency in past copy.", icon="⚠️")
  if 'outputs' in st.session_state:
    for output in st.session_state['outputs']:
      col1, col2 = st.columns([.95, .05])
      with col1:
        st.write( output.replace("$", r"\$") ) #this prevents us from entering math mode when we ask about money.
      if st.session_state.get("developer_mode"):
        with col2:
          if st.button("🖋️", key="🖋️"+output, help="Send down to Cicero"):
            default_reply = "Here is a conservative fundraising text: [" + output + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email."
            st.session_state['cicero_ai']=default_reply
            st.session_state['display_only_this_at_first_blush'] = "«"+output+"»"
    st.caption(st.session_state.get('character_counts_caption'))
    if st.session_state.get('cicero_ai'):
      if isinstance(st.session_state['cicero_ai'], int): # Arbitrary truthy value that isn't a string (so thus can't be from the responses above, which are text)
        cicero_rag_only.main(streamlit_key_suffix="_prompter")
      else:
        #clear previous chat history
        st.session_state.chat = None
        st.session_state.messages = None
        cicero_rag_only.grow_chat(streamlit_key_suffix="_prompter", alternate_content=st.session_state['cicero_ai'], display_only_this_at_first_blush=st.session_state['display_only_this_at_first_blush'])
        cicero_rag_only.main(streamlit_key_suffix="_prompter")
        st.session_state['cicero_ai'] = 2 # This sets the arbitrary value discussed above.

  st.error('**REMINDER!** Please tag all projects with "**optimization**" in the LABELS field in Salesforce.')

  with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
    st.header("History of replies:")
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)

  login_activity_counter_container.write(
    f"""You are logged in as {st.session_state['email']}{" (internally, "+str(st.experimental_user['email'])+")" if st.session_state["developer_mode"] else ""}. You have prompted {st.session_state['use_count']} time{'s' if st.session_state['use_count'] != 1 else ''} today, out of a limit of {use_count_limit}. {"You are in developer mode." if st.session_state["developer_mode"] else ""}"""
  )

  # Activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query.
  if did_a_query:
    # promptsent is only illustrative. But maybe that's enough.
    write_to_activity_log_table( datetime=str(datetime.now()), useremail=st.session_state['email'], promptsent=promptsent, responsegiven=json.dumps(outputs), modelparams="(wes-rag-only strategy has no singular modelparams to record, at least at the moment)", modelname="(wes-rag-only strategy has no singular model_name to record, at least at the moment)", modelurl="(wes-rag-only strategy has no singular modelurl to record, at least at the moment)" )

  # st.components.v1.html('<!--<script>//you can include arbitrary html and javascript this way</script>-->') #or, use st.markdown, if you want arbitrary html but javascript isn't needed.

if __name__ == "__main__": main()
