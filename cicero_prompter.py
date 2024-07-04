#!/usr/bin/env -S streamlit run

"""Post hoc ergo prompter hoc?"""

import streamlit as st
import pandas as pd
import json
from typing import Any, Literal, TypedDict, TypeVar, get_args
from cicero_shared import assert_always, consul_show, ensure_existence_of_activity_log, exit_error, get_base_url, load_account_names, sql_call, sql_call_cacheless, topics_big, typesafe_selectbox
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
import jellyfish

from databricks.vector_search.client import VectorSearchClient

def disable_submit_button_til_complete() -> None:
  st.session_state["submit_button_disabled"] = True

def external_topic_names_to_internal_topic_names_list_mapping(external_topic_names: list[str]) -> list[str]:
  return [topics_big[e]["internal name"].replace("_", " ").lower() for e in external_topic_names]

@st.cache_data(show_spinner=False) #STREAMLIT-BUG-WORKAROUND: Necessity demands we do a manual cache of this function's result anyway in the one place we call it, but (for some reason) it seems like our deployed environment is messed up in some way I cannot locally replicate, which causes it to run this function once every five minutes. So, we cache it as well, to prevent waking up our server and costing us money.
def count_from_activity_log_times_used_today(user_email: str) -> int:
  """Count the number of times the user has used the prompter.
  This goes by whatever the default timezone is because we don't expect the exact boundary to matter much."""
  keyword_arguments = locals()
  ensure_existence_of_activity_log()
  return int( sql_call("SELECT COUNT(*) FROM cicero.default.activity_log WHERE user_email = :user_email AND DATE(timestamp) == current_date() AND prompter_or_chatbot = 'prompter'", keyword_arguments)[0][0] )

@st.cache_data(show_spinner=False)
def load_bios() -> dict[str, str]:
  return {row["candidate"]:row["bio"] for row in sql_call("SELECT candidate, bio FROM cicero.default.ref_bios")}

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

Short_Model_Name = Literal["DBRX-Instruct", "Llama-3-70b-Instruct", "Mixtral-8x7b-Instruct"] #See https://stackoverflow.com/questions/64522040/dynamically-create-literal-alias-from-list-of-valid-values for an explanation of what we're doing here. #COULD: one day use the `type` keyword here for defining this type. But it's not supported yet.
short_model_names: tuple[Short_Model_Name, ...] = get_args(Short_Model_Name)
Long_Model_Name = Literal["databricks-dbrx-instruct", "databricks-meta-llama-3-70b-instruct", "databricks-mixtral-8x7b-instruct"] #IMPORTANT: the cleanest way of implementing this REQUIRES that short_model_names and long_model_names correspond via index. This is an unfortunate burden, but it's better than the other ways I tried...
long_model_names: tuple[Long_Model_Name, ...] = get_args(Long_Model_Name)
#TODO: "valid values" dict? And then use that for "I'm feeling lucky"?
Selectable_Length = Literal['short', 'medium', 'long']
Ask_Type = Literal['Hard Ask', 'Medium Ask', 'Soft Ask', 'Soft Ask Petition', 'Soft Ask Poll', 'Soft Ask Survey']
Tone = Literal['Agency', 'Apologetic', 'Candid', 'Exclusivity', 'Fiesty', 'Grateful', 'Not Asking For Money', 'Pleading', 'Quick Request', 'Secretive', 'Time Sensitive', 'Urgency'] #Could: , 'Swear Jar' will probably be in here some day, but we don't have "we need more swear jar data to make this tone better"
Num_Outputs = Literal[1,3,5,10]

#Make default state, and other presets, so we can manage presets and resets.
# Ah, finally, I've figured out how you're actually supposed to do it: https://docs.streamlit.io/library/advanced-features/button-behavior-and-examples#option-1-use-a-key-for-the-button-and-put-the-logic-before-the-widget
#IMPORTANT: these field names are the same field names as what we eventually submit. HOWEVER, these are just the default values, and are only used for that, and are stored in this particular data structure, and do not overwrite the other variables of the same names that represent the returned values.
class PresetsPayload(TypedDict):
  temperature: float
  model_name: Short_Model_Name
  account: str | None
  ask_type: Ask_Type
  tones: list[Tone]
  topics: list[str]
  additional_topics: str
  exact_match_query: str
  headline: str | None
  overdrive: bool
  num_outputs: Num_Outputs
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
    "tones" : [],
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

def short_model_name_to_long_model_name(short_model_name: Short_Model_Name) -> Long_Model_Name:
  return long_model_names[short_model_names.index(short_model_name)]

ReferenceTextElement = TypedDict('ReferenceTextElement', {'prompt': str, 'text': str, 'score': float})

def sample_dissimilar_texts(population: list[ReferenceTextElement], k: int, max_similarity: float=0.8) -> list[ReferenceTextElement]: #TODO: it seems that this function is only called when text is Long, which is probably not right? #TODO: it takes line 20 seconds for this code to run, it seems, and this code is called {# Outputs} times (again, only on Long) and furthermore I suspect this code can be replaced with about 5 lines, so maybe that refactor will also speed things up.
  consul_show(f"sample_dissimilar_texts's {max_similarity=}")
  final_arr: list[ReferenceTextElement] = []
  not_selected = []
  randomized_arr = random.sample(population, k=len(population))
  for num, item in enumerate(randomized_arr):
    valid = True
    for selected in final_arr:
      distance = jellyfish.damerau_levenshtein_distance(item["text"], selected["text"])
      similarity = 1 - (distance / (len(item["text"]) + len(selected["text"])))
      if similarity > max_similarity:
        valid = False
        break
    if valid:
      final_arr.append(item)
    else:
      not_selected.append((item, 0.0))
    if len(final_arr) == k:
      not_selected.extend((alpha, 0.0) for alpha in randomized_arr[num+1:])
      break
  while len(final_arr) < (k - 5):
    if not not_selected:
      break
    scored_unselected = []
    for item, _ in not_selected:
      score = 0.0
      for selected in final_arr:
        distance = jellyfish.damerau_levenshtein_distance(item["text"], selected["text"])
        score += 1 - (distance / (len(item["text"]) + len(selected["text"])))
      average_score = score / len(final_arr)
      scored_unselected.append((item, average_score))
    scored_unselected = sorted(scored_unselected, key=lambda x: x[1], reverse=False)
    final_arr.append(scored_unselected.pop(0)[0])
    not_selected = scored_unselected
  return random.sample(final_arr, k=len(final_arr))

def execute_prompting(model: Long_Model_Name, account: str, ask_type: Ask_Type, topics: list[str], additional_topics: list[str], tones: list[Tone], text_len: Selectable_Length, headline: str|None, num_outputs: Num_Outputs, model_temperature: float = 0.8, bio: str|None = None, max_tokens: int = 4096, topic_weight: float = 4, tone_weight: float = 1, client_weight: float = 6, ask_weight: float = 2, text_len_weight: float = 3, doc_pool_size: int = 30, num_examples: int = 10) -> tuple[str, list[str], str, str]:
  score_threshold = 0.5 # Document Similarity Score Acceptance Threshold
  consul_show(f"{score_threshold=}, {doc_pool_size=}, {num_examples=}")
  assert_always(num_examples <= doc_pool_size, "You can't ask to provide more examples than there are documents in the pool! Try again with a different value.")
  ref_tag_name = "models.lovelytics.ref_tags" # Tags Table Name
  primary_key = "PROJECT_NAME" # Index Table Primary Key Name
  topics += additional_topics
  topics_str = ", ".join(topics)
  tones_str = ", ".join(tones)

  # Create a target prompt that is used during the vector index similarity search to score retrieved texts.
  target_prompt = f"A {text_len} {ask_type} text message from {account}" + f" about {topics_str}"*bool(topics) + f" written with an emphasis on {tones_str}"*bool(tones)

  #### Create All Possible Filter Combinations and Sort By Importance ###

  ### Tag importance from most important to least
  # Topics (Tp)
  # Account/Client Name (C) # /Client is considered a synonym for account currently #TODO: actually we should refactor out the word "client" I guess. Either one of client or account should go. And begone from variable names.
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
  T = TypeVar('T')
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
  # (?i) makes it case-insensitive
  # ^(?=.*\btopic\b)(?=.*\btopic\b).*$ regex for matching
  topic_sets = [("topics", x, topic_weight * len(x)) for x in powerset(sorted(topics), start=min(1, len(topics)))]
  tone_sets = [("tone_regex", "(?i)" + "(, .*){1,}".join(x), tone_weight * len(x)) for x in powerset(sorted(tones), start=min(1, len(tones)))]
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
  print("Finding the documents")
  results_found = set() # results_found is a set of every primary key we've search so far. This is to prevent duplicate documents/texts from showing up.
  reference_texts : list[ReferenceTextElement] = [] # reference_texts will be a list of dictionaries containing example user prompts and assistant responses (i.e. the text messages). Also, scores (a number, represented numerically).
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
      c["topic_regex"] = topic_regex
      c.pop("topics", None)
      c["text_regex"] = text_regex
    #c["results_found"]= list(results_found)
    combo_results = sql_call_cacheless(
      "SELECT project_name, final_text from models.lovelytics.gold_text_outputs where TRUE"+
        # Only apply filters if they are present in the current filter combination...
        ("topic_regex" in c) * " AND topics rlike :topic_regex" +
        ("tone_regex" in c) * " AND tones rlike :tone_regex" +
        ("text_regex" in c) * " AND final_text rlike :text_regex" +
        ("client" in c) * " AND client_name == :client" +
        ("ask" in c) * " AND ask_type == :ask" +
        ("text_len" in c) * " AND text_length == :text_len",
      c
    )
    combo_results = [x for x in combo_results if x[0] not in results_found] #couldn't ever quite get this to work within the sql statement, so here it is.
    # If no results were found, move onto the next filter combination. Otherwise, continue the process of considering these candidate results.
    if not combo_results:
      continue
    results_found.update([x for x, _ in combo_results]) # add the found primary key values to the results_found set
    search_results: list[ReferenceTextElement] = []
    lowest_score = score_threshold
    batch_bounds = list(range(0, len(combo_results), doc_pool_size)) + [len(combo_results)]
    start = batch_bounds[0]
    # Perform a similarity search using the target_prompt defined beforehand. Filter for only the results we found earlier in this current iteration.
    print()
    try: # In case something goes wrong, we have FAISS as a backup. #Ironically, the backup has its own issues. But I guess it's being triggered, because those issues seem to be coming up!
      assert not st.session_state.get("use_backup_similarity_search_library")
      for end in batch_bounds[1:]:
        dbx_search = text_index.similarity_search(
          num_results=doc_pool_size, # This must be at most about 2**13 (8192) I have no idea what the actual max is
          columns=["Final_Text"],
          filters={primary_key: [x for x, _ in combo_results[start:end]]}, # The filter statement can only provide at most 1024 items. Here, I guess, we're using the stride of the doc_pool_size.
          query_text=target_prompt
        )
        # Add results returned by the similarity search to the search_results list only if their similarity score is greater than or equal to the lowest similarity score we've stored. We only keep the top doc_pool_size number of documents for a single combination
        if dbx_search["result"]["row_count"] != 0:
          search_results.extend({"prompt": "Please write me a" + x[0].split(":\n\n", 1)[0][1:], "text": x[0].split(":\n\n", 1)[1], "score": x[-1]} for x in dbx_search["result"]["data_array"] if x[-1] >= lowest_score)
          search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)[:doc_pool_size]
          lowest_score = search_results[-1]["score"] if len(search_results) == doc_pool_size else lowest_score
        start = end
      # Then add all results sorted by score descending to the reference_texts list
      reference_texts.extend(search_results)
    except:
      if st.session_state.get("developer_mode"):
        st.write("developer mode message: error was encountered in the main similarity search library (or perhaps you induced a fake error there for testing purposes) so we are using the backup option")
        print("developer mode message: error was encountered in the main similarity search library (or perhaps you induced a fake error there for testing purposes) so we are using the backup option")
      search_results = []
      lowest_score = 0.0 # This value is a hack. Our original score_threshold value (which we set this variable to the value of) was too high, so we never found any results, so the score_threshold was never updated. (Although, I think it can only ever update up, that's the whole point of updating it in our code later, I guess. So in reality that part of the process was irrelevant and the real problems was that the score_threshold was simply too high.) This is probably because instead of values between 0 and 1, like it's supposed to, the FAISS thing is giving us back all sorts of numbers, some of them negative. And I guess very few of those are >0.5 or whatever the score_threshold is. This caused the code to run approximately forever, eat up enormous amounts of RAM, and then (exceeding the RAM limit) die. I think this method will still exceed the RAM limit and die on Streamlit, even with this fix! (Although sometimes Streamlit seems to allow you to exceed the RAM limit, maybe if you only do it for a second, without crashing you, so we'll see.)
      start = batch_bounds[0]
      # We get many pretty ghastly warnings here, apparently because this "sentence-transformers/all-MiniLM-L12-v2" embedding thing creates some negative-numbered results, which FAISS doesn't like. Or maybe this is a bug in FAISS?
      embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L12-v2") #TODO: probably bad to do this each time. Maybe it's fine though. This is only a backup, anyway.
      # Using the from_texts instantiation so it automatically creates a Docstore for us. Need to provide at least one text/document, so we're providing a dummy value that will be immediately removed
      faiss_vs = FAISS.from_texts(["TEMP_REMOVE"], embeddings, ids=["TEMP_REMOVE"])
      faiss_vs.delete(ids=["TEMP_REMOVE"])
      for end in batch_bounds[1:]:
        added_ids = faiss_vs.add_texts(texts=[y for _, y in combo_results[start:end]])
        faiss_search = [(x[0].page_content, x[1]) for x in faiss_vs.similarity_search_with_relevance_scores(query=target_prompt, k=doc_pool_size, score_threshold=lowest_score)]
        if faiss_search:
          search_results.extend({"prompt": "Please write me a" + x.split(":\n\n", 1)[0][1:], "text": x.split(":\n\n", 1)[1], "score": y} for x, y in faiss_search)
          search_results = sorted(search_results, key=lambda x: x["score"], reverse=True)[:doc_pool_size]
          lowest_score = search_results[-1]["score"] if len(search_results) == doc_pool_size else lowest_score
        # We delete the texts we were looking at for one reason: The FAISS vector search client/collection is being instantiated and saved in memory; unlike the Databricks vector search which is searching through and querying texts that are stored in a table in Databricks. This means that documents added to the collection persist in memory, so I'm deleting records we've already looked at to preserve memory
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
      # faiss_search = [(x[0].page_content, x[1]) for x in
      #               faiss_vs.similarity_search_with_relevance_scores(query=target_prompt, k=num_searches,
      #                                                                score_threshold=score_threshold,
      #                                                                filter={primary_key: {"$in": [x for x, _ in results]}})]

    # If we've found at least the number of desired documents, exit the loop and take the first doc_pool_size number of texts. The beginning of the reference_texts array will contain the texts that match the most important filters and the highest similarity scores.
    if len(reference_texts) >= doc_pool_size:
      reference_texts = reference_texts[:doc_pool_size]
      break

  ### Query Endpoints ###
  print("Query Endpoints")

  ##### INSERT PROMPT HERE #####
  # Llama-3 Prompt Styling
  # Base beginning structure of the RAG prompt
  rag_prompt = "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"

  combined_dict: dict[str, str|float] = {}  # combined_dict stores all of the string format variables used in the prompt and their values
  prompter_system_prompt = """You are an expert copywriter who specializes in writing text messages for conservative political candidates in the United States of America. Make sure all texts are in English. Try to grab the reader's attention in the first line. Do not start your message like an email. Make sure to have an explicit call to action. Do not make up facts or statistics. Do not use emojis or hashtags in your messages. Do not copy previously written text messages in content or structure. Make sure each written text message is unique. Write the exact number of text messages asked for."""
  combined_dict["system_prompt"] = prompter_system_prompt

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
  question_prompt += {
    "short": " that each use about 250 characters",
    "medium": " that each use about 350 characters",
    "long": " that uses at least 400 characters"
  }[text_len]
  question_prompt += bool(topics) * f" about {topics}" + bool(tones) * f" written with an emphasis on {tones}" + bool(bio) * f""" Here is important biographical information about the conservative candidate you are writing for: {bio}""" + bool(headline) * f""" Here is/are news headline(s) you should reference in your text messages: {headline}"""
  combined_dict["question"] = question_prompt
  ##### END PROMPT INSERTION #####
  # print(rag_prompt)

  # Create the prompt template using langchain's PromptTemplate
  # Tell it that the input variables it should expect is everything in our combined_dict dictionary
  prompt = PromptTemplate(
    input_variables=list(combined_dict.keys()),
    template=rag_prompt
  )

  # Note: The Llama-3 model has a limit of 8192 tokens for its input and output combined. e.g. if our input is 8000 tokens, then we can only have 192 tokens for the output. However, we don't handle that eventuality; an error message will just happen I guess.

  chat_model = ChatDatabricks(endpoint=model, max_tokens=max_tokens, temperature=model_temperature) # Keep in mind that unless DATABRICKS_HOST and DATABRICKS_TOKEN are in the environment (streamlit does this with secret value by default), then the following line of code will fail with an extremely cryptic error asking you to run this program with a `setup` command line argument (which won't do anything)

  # Assemble the LLM chain, which makes it easier to invoke the model and parse its outputs. This uses langchain's own pipe syntax to organize multiple components into a "pipe".
  model_chain = ( prompt | chat_model | StrOutputParser() )
  if text_len != "long":
    # Randomize the order of the example texts.
    texts_to_use = random.sample(reference_texts, k=num_exes)
    # We reinsert and separate the found documents into two separate dictionaries
    # This makes it easier to assemble the RAG prompt and pass them as string format variables to langchain
    multishot_items = {}
    for num, content in enumerate(texts_to_use):
        multishot_items[f"example_{num + 1}_p"] = content["prompt"]
        multishot_items[f"example_{num + 1}_t"] = content["text"]
    combined_dict["chat_history"] = "".join(base_chat_history[:len(multishot_items)]).format(**multishot_items)
    single_output = model_chain.invoke(combined_dict)
  else:
    single_output = ""
    for i in range(num_outputs):
      # Use our custom sampling and text selection function to randomly select the texts we'll use as examples
      texts_to_use = sample_dissimilar_texts(reference_texts, k=num_exes) #TODO: this line of code seemingly never runs 
      # Reinstantiate the multishot_items dictionary. This is just in case the sample function we provided returns less items than the chat_history is prepared for
      multishot_items = {}
      for num, content in enumerate(texts_to_use):
        multishot_items[f"example_{num + 1}_p"] = content["prompt"]
        multishot_items[f"example_{num + 1}_t"] = content["text"]
      # Create the chat history text up to the number of texts found from sampling
      combined_dict["chat_history"] = "".join(base_chat_history[:len(multishot_items)]).format(**multishot_items)
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
    """Detect if a string is likely the random natter often produced by LLMs, based on how it starts."""
    msg_pattern = r"\*?\*?Message \d\.?\*?\*?$"
    return x.startswith("Here ") or x.startswith("Here's ") or x.startswith("Sure") or x.startswith("OK") or bool(re.match(msg_pattern, x))
  outputs = [ x for o in single_output.split('\n') for x in [dequote(behead(dequote(o))).strip()] if x and x.isascii() and not is_natter(x) ]
  print("Done with prompting.")
  if num_outputs != len(outputs):
    print(f"!!! CICERO has detected that the number of outputs may be wrong. Desired {num_outputs=}. Observed {len(outputs)=}. Problematic output: {single_output=}. Parsed into {outputs=}")
  return question, outputs, entire_prompt, prompter_system_prompt

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
    headline = st.selectbox("If a headline is selected here, it will be added to your prompt below.", list(h), key="headline") # No typesafe_selectbox here because we actually do want this to possibly be unselected.

  st.text("") # Just for vertical spacing.

  default_sys_prompt: str = "You are a helpful, expert copywriter who specializes in writing fundraising text messages and emails for conservative candidates and causes. Be direct with your responses, and avoid extraneous messages like 'Hello!' and 'I hope this helps!'. These text messages and emails tend to be more punchy and engaging than normal marketing material. Do not mention that you are a helpful, expert copywriter."
  
  with st.form('query_builder'):
    with st.sidebar:
      if st.session_state["developer_mode"]:
        topic_weight: float = st.slider("Topic Weight", min_value=0.0, max_value=10.0, key="topic_weight")
        tone_weight: float = st.slider("Tone Weight", min_value=0.0, max_value=10.0, key="tone_weight")
        client_weight: float = st.slider("Client Weight", min_value=0.0, max_value=10.0, key="client_weight")
        ask_weight: float = st.slider("Ask Weight", min_value=0.0, max_value=10.0, key="ask_weight")
        text_len_weight: float = st.slider("Text Len Weight", min_value=0.0, max_value=10.0, key="text_len_weight")
        st.session_state["the_real_dude_model_name"] = typesafe_selectbox("Model selection for Cicero (the actual, historical man (it's really him))", short_model_names, default="Llama-3-70b-Instruct") #TODO: this is deliberately not in the preset system, because it might get removed later.
        st.session_state["the_real_dude_system_prompt"] = typesafe_selectbox("Model system prompt for Cicero (the actual, historical man (it's really him))", [default_sys_prompt]) #TODO: this is deliberately not in the preset system, because it might get removed later.
        doc_pool_size: int = st.slider("Doc Pool Size", min_value=5, max_value=100, value=30) #TODO: this is deliberately not in the preset system, because it might get removed later.
        num_examples: int = st.slider("Number of Examples", min_value=5, max_value=100, value=10) #TODO: this is deliberately not in the preset system, because it might get removed later.
      else:
        topic_weight = 4
        tone_weight = 1
        client_weight = 6
        ask_weight = 2
        text_len_weight = 3
        st.session_state["the_real_dude_model_name"] = "Llama-3-70b-Instruct"
        st.session_state["the_real_dude_system_prompt"] = default_sys_prompt
        doc_pool_size = 30
        num_examples = 10
    st.session_state["the_real_dude_model"] = short_model_name_to_long_model_name(st.session_state["the_real_dude_model_name"])
    model_name = typesafe_selectbox("Model (required)", short_model_names, default="Llama-3-70b-Instruct", key="model") if st.session_state["developer_mode"] else "Llama-3-70b-Instruct"
    model = short_model_name_to_long_model_name(model_name)
    account = st.selectbox("Account (required)", account_names, key="account") # No typesafe_selectbox here because we actually do want this to possibly be unselected.
    ask_type = typesafe_selectbox("Ask Type", get_args(Ask_Type), key="ask_type").lower()
    topics = st.multiselect("Topics", sorted([t for t, d in topics_big.items() if d["show in prompter?"]]), key="topics" )
    topics = external_topic_names_to_internal_topic_names_list_mapping(topics)
    length_select = typesafe_selectbox("Length", get_args(Selectable_Length), key='lengths', format_func=lambda x: f"{x.capitalize()} ({'<160' if x == 'short' else '161-399' if x == 'medium' else '400+'} characters)")
    additional_topics = [x.strip().lower() for x in st.text_input("Additional Topics (examples: Biden, survey, deadline)", key="additional_topics" ).split(",") if x.strip()] # The list comprehension is to filter out empty strings on split, because otherwise this fails to make a truly empty list in the default case, instead having a list with an empty string in, because split changes its behavior when you give it arguments. Anyway, this also filters out trailing comma edge-cases and such.
    tones = st.multiselect("Tones", get_args(Tone), key="tones")
    num_outputs = typesafe_selectbox(r"\# Outputs", get_args(Num_Outputs), key='num_outputs')
    temperature: float = st.slider("Output Variance:", min_value=0.0, max_value=1.0, key="temperature") if st.session_state["developer_mode"] else 0.7
    buttonhole = st.empty()
    with buttonhole:
      if st.session_state.get("submit_button_disabled"):
        st.form_submit_button("Processing...", type="primary", disabled=True)
      else:
        st.form_submit_button("Submit", type="primary", on_click=disable_submit_button_til_complete)
    if st.session_state.get("developer_mode"):
      st.session_state["use_backup_similarity_search_library"] = typesafe_selectbox("(developer mode option) trigger a fake error in the appropriate place in this run to use backup similarity search library", [False, True])
  if st.session_state.get("developer_mode"):
    if st.button("Developer mode special button for testing: “***I'm feeling (un)lucky***”"):
      st.session_state["submit_button_disabled"] = True
      account = "AAF" #TODO: is there a better testing value? Could I have my own dummy account that just writes nice things about me personally, for example? Or nasty things about Ceasar?

  #Composition and sending a request:
  did_a_query = False
  if st.session_state.get("submit_button_disabled"):
    if not account:
      st.warning("***No Account is selected, so I can't send the request!***")
    elif not model:
      st.warning("***No Model is selected, so I can't send the request! (If you have no ability to select a Model and get this error, please contact the Optimization team.***")
    else:
      did_a_query = True
      cicero_rag_only.reset_chat()
      st.session_state['use_count']+=1 #this is just an optimization for the front-end display of the query count
      bio = bios.get(account) if ("bio" in topics and account in bios) else None
      max_tokens = 4096
      prompt_sent, st.session_state['outputs'], st.session_state['entire_prompt'], prompter_system_prompt = execute_prompting(model, account, ask_type, topics, additional_topics, tones, length_select, headline, num_outputs, temperature, bio, max_tokens, topic_weight, tone_weight, client_weight, ask_weight, text_len_weight, doc_pool_size, num_examples)
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
          cicero_rag_only.reset_chat()
          cicero_rag_only.grow_chat(streamlit_key_suffix="_prompter", alternate_content=output)
        key_collision_preventer += 1
    st.caption(st.session_state.get('character_counts_caption'))
    if st.session_state.get('messages'):
      cicero_rag_only.display_chat(streamlit_key_suffix="_prompter")
  st.error('**REMINDER!** Please tag all projects with "**optimization**" in the LABELS field in Salesforce.')

  with st.sidebar: #The history display includes a result of the logic of the script, that has to be updated in the middle of the script where the button press is (when the button is in fact pressed), so the code to display it has to be after all the logic of the script or else it will lag behind the actual state of the history by one time step.
    st.header("History of replies:")
    if 'history' not in st.session_state: st.session_state['history'] = []
    st.dataframe( pd.DataFrame(reversed( st.session_state['history'] ),columns=(["Outputs"])), hide_index=True, use_container_width=True)

  login_activity_counter_container.write(
    f"""You are logged in as {st.session_state['email']}{" (internally, "+str(st.experimental_user['email'])+")" if st.session_state["developer_mode"] else ""}. You have prompted {st.session_state['use_count']} time{'s' if st.session_state['use_count'] != 1 else ''} today, out of a limit of {use_count_limit}. {"You are in developer mode." if st.session_state["developer_mode"] else ""}"""
  )

  st.session_state["submit_button_disabled"] = False
  buttonhole.form_submit_button("Submit ", type="primary", on_click=disable_submit_button_til_complete) # After everything, re-enable the submit button. Note that the space at the end of Submit here doesn't show up in the UI; it's just a convenient way to make the key of this replacement button not identical to the original button (which would cause an error). I didn't even bother to file an issue about this because who cares.
  # Activity logging takes a bit, so I've put it last to preserve immediate-feeling performance and responses for the user making a query.
  if did_a_query:
    # prompt_sent is only illustrative. But maybe that's enough. Maybe we should be using a different prompt?
    st.session_state["activity_log_payload"] = {"user_email": st.session_state['email'], "prompter_or_chatbot": "prompter", "prompt_sent": prompt_sent, "response_given": json.dumps(st.session_state['outputs']), "model_name": model_name, "model_url": model, "model_parameters": str({"max_tokens": max_tokens, "temperature": temperature}), "system_prompt": prompter_system_prompt, "base_url": get_base_url()}


  # import streamlit.components.v1 as components; components.html('<!--<script>//you can include arbitrary html and javascript this way</script>-->') #or, use st.markdown, if you want arbitrary html but javascript isn't needed.

if __name__ == "__main__": main()
