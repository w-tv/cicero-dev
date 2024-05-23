#!/usr/bin/env -S streamlit run

"""Post hoc ergo prompter hoc?"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, date
#COULD: use https://pypi.org/project/streamlit-profiler/ for profiling
from typing import Any, Literal, TypedDict, TypeVar
from zoneinfo import ZoneInfo as z
from cicero_shared import assert_always, exit_error, load_account_names, sql_call, sql_call_cacheless, topics_big, Row
import cicero_rag_only

from num2words import num2words
from itertools import combinations
from functools import reduce
from langchain.prompts import PromptTemplate
from langchain_community.chat_models.databricks import ChatDatabricks
from langchain.schema.output_parser import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

import re
import random
import os
from os import environ

from databricks.vector_search.client import VectorSearchClient

def external_topic_names_to_internal_topic_names_list_mapping(external_topic_names: list[str]) -> list[str]:
  return [topics_big[e]["internal name"].replace("_", " ").lower() for e in external_topic_names]

def ensure_existence_of_activity_log() -> None:
  sql_call("CREATE TABLE IF NOT EXISTS cicero.default.activity_log (datetime string, useremail string, promptsent string, responsegiven string, modelparams string, modelname string, modelurl string, pod string)")

@st.cache_data(show_spinner=False) #STREAMLIT-BUG-WORKAROUND: Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
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

@st.cache_data(show_spinner=False)
def load_bios() -> dict[str, str]:
  return {row["candidate"]:row["bio"] for row in sql_call("SELECT candidate, bio FROM cicero.default.ref_bios")}

@st.cache_data(show_spinner=False)
def load_bio(candidate: str) -> str:
  return str( sql_call("SELECT bio FROM cicero.default.ref_bios WHERE candidate = :candidate", locals())[0][0] )

@st.cache_data(show_spinner=False)
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
  model_name: str
  account: str | None
  ask_type: str
  tone: list[str]
  topics: list[str]
  additional_topics: str
  exact_match_query: str
  headline: str | None
  overdrive: bool
  num_outputs: int
  topic_weight: float
  tone_weight: float
  client_weight: float
  ask_weight: float
  text_len_weight: float

presets: dict[str, PresetsPayload] = {
  "default": {
    "temperature": 0.7,
    "model_name": "Llama-3-70b-Instruct",
    "account" : None,
    "ask_type": "Hard Ask",
    "tone" : [],
    "topics" : [],
    "additional_topics" : "",
    "exact_match_query": "",
    "headline": None,
    "overdrive": False,
    "num_outputs": 5,
    "topic_weight": 4,
    "tone_weight": 1,
    "client_weight": 6,
    "ask_weight": 2,
    "text_len_weight": 3
  },
}

def set_ui_to_preset(preset_name: str) -> None:
  preset = presets[preset_name]
  for key, value in preset.items():
    st.session_state[key] = value

def list_lower(l: list[str]) -> list[str]:
  return [x.lower() for x in l]

def only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(l: list[str], s: str) -> list[str]:
  return [x for x in l if s.lower() in x.lower()]

def execute_prompting(model: str, account: str, ask_type: str, topics: list[str], additional_topics: list[str], tones: list[str], text_len: Literal["short", "medium", "long", ""], headline: str|None, num_outputs: int, model_temperature: float = 0.8, use_bio: bool = True, max_tokens: int = 4096, topic_weight: float = 4, tone_weight: float = 1, client_weight: float = 6, ask_weight: float = 2, text_len_weight: float = 3) -> tuple[str, list[str], str]:
  score_threshold = 0.5 # Document Similarity Score Acceptance Threshold
  doc_pool_size = 10 # Document Pool Size
  num_examples = 10 # Number of Documents to Use as Examples
  assert_always(num_examples <= doc_pool_size, "You can't ask to provide more examples than there are documents in the pool! Try again with a different value.")
  output_table_name = "models.lovelytics.gold_text_outputs" # Text Output Table Name
  ref_tag_name = "models.lovelytics.ref_tags" # Tags Table Name
  primary_key = "PROJECT_NAME" # Index Table Primary Key Name
  client = account # we never use this variable, but client is considered a synonym for account currently
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

  T = TypeVar('T') # Could: Changed in version 3.12: Syntactic support for generics is new in Python 3.12.
  def powerset(l: list[T], start: int = 0) -> list[tuple[T, ...]]:
    """powerset([1,2,3]) → () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    Used to generate powersets of filters."""
    return [x for r in range(start, len(l)+1) for x in combinations(l, r)]

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
  topic_sets = [("topics", x, topic_weight * len(x)) for x in powerset(sorted(topics), start=min(1, len(topics)))]
  tone_sets = [("tones", "(, .*){1,}".join(x), tone_weight * len(x)) for x in powerset(sorted(tones), start=min(1, len(tones)))]
  combos_set: set[Any] = set() # This isn't a great type annotation, but who knows what this is supposed to be.
  # Iterate through each pairing of topics and tones
  for tp in topic_sets:
    for to in tone_sets:
      # Generate every combination between client, ask type, text length, topic, and tone
      # This means that for each topic set and tone set, we're generating every possible combination between those and the client, ask, and length
      temp_arr: list[tuple[str, str|tuple[str, ...], float]] = [("client", account, client_weight), ("ask", ask_type, ask_weight), ("text_len", text_len, text_len_weight)]
      # But only add the topics and tones if they exist i.e. are not an empty string
      if tp[-1] != 0:
        temp_arr.append(tp)
      if to[-1] != 0:
        temp_arr.append(to)
      # Then update the set of filter combinations. A set is used to remove any duplicate filter combinations
      # Note that each filter tag (e.g. client, a topic set) has it's own weight value that dictate the filter's importance
      # Higher weight filters will be used first
      # When the sets of all filters are generated, their combined weight is summed together using the reduce function
      combos_set.update( (x, reduce(lambda a, b: a+b[2], x, 0.0))  if len(x) != 0 else (x, 0) for x in powerset(temp_arr) )
  # Then, the filters are sorted by their weight in descending order
  # So higher weight filter combinations are first in the array which means any documents with those filters will be considered first
  combos = [{y[0]: y[1] for y in x[0]} for x in sorted(combos_set, key=lambda a: a[1], reverse=True)] #a list of dictionaries
  # TODO: write example of a combo here

  ### Find as Many Relevant Documents as Possible ###

  @st.cache_data(show_spinner=False)
  def read_output_table() -> list[Row]:
    return sql_call(f"SELECT * from {output_table_name}")

  text_rows = read_output_table() # Keep in mind that row name-indexing is case-sensitive!
  # results_found is a set of every primary key we've search so far
  # This is to prevent duplicate documents/texts from showing up
  results_found = set()
  # reference_texts will be a list of dictionaries containing example user prompts and assistant responses (i.e. the text messages). Also, scores (a number, represented numerically).
  ReferenceTextElement = TypedDict('ReferenceTextElement', {'prompt': str, 'text': str, 'score': float})
  reference_texts : list[ReferenceTextElement] = []
  # Setup Vector Search Client that we will use in the loop.
  vsc = VectorSearchClient( personal_access_token=st.secrets["DATABRICKS_TOKEN"], workspace_url=st.secrets['DATABRICKS_HOST'], disable_notice=True )
  text_index = vsc.get_index(endpoint_name="rag_llm_vector", index_name="models.lovelytics.gold_text_outputs_index")
  # Get a list of all existing tagged topics #COULD: cache. but probably will refactor instead
  topic_tags = set(x["Tag_Name"] for x in sql_call(f"SELECT Tag_Name FROM {ref_tag_name} WHERE Tag_Type = 'Topic'") )
  for c in combos:
    if "topics" not in c: #TODO: Perhaps one could replace all this regex with several sql CONTAINS statements some day?
        topic_regex = ""
        text_regex = ""
    else:
        tagged_topics = []
        new_topics = []
        for t in c["topics"]:
            if t in topic_tags:
                tagged_topics.append(t)
            else:
                new_topics.append(t)
        # Join together the topics that have been tagged using the same pattern the tones were joined together with
        # For any new topics (i.e. topics that haven't been tagged) join them together using a new pattern
        # (?is)^(?=.*\bTOPIC_X\b)(?=.*\bTOPIC_Y\b).*$
        # To breakdown the regex
        #   (?is)   - Perform case insensitive search and have the . pattern match newlines as well
        #   ^       - At the start of a string
        #   (?=)    - Positive lookahead. Which basically means look forward for a match
        #   .*      - Match any character 0 or more times
        #   \b      - Word boundary
        #   TOPIC_X - The word/phrase we're looking for. In this case it's a placeholder example for the actual topics we want and there could be any number of them
        #   $       - The end of a string
        # To sum up, the regex above says perform a case insensitive search across multiple lines from start to end of a string looking for the topics specified in the forward lookaheads in any order.
        # The key benefit of this is that the words/phrases being looked for can come in any order due to how lookaheads function. So TOPIC_X can come before or after TOPIC_Y in the string and the regex will match either way
        topic_regex = "(, .*){1,}".join(tagged_topics)
        if len(new_topics) != 0:
            text_regex = "(?is)^" + "".join(f"(?=.*\\b{x}\\b)" for x in new_topics) + ".*$"
        else:
            text_regex = ""
    if "tones" not in c:
        tone_regex = ""
    else:
        tone_regex = c["tones"]
    results = [
      (row[primary_key], row["Final_Text"]) for row in text_rows if # Only apply filters if they are present in the current filter combination.
        (row[primary_key] not in results_found                              )  and
        ("topics"   not in c    or    re.search(topic_regex, row["Topics"]) )  and
        ("tones"    not in c    or    re.search(tone_regex, row["Tones"])   )  and
        (not text_regex         or re.search(text_regex, row["Final_Text"]) )  and
        ("client"   not in c    or    c["client"] == row["Client_Name"]     )  and
        ("ask"      not in c    or    c["ask"] == row["Ask_Type"]           )  and
        ("text_len" not in c    or    c["text_len"] == row["Text_Length"]   )
    ]
    # If no results were found, move onto the next filter combination. Otherwise, continue the process of considering these candidate results.
    if not results:
      continue
    results_found.update([x for x, _ in results]) # add the found primary key values to the results_found set
    search_results = []
    lowest_score = score_threshold
    batch_bounds = [x for x in range(0, len(results), doc_pool_size)] + [len(results)]
    start = batch_bounds[0]
    # Perform a similarity search using the target_prompt defined beforehand. Filter for only the results we found earlier in this current iteration.
    try: # In case something goes wrong, we have FAISS as a backup.
      # assert for_testing_purposes_dont_use_dbx_vcs #uncomment to enable this test
      for end in batch_bounds[1:]:
        sim_search = text_index.similarity_search(
          num_results=doc_pool_size, # This must be at most about 2**13 (8192) I have no idea what the actual max is
          columns=["Final_Text"],
          filters={primary_key: [x for x, _ in results[start:end]]}, # The filter statement can only provide at most 1024 items
          query_text=target_prompt
        )
        # Add results returned by the similarity search to the search_results list only if their similarity score is greater than or equal to the lowest similarity score we've stored. We only keep the top doc_pool_size number of documents for a single combination
        if sim_search["result"]["row_count"] != 0:
          search_results.extend({"prompt": "Please write me a" + x[0].split(":\n\n", 1)[0][1:], "text": x[0].split(":\n\n", 1)[1], "score": x[-1]} for x in sim_search["result"]["data_array"] if x[-1] >= lowest_score)
          search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)[:doc_pool_size]
          lowest_score = search_results[-1]["score"] if len(search_results) == doc_pool_size else lowest_score
        start = end
      # Then add all results sorted by score descending to the reference_texts list
      reference_texts.extend(search_results)
    except:
      search_results = []
      lowest_score = score_threshold
      start = batch_bounds[0]
      # embeddings = DatabricksEmbeddings(target_uri="https://c996c2e15417489d87ab0db3f1cc6fc0.serving.cloud.databricks.com/8188181812650195/serving-endpoints/gte_small_embeddings/invocations", endpoint="gte_small_embeddings") #TODO: probably bad to do this each time. Maybe it's fine though. This is only a backup, anyway. #doesn't work
      #maybe this is a model?
      #vsc = VectorSearchClient( personal_access_token=st.secrets["DATABRICKS_TOKEN"], workspace_url=st.secrets['DATABRICKS_HOST'], disable_notice=True )
      #text_index = vsc.get_index(endpoint_name="rag_llm_vector", index_name="models.lovelytics.gold_text_outputs_index")
      embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L12-v2") #TODO: probably bad to do this each time. Maybe it's fine though. This is only a backup, anyway.
      # Using the from_texts instantiation so it automatically creates a Docstore for us. Need to provide at least one text/document, so we're providing a dummy value that will be immediately removed
      faiss_vs = FAISS.from_texts(["TEMP_REMOVE"], embeddings, ids=["TEMP_REMOVE"])
      faiss_vs.delete(ids=["TEMP_REMOVE"])
      for end in batch_bounds[1:]:
        added_ids = faiss_vs.add_texts(texts=[y for _, y in results[start:end]])
        sim_search = [(x[0].page_content, x[1]) for x in faiss_vs.similarity_search_with_relevance_scores(query=target_prompt, k=doc_pool_size, score_threshold=lowest_score)]
        if sim_search:
          search_results.extend({"prompt": "Please write me a" + x.split(":\n\n", 1)[0][1:], "text": x.split(":\n\n", 1)[1], "score": y} for x, y in sim_search)
          search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)[:doc_pool_size]
          lowest_score = search_results[-1]["score"] if len(search_results) == doc_pool_size else lowest_score
        # We delete the texts we were looking at for one reason
        # The FAISS vector search client/collection is being instantiated and saved in memory. Unlike the Databricks vector search which is searching through
        # and querying texts that are stored in a table in Databricks
        # This means that documents added to the collection persist in memory, so I'm deleting records we've already looked at to preserve memory
        faiss_vs.delete(ids=added_ids)
        start = end
      reference_texts.extend(search_results)
      # Note: We could persist all documents added to the FAISS collection with minimal changes. Primarily, we'd need to add a few lines of code to make sure we don't return any texts we've already found when we do the similarity search
      # We'd need to add metadatas information to the add_texts function call. Then we add a filter to the similarity_search_with_relevance_scores function call
      # The last change would be to remove the delete function call
      # The exact code we would use is this
      # added_ids = faiss_vs.add_texts(texts=[y for _, y in results],
      #                                metadatas=[{primary_key: x} for x, _ in results]
      #                                )
      # sim_search = [(x[0].page_content, x[1]) for x in
      #               faiss_vs.similarity_search_with_relevance_scores(query=target_prompt, k=num_searches,
      #                                                                score_threshold=score_threshold,
      #                                                                filter={primary_key: {"$in": [x for x, _ in results]}})]

    # If we've found at least the number of desired documents, exit the loop and take the first doc_pool_size number of texts. The beginning of the reference_texts array will contain the texts that match the most important filters and the highest similarity scores.
    if len(reference_texts) >= doc_pool_size:
      reference_texts = reference_texts[:doc_pool_size]
      break

  ### Query Endpoints ###

  ##### INSERT PROMPT HERE #####
  # Llama-3 Prompt Styling
  # Base beginning structure of the RAG prompt
  rag_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"

  # Define the system prompt
  sys_prompt = """You are an expert copywriter who specializes in writing text messages for conservative political candidates in the United States of America. Make sure all texts are in English. Try to grab the reader's attention in the first line. Do not start your message like an email. Make sure to have an explicit call to action. Do not make up facts or statistics. Do not use emojis or hashtags in your messages. Do not copy previously written text messages in content or structure. Make sure each written text message is unique. Write the exact number of text messages asked for."""

  if use_bio and account:
    sys_prompt += f""" Here is important biographical information about the conservative candidate you are writing for: {load_bio(account)}"""

  combined_dict: dict[str, str|float] = {}  # combined_dict stores all of the string format variables used in the prompt and their values
  combined_dict["system_prompt"] = sys_prompt

  # Then for every example document, we add the corresponding assistant and user lines
  # Triple brackets are used so the actual key name in the ms_prompts and ms_texts dictionaries can be inserted dynamically while also keeping the curly braces in the final string
  # So for example, if k = "apples" f"I like to eat {{{k}}}" would return the string "I like to eat {apples}"
  num_exes = min(num_examples, len(reference_texts))
  multishot_items = {}
  base_chat_history = []
  for i in range(num_exes):
      k = f"example_{i + 1}_p"
      multishot_items[k] = ""
      ok = f"example_{i + 1}_t"
      multishot_items[ok] = ""
      base_chat_history.append(f"""<|start_header_id|>user<|end_header_id|>{{{k}}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>{{{ok}}}<|eot_id|>""")
  rag_prompt += "{chat_history}"

  # Add in the final component of the RAG prompt where we pass in the prompt/question we want to send to the model
  rag_prompt += "<|start_header_id|>user<|end_header_id|>\n\n{question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
  # Combine all of the dictionaries with the string format keys and values for langchain parameter passing usage
  # combined_dict = combined_dict | ms_prompts | ms_texts
  combined_dict["chat_history"] = ""

  # Create the question prompt and add it to the combined_dict dictionary
  question_prompt = f"Please write me {num2words(num_outputs)} {text_len} {ask_type} text messages for {account}" if text_len != "long" else f"Please write me a {text_len} {ask_type} text message for {account}"
  # Add instructions on how long or short a text should be depending on the text length we want the model to generate
  # Add specificity of specific ask type of the text message too
  # Try to make the model understand that the outputs we specifically are asking for should be this length
  question_prompt += {
    "": "",
    "short": " that each use about 250 characters",
    "medium": " that each use about 300 characters",
    "long": " that uses at least 400 characters"
  }[text_len]
  if topics:
    question_prompt += f" about {topics}"
  if tones:
    question_prompt += f" written with an emphasis on {tones}"
  if headline:
    sys_prompt += f""" Here is/are news headline(s) you should reference in your text messages: {headline}"""

  combined_dict["question"] = question_prompt
  ##### END PROMPT INSERTION #####
  # print(rag_prompt)

  # Create the prompt template using langchain's PromptTemplate
  # Tell it that the input variables it should expect is everything in our combined_dict dictionary
  prompt = PromptTemplate(
    input_variables=list(combined_dict.keys()),
    template=rag_prompt
  )

  # Note: The Llama-3 model has a limit of 8192 tokens for its input and output combined. e.g. if our input is 8000 tokens, then we can only have 192 tokens for the output. However, we don't handle that eventuality; the code I'm porting just gives basically an error message, which will already happen.

  # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then the following line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)
  chat_model = ChatDatabricks(endpoint=model, max_tokens=max_tokens, temperature=model_temperature)

  # Assemble the LLM chain, which makes it easier to invoke the model and parse its outputs. This uses langchain's own pipe syntax to organize multiple components into a "pipe".
  model_chain = ( prompt | chat_model | StrOutputParser() )
  if text_len != "long":
    # Randomize the order of the example texts.
    texts_to_use = random.sample(reference_texts, k=num_exes)
    # We reinsert and separate the found documents into two separate dictionaries
    # This makes it easier to assemble the RAG prompt and pass them as string format variables to langchain
    for num, content in enumerate(texts_to_use):
        multishot_items[f"example_{num + 1}_p"] = content["prompt"]
        multishot_items[f"example_{num + 1}_t"] = content["text"]
    combined_dict["chat_history"] = "".join(base_chat_history).format(**multishot_items)
    filled_in_prompt = (prompt.format(**combined_dict))
    # print(filled_in_prompt)
    single_output = model_chain.invoke(combined_dict)
  else:
      single_output = ""
      for i in range(num_outputs):
        texts_to_use = random.sample(reference_texts, k=num_exes)
        for num, content in enumerate(texts_to_use):
            multishot_items[f"example_{num + 1}_p"] = content["prompt"]
            multishot_items[f"example_{num + 1}_t"] = content["text"]
        combined_dict["chat_history"] = "".join(base_chat_history).format(**multishot_items)
        filled_in_prompt = (prompt.format(**combined_dict))
        inv_res = model_chain.invoke(combined_dict)
        single_output += f"{i + 1}. " + inv_res + "\n"
  entire_prompt = str(combined_dict)
  question = str(combined_dict["question"]) #the str call here is purely to help the typechecker.
  # Output validation and conformance. For example, check if English by using ascii as proxy.
  def dequote(s: str) -> str:
    """If s is a string that starts and ends with quotation marks, but contains no other quotation marks, return it without those quotations marks. Return anything else untouched."""
    return s[1:-1] if ( len(s)>=2 and s[0] == s[-1] == '"' and '"' not in s[1:-1] ) else s
  def behead(s: str) -> str:
    """Strip off annoying LLM numbering often found at the beginning of a response. Returns anything else untouched."""
    return re.sub(r"^\s*(?:Message )*\d*\s*[.:]*\s*", "", s)
  def is_natter(x: str) -> bool:
    """Detect if a string is likely random natter often produced by LLMs, based on how it starts."""
    return x.startswith("Here ") or x.startswith("Sure") or x.startswith("OK")
  outputs = [ x for o in single_output.split('\n') for x in [dequote(behead(dequote(o))).strip()] if x and x.isascii() and not is_natter(x) ]
  return question, outputs, entire_prompt

def main() -> None:

  st.session_state['human-facing_prompt'] = '' #to clear the prompt between prompts. could definitely be placed in a better spot.
  if not st.session_state.get('email'): #this line is of dubious usefulness. It's supposed to let you run cicero_prompter.py locally and stand-alone without cicero.py, however.
    st.session_state["email"] = str(st.experimental_user["email"]) #this str call also accounts for if the user email is None.
  if 'use_count' not in st.session_state:
    st.session_state['use_count'] = count_from_activity_log_times_used_today(st.session_state["email"])
  use_count_limit = 100 #arbitrary but reasonable choice of limit
  if st.session_state['email'] in ["abrady@targetedvictory.com", "thall@targetedvictory.com", "test@example.com"]: # Give certain users nigh-unlimited uses.
    use_count_limit = 100_000_000
  if st.session_state['use_count'] >= use_count_limit:
    st.write(f"You cannot use this service more than {use_count_limit} times a day, and you have reached that limit. Please contact the team if this is in error or if you wish to expand the limit.")
    exit_error(52) # When a user hits the limit it completely locks them out of the ui using an error message. This wasn't a requirement, but it seems fine.

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

  # Because parts of it update when other parts of it are changed, this news dialogue can't go within the st.form (which precludes that on purpose, as a feature to improve performance)
  #Restyle the news headline heading to Helvetica Neue. (nb: I think it's crazy to want to change from streamlit default sans-serif font to helvetica, because every font of that general style looks pretty much identical; but the boss gets what the boss wants, within possibility.)
  #st.markdown(""" <style> .size8 {color: yellow; font-family: Times} </style> """, unsafe_allow_html=True) # This line shows we could do it by size instead, if we wanted.
  st.markdown(""" <style> @import url('https://fonts.cdnfonts.com/css/helvetica-neue-55'); .textsf {font-family: Helvetica Neue !important; font-size: 18px !important;}  </style> """, unsafe_allow_html=True) # Thanks to this random for hosting this font for us, I guess! https://www.cdnfonts.com/helvetica-neue-55.font
  # TODO: make the label in this expander match, or just more closely match, the size of the "History of Replies"
  with st.expander(r"$\textsf{\Large NEWS HEADLINES}$"): # I tried to remove the LaTeX, but then the font size wouldn't change without it
    exact_match_query = st.text_input("Headline Search  \n*Returns headlines containing the search terms. Hit Enter to filter the headlines.*", key="exact_match_query")
    overdrive: bool = st.checkbox("Only search headlines from the last 3 days.", key="overdrive")
    h: list[str] = load_headlines(get_all=False) if not overdrive else load_headlines(get_all=False, past_days=3)
    if exact_match_query:
      h = only_those_strings_of_the_list_that_contain_the_given_substring_case_insensitively(h, exact_match_query)
    headline = st.selectbox("If a headline is selected here, it will be added to your prompt below.", list(h), key="headline")

  st.text("") # Just for vertical spacing.

  with st.form('query_builder'):
    with st.sidebar:
      if st.session_state["developer_mode"]:
        topic_weight: float = st.slider("Topic Weight", min_value=0.0, max_value=10.0, key="topic_weight")
        tone_weight: float = st.slider("Tone Weight", min_value=0.0, max_value=10.0, key="tone_weight")
        client_weight: float = st.slider("Client Weight", min_value=0.0, max_value=10.0, key="client_weight")
        ask_weight: float = st.slider("Ask Weight", min_value=0.0, max_value=10.0, key="ask_weight")
        text_len_weight: float = st.slider("Text Len Weight", min_value=0.0, max_value=10.0, key="text_len_weight")
      else:
        topic_weight = 4
        tone_weight = 1
        client_weight = 6
        ask_weight = 2
        text_len_weight = 3

    model_name = str( st.selectbox("Model (required)", ["Llama-3-70b-Instruct", "DBRX-Instruct", "Mixtral-8x7b-Instruct"], key="model") ) if st.session_state["developer_mode"] else "Llama-3-70b-Instruct"
    model = {
      "Llama-3-70b-Instruct":"databricks-meta-llama-3-70b-instruct",
      "DBRX-Instruct": "databricks-dbrx-instruct",
      "Mixtral-8x7b-Instruct": "databricks-mixtral-8x7b-instruct"
    }[model_name]
    account = st.selectbox("Account (required)", list(account_names), key="account")
    ask_type = str( st.selectbox("Ask Type", ['Hard Ask', 'Medium Ask', 'Soft Ask', 'Soft Ask Petition', 'Soft Ask Poll', 'Soft Ask Survey'], key="ask_type") ).lower() #STREAMLIT-BUG-WORKAROUND: every time I, eg, wrap selectbox in str I think this is technically working around a bug in streamlit, although it's a typing bug and might be impossible for them to fix: https://github.com/streamlit/streamlit/issues/8717
    topics = st.multiselect("Topics", sorted([t for t, d in topics_big.items() if d["show in prompter?"]]), key="topics" )
    topics = external_topic_names_to_internal_topic_names_list_mapping(topics)
    lengths_selectable: list[Literal['short', 'medium', 'long']] = ['short', 'medium', 'long']
    length_select = st.selectbox("Length", lengths_selectable, key='lengths', format_func=lambda x: f"{x.capitalize()} {('(<160 characters)' if x == 'short' else '(161-399 characters)' if x == 'medium' else '(400+ characters)')}")
    if length_select is None:
      print("length selection was None... that's not supposed to happen...")
      exit_error(69)
    additional_topics = [x.strip().lower() for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
    tones = list_lower( st.multiselect("Tones", ['Agency', 'Apologetic', 'Candid', 'Exclusivity', 'Fiesty', 'Grateful', 'Not Asking For Money', 'Pleading', 'Quick Request', 'Secretive', 'Time Sensitive', 'Urgency'], key="tone") ) #TODO: , 'Swear Jar' will probably be in here some day, but we don't have "we need more swear jar data to make this tone better"
    num_outputs: int = st.selectbox("\# Outputs", [1,3,5,10], key='num_outputs')
    temperature: float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") if st.session_state["developer_mode"] else 0.7
    generate_button = st.form_submit_button("Submit", type="primary")

  #Composition and sending a request:
  did_a_query = False
  if generate_button:
    if not account:
      st.warning("***No Account is selected, so I can't send the request!***")
    elif not model:
      st.warning("***No Model is selected, so I can't send the request! (If you have no ability to select a Model and get this error, please contact the Optimization team.***")
    else:
      did_a_query = True
      cicero_rag_only.reset_chat()
      st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
      use_bio=("Bio" in topics and account in bios)
      max_tokens = 4096
      promptsent, st.session_state['outputs'], st.session_state['entire_prompt'] = execute_prompting(model, account, ask_type, topics, additional_topics, tones, length_select, headline, num_outputs, temperature, use_bio, max_tokens, topic_weight, tone_weight, client_weight, ask_weight, text_len_weight)
      if len(st.session_state['outputs']) != num_outputs:
        st.info("CICERO has detected that the number of outputs may be wrong.")
      if 'history' not in st.session_state:
        st.session_state['history'] = []
      st.session_state['history'] += st.session_state['outputs']
      st.session_state['character_counts_caption'] = "Character counts: "+str([len(o) for o in st.session_state['outputs']])

  # The idea is for these output elements to persist after one query button, until overwritten by the results of the next query.

  if 'entire_prompt' in st.session_state and st.session_state.get("developer_mode"):
    with st.expander("Developer Mode Message: the prompt passed to the model"):
      st.caption(st.session_state['entire_prompt'].replace("$", r"\$"))

  st.error("WARNING! Outputs have not been fact checked. CICERO is not responsible for inaccuracies in deployed copy. Please check all *names*, *places*, *counts*, *times*, *events*, and *titles* (esp. military titles) for accuracy.  \nAll numbers included in outputs are suggestions only and should be updated. They are NOT analytically optimized to increase conversions (yet) and are based solely on frequency in past copy.", icon="⚠️")
  if 'outputs' in st.session_state:
    key_collision_preventer = 1
    for output in st.session_state['outputs']:
      col1, col2 = st.columns([.95, .05])
      with col1:
        st.write( output.replace("$", r"\$") ) #this prevents us from entering math mode when we ask about money.
      with col2:
        if st.button("⚡", key="⚡"+str(key_collision_preventer), help="Edit with Cicero"):
          default_reply = "Here is a conservative fundraising text: [" + output + "] Analyze the quality of the text based off of these five fundraising elements: the Hook, Urgency, Agency, Stakes, and the Call to Action (CTA). Do not assign scores to the elements. It's possible one or more of these elements is missing from the text provided. If so, please point that out. Then, directly ask the user what assistance they need with the text. Additionally, mention that you can also help edit the text to be shorter or longer, and convert the text into an email."
          st.session_state['cicero_ai']=default_reply
          st.session_state['display_only_this_at_first_blush'] = "« "+output+" »"
        key_collision_preventer += 1
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
    # promptsent is only illustrative. But maybe that's enough. Maybe we should be using a different prompt?
    write_to_activity_log_table( datetime=str(datetime.now(z("US/Eastern"))), useremail=st.session_state['email'], promptsent=promptsent, responsegiven=json.dumps(st.session_state['outputs']), modelparams=str({"max_tokens": max_tokens, "temperature": temperature}), modelname=model_name, modelurl=model )

  # st.components.v1.html('<!--<script>//you can include arbitrary html and javascript this way</script>-->') #or, use st.markdown, if you want arbitrary html but javascript isn't needed.

if __name__ == "__main__": main()
