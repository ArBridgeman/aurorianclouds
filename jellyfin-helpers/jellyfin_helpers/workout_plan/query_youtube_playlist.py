import os
import pickle

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

client_secrets_file = "../../../tokens/google_youtube_client.json"
scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
token_file = "token.pickle"

# Disable OAuthlib's HTTPS verification when running locally.
# *DO NOT* leave this option enabled in production.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


def connect_and_get_token():
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, scopes
    )
    credentials = flow.run_local_server(port=0)
    with open(token_file, "wb") as token:
        pickle.dump(credentials, token)
    return credentials


def get_credentials():
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            return pickle.load(token)
    return connect_and_get_token()


def main():
    credentials = get_credentials()
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )

    # https://developers.google.com/youtube/v3/docs/playlistItems/list
    # TODO get from google sheets tab the relevant playlistID
    request = youtube.playlistItems().list(
        part="contentDetails",
        # made arms list unlisted & took id from link
        playlistId="PL2HYEHI_PARm3-hXRa0gYaWxaHNcu1vDZ",
        # need to decide if want all or some sane limit to query
        # could take 1st page & only retrieve next if needed pageToken -> int
        maxResults=10,
    )
    response = request.execute()
    print(response["pageInfo"])

    video_ids = ",".join(
        [item["contentDetails"]["videoId"] for item in response["items"]]
    )

    # https://developers.google.com/youtube/v3/docs/videos/list
    request = youtube.videos().list(part="contentDetails", id=video_ids)
    response = request.execute()
    print(response)
    #  'contentDetails': {'duration': 'PT15M2S'
    # pd.to_timedelta("PT15M2S")


if __name__ == "__main__":
    main()
