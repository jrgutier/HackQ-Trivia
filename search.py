import re
from html import unescape

from bs4 import BeautifulSoup
from nltk import word_tokenize
from nltk.corpus import stopwords
from nltk.tag.perceptron import PerceptronTagger
from nltk.tokenize import RegexpTokenizer
from unidecode import unidecode
import json
import os

import networking

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "conn_settings.txt"), "r") as conn_settings:
    settings = conn_settings.read().splitlines()
    settings = [line for line in settings if line != "" and line != " "]

    try:
        GOOGLE_API_KEY = settings[1].split("=")[1]
        CSE_ID = settings[2].split("=")[1]
    except IndexError as e:
        logging.fatal(f"Settings read error: {settings}")
        raise e

STOP = set(stopwords.words("english")) - {"most", "least"}
tokenizer = RegexpTokenizer(r"\w+")
tagger = PerceptronTagger()
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:58.0) Gecko/20100101 Firefox/58.0",
           "Accept": "*/*",
           "Accept-Language": "en-US,en;q=0.5",
           "Accept-Encoding": "gzip, deflate"}
GOOGLE_URL = "https://www.googleapis.com/customsearch/v1?q={{}}&key={}&cx={}".format(GOOGLE_API_KEY,CSE_ID)
print(GOOGLE_URL)

def find_keywords(words):
    """
    Returns the list of words given without stopwords.
    :param words: List of words
    :return: Words without stopwords
    """
    return [w for w in tokenizer.tokenize(words.lower()) if w not in STOP]


def find_nouns(text, num_words, reverse=False):
    tokens = word_tokenize(text)
    tags = [tag for tag in tagger.tag(tokens) if tag[1] != "POS"]
    print(tags)

    tags = tags[:num_words] if not reverse else tags[-num_words:]

    nouns = []
    consecutive_nouns = []

    for tag in tags:
        tag_type = tag[1]
        word = tag[0]

        if "NN" not in tag_type and len(consecutive_nouns) > 0:
            nouns.append(" ".join(consecutive_nouns))
            consecutive_nouns = []
        elif "NN" in tag_type:
            consecutive_nouns.append(word)

    if len(consecutive_nouns) > 0:
        nouns.append(" ".join(consecutive_nouns))

    return nouns


def find_q_word_location(question_lower):
    for q_word in ["what", "when", "who", "which", "whom", "where", "why", "how"]:
        q_word_location = question_lower.find(q_word)
        if q_word_location != -1:
            return q_word_location


def get_google_links(page, num_results):
    results = json.loads(page)

    links = []
    for r in results["items"]:
        links.append(r["link"])
    links = list(dict.fromkeys(links))  # Remove duplicates while preserving order

    return links[:num_results]


async def search_google(question, num_results):
    """
    Returns num_results urls from a google search of question.
    :param question: Question to search
    :param num_results: Number of results to return
    :return: List of length num_results of urls retrieved from the search
    """

    page = await networking.get_response(GOOGLE_URL.format(question), timeout=5, headers=HEADERS)
    return get_google_links(page, num_results)

async def multiple_search(questions, num_results):
    queries = list(map(GOOGLE_URL.format, questions))
    pages = await networking.get_responses(queries, timeout=5, headers=HEADERS)
    link_list = [get_google_links(page, num_results) for page in pages]
    return link_list


def clean_html(html):
    # First we remove inline JavaScript/CSS:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", html.strip())
    # Then we remove html comments. This has to be done before removing regular
    # tags since comments can contain '>' characters.
    cleaned = re.sub(r"(?s)<!--(.*?)-->[\n]?", "", cleaned)
    # Next we can remove the remaining tags:
    cleaned = re.sub(r"(?s)<.*?>", " ", cleaned)
    # Finally, we deal with whitespace
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"\n", " ", cleaned)
    cleaned = re.sub(r"\s\s+", " ", cleaned)

    return unidecode(unescape(cleaned.strip()))


async def get_clean_texts(urls, timeout=1.5, headers=HEADERS):
    responses = await networking.get_responses(urls, timeout, headers)

    return [clean_html(r).lower() for r in responses]
