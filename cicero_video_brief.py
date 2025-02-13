#!/usr/bin/env -S streamlit run
import streamlit as st
# code adapted from https://developers.google.com/drive/api/guides/manage-uploads#python_1
import google.auth
from google.auth.exceptions import DefaultCredentialsError 
from googleapiclient.discovery import build # this is google-api-python-client
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO
from cicero_shared import st_print, is_dev
from cicero_chat import display_chat
from cicero_video_brief_system_prompt import example_document, example_dick

# Theoretically this may be used in Databricks or standalone instead of in streamlit. Not sure how we'll do the google auth for that, though...

st.warning("The google docs upload seems to work only within GCP so far.")
# code adapted from https://developers.google.com/drive/api/guides/manage-uploads#python_1
if is_dev() and st.button("Upload test file"):
  # Upload file with conversion
  
  # Todo(wyatt): figure this out:
  # Load pre-authorized user credentials from the environment.
  # TODO(developer) - See https://developers.google.com/identity
  # for guides on implementing OAuth2 for the application.

  creds, _ = google.auth.default() #this works in our deployed environment, but not in local testing (because in local testing, you aren't logged in! May need to revive the optional google login button if we want to fix that?)

  try:
    # create drive api client
    service = build("drive", "v3", credentials=creds)
    # here for testing purposes.
    st_print(service.about())
    st_print(service.about().get())
    
    # On GCP we seem to get this far, at least.
    file_metadata = {
        "name": "Cool Example Document",
        "mimeType": "application/vnd.google-apps.document",
    }
    media = MediaIoBaseUpload(BytesIO(example_document), mimetype="text/html", resumable=True)
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    st_print(f'File with ID: "{file.get("id")}" has been uploaded.')
  except HttpError as error:
    st_print(f"An HTTP error occurred: {error}")
  except DefaultCredentialsError as e:
    st_print(f"An error occurred (probably because you're not logged in to google in local testing!): {e}")

st.write("Paste in a script below, the sort that is formatted vaguely like:\n ```", example_dick, "\n```\nWarning: this request will probably take approximately 20 seconds to process.")
display_chat("_video_brief")

