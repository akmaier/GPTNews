# Created by Andreas Maier
# Published under GPL 3.0

import feedparser
import openai
import re
import os
import requests
import time
import medium
import urllib
import tweepy

from openai import InvalidRequestError
from openai.error import ServiceUnavailableError

# Set the OpenAI API key
openai.api_key = "your_openai_key"

# Replace these with your own API keys and secrets
consumer_key = "your_twitter_key"
consumer_secret = "your_twitter_key"
access_token = "your_twitter_key"
access_token_secret = "your_twitter_key"


def post_tweet(message):
    # Authenticate with Twitter
    auth = tweepy.OAuth1UserHandler(consumer_key, consumer_secret, access_token, access_token_secret)

    # Create the API client
    api = tweepy.API(auth)

    # Post the message
    api.update_status(message)

    print("Message posted on twitter successfully!")


def remove_blank_lines(input_string):
    lines = input_string.split("\n")

    # Remove blank lines and add paragraph tags
    output_lines = []
    for line in lines:
        if line.strip():  # Check if the line is not blank
            output_lines.append(line)

    # Join the lines back into a single string
    output_string = "\n".join(output_lines)

    # Print the output string
    return output_string


def htmlify(input_string):
    lines = input_string.split("\n")

    # Remove blank lines and add paragraph tags
    output_lines = []
    for line in lines:
        if line.strip():  # Check if the line is not blank
            output_lines.append("<p>{}</p>".format(line))

    # Join the lines back into a single string
    output_string = "\n".join(output_lines)

    # Print the output string
    return output_string


def publish_post(title, content, orig_url):
    medium_api_key = "your_Medium_Key"
    # Set up the Medium client with your API key
    client = medium.Client(access_token=medium_api_key)

    # Create the post object
    user = client.get_current_user()

    # Use the OpenAI API to generate an image from the title
    response = openai.Image.create(
        prompt=title,
        n=1,
        size="1024x1024",
    )
    image_url = response["data"][0]["url"]

    # Download the image from the URL
    response = requests.get(image_url)
    image_data = response.content

    # Upload the image to Medium
    print(image_url)
    filename = "/local/filesystem/dalle2_{}.png".format(os.getpid())
    urllib.request.urlretrieve(image_url, filename)
    response = client.upload_image(file_path=filename, content_type="image/png")

    # Get the image ID
    image_id = response["md5"]

    # Set the image as the first element in the post
    html = "<h1>" + title + "</h1><p><img src='{}'></p>".format(response["url"])
    html = html + content + "<p>This post was generated automatically by " \
                            "<a href='https://chat.openai.com/chat'>GPT by OpenAI</a>. " \
                            "The image is created by " \
                            "<a href='https://labs.openai.com/e/nLdHawUIwBM9uFy2oy3X1GjV/RCtM6kQyLLk10b8ssIFlUjHD'>" \
                            "DALLE-2</a> from the title. " \
                            "The content of this post may not be factually correct. Check the " \
                            "<a href='{}'>original source</a>. " \
                            "The content of this post including images are licensed under CC0.".format(orig_url)

    # Publish the post
    user = client.get_current_user()
    response = client.create_post(user_id=user["id"], title=title, content=html, content_format="html",
                                  publish_status="public", license="public-domain", tags=['GPT News', 'News'])
    news_url = response['url']
    post_tweet("#GPTNews: " + title + "\n\n" + news_url)
    # Wait 2 mins to not exceed twitter's rate limits.
    time.sleep(120)

def pick_first_4000_chars(string):
    last_4000_chars = string[4000:]  # pick the first 4000 characters
    return last_4000_chars


def pick_first_4000_words(string):
    words = string.split(" ")  # split the string into a list of words
    first_4000_words = words[:4000]  # pick the first 4000 words
    return " ".join(first_4000_words)  # join the words into a single string and return


def edit_text(command, text):
    # Use the GPT-3 model to rewrite the text
    query = text
    if (len(query) > 4000):
        query = pick_first_4000_chars(query)
    response = openai.Edit.create(
        engine="text-davinci-edit-001",
        input=query,
        instruction=command,
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    # Get the rewritten text
    rewritten_text = response["choices"][0]["text"]

    # Remove any remaining HTML tags from the rewritten text
    rewritten_text = re.sub("<[^<]+?>", "", rewritten_text)

    return rewritten_text


def rewrite_text(command, text):
    # Use the GPT-3 model to rewrite the text
    query = text + command
    if (len(query) > 4000):
        query = pick_first_4000_chars(query)
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=query,
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    # Get the rewritten text
    rewritten_text = response["choices"][0]["text"]

    # Remove any remaining HTML tags from the rewritten text
    rewritten_text = re.sub("<[^<]+?>", "", rewritten_text)

    return rewritten_text


def fetch_html(url):
    # Make an HTTP GET request to the URL
    response = requests.get(url)

    # Check the response status code
    if response.status_code == 200:
        # Return the HTML code of the webpage
        return response.text
    else:
        return None


def get_first_double_quoted_expression(string):
    # use a regular expression to match the first double-quoted expression in the string
    match = re.search(r'"([^"\\]*(?:\\.[^"\\]*)*)"', string)

    if match:
        # if a match is found, return the first double-quoted expression
        return match.group(1)
    else:
        # if no match is found, return an empty string
        return ""


def get_news_text(html):
    lines = html.split("\n")

    # Flag to track if the first matching line has been found
    found = False

    # Print all lines containing "articleBody"
    for line in lines:
        # Search for "articleBody" in the line
        index = line.find("articleBody")
        # If the string is found and the first matching line has not been found yet
        if index != -1 and not found:
            # Remove the leading string "articleBody" from the line
            line = line[index + len("articleBody") + 1:]
            line = get_first_double_quoted_expression(line)
            # Set the flag to indicate that the first matching line has been found
            return line
    return None


def parse_entry(entry):
    print("\n---")
    title = entry["title"]
    # Fetch the HTML code of the webpage
    html = fetch_html(entry["link"])
    if html:
        news_text = get_news_text(html)
        if news_text:
            print("Title Old: ", title)
            new_title = remove_blank_lines(
                rewrite_text(". Write a headline similar to the previous one. "
                             " Keep the same lenght!"
                             , title))
            print("Title New: ", new_title)
            print("Link: ", entry["link"])
            print("Old News: ", news_text)

            new_news = htmlify(
                rewrite_text(" Please convert the text into a squib in emotionally engaging language."
                             " Make sure that the text is at least 4.000 characters long"
                             " and has more than four paragraphs. " +
                             " Never ever copy parts of the text! ", news_text))
            while len(new_news) < 1000:
                new_news = htmlify(
                    rewrite_text(" Please convert the text into a squib in emotionally engaging language."
                                 " Make sure that the text is at least 4.000 characters long"
                                 " and has more than four paragraphs. " +
                                 " Never ever copy parts of the text! ", news_text))
            print("New News: ", new_news)
            publish_post(new_title, new_news, entry["link"])


# URL of the RSS feed to monitor
rss_url = "http://rss.cnn.com/rss/cnn_topstories.rss"

# Parse the RSS feed
feed = feedparser.parse(rss_url)

# List to store parsed entries
parsed_entries = []

# Print the feed title and number of entries
print(feed["feed"]["title"])
print("Total entries: ", len(feed["entries"]))

# Monitor the feed continuously
while True:
    # Parse the RSS feed
    feed = feedparser.parse(rss_url)

    # Print the feed title and number of entries
    print(feed["feed"]["title"])
    print("Total entries: ", len(feed["entries"]))

    # Process new entries
    for entry in feed["entries"]:
        if entry not in parsed_entries:
            try:
                parse_entry(entry)
            except ServiceUnavailableError:
                print("Sever Overload at OpenAI. Waiting 60 sec.")
                time.sleep(60)
            except InvalidRequestError:
                print("Post omitted due to OpenAI API restritions")
            parsed_entries.append(entry)

    # Sleep for a while before checking for new entries
    print("Processed entries: ", len(parsed_entries))
    time.sleep(60)  # check for new entries every 60 seconds

