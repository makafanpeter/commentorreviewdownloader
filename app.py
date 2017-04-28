import csv
import io
import json
import re
import requests
from dateutil import parser as dateparser
from flask import Flask, render_template, request, jsonify, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from googleapiclient.discovery import build
from lxml import html
from rq import Queue
from rq.job import Job

import configuration
from worker import conn

app = Flask(__name__)
app.config.from_object(configuration.ProductionConfig)
db = SQLAlchemy(app)

task_queue = Queue(connection=conn, default_timeout=600)
import models


@app.route('/')
def index():
    return render_template('index.html')


# Route to pull the data
@app.route('/crawl', methods=['POST'])
def get_reviews():
    # get url
    if not request.json:
        abort(400)
    data = request.json.get('url')
    url = data
    url = re.sub("https://|http://", "", url)
    # form URL, id necessary
    if 'http://' not in url[:7]:
        url = 'https://' + url

    parser_name = ''
    if 'youtube' in url.lower():
        parser_name = "youtube"
    elif 'amazon' in url.lower():
        parser_name = 'amazon'
    else:
        abort(400)
    parser = ReviewParser.get_parser(parser_name)

    # start job
    job = task_queue.enqueue_call(
        func=parser.get_reviews, args=(url,), result_ttl=5000
    )
    # return created job id
    return job.get_id()


# Route to check job status
@app.route("/result/<job_key>", methods=['GET'])
def get_result(job_key):
    job = Job.fetch(job_key, connection=conn)

    if job.is_finished:
        if type(job.result) == dict:
            if "error" in job.result:
                return jsonify(job.result), 500
        return jsonify({"id": job.result})
    else:
        return "Nay!", 202


# Route to Export the CSV
@app.route('/download/<int:id>', methods=['get'])
def download_csv(id):
    dest = io.StringIO()
    # writer = csv.writer(dest)
    reviews = models.Review.query.filter_by(item_id=id).all()
    header = ["user_name", "date", "star_rating", "review", "url"]
    writer = csv.DictWriter(dest, delimiter=",", fieldnames=header)
    writer.writeheader()
    for row in reviews:
        writer.writerow(row.serialize)

    output = make_response(dest.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"

    return output


# Review Parser
# Youtube API Configuration
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
DEVELOPER_KEY = "AIzaSyCSo0Boq9Ym29KPqE8Fjac06sTg3c4eRhw"
import os

AMAZON_ASIN = re.compile("/([a-zA-Z0-9]{10})(?:[/?]|$)")
YOUTUBE_ID = re.compile("((?<=(v|V)/)|(?<=be/)|(?<=(\?|\&)v=)|(?<=embed/))([\w-]+)")


class ReviewParser(object):
    parsers = None
    errors = []

    def __init__(self, parser_name):
        self.parser_name = parser_name

    @classmethod
    def get_parser(cls, parser_name: object) -> object:
        if cls.parsers is None:
            cls.parsers = {}
            for parser_class in cls.__subclasses__():
                parser = parser_class()
                cls.parsers[parser.parser_name] = parser
        return cls.parsers[parser_name]

    def get_reviews(self, url):
        pass


# Youtube Review Parser
class YoutubeReviewParser(ReviewParser):
    def __init__(self):
        super(YoutubeReviewParser, self).__init__('youtube')
        self.youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
                             developerKey=DEVELOPER_KEY)

    def get_reviews(self, url):
        youtube_url, video_id = get_youtube_id(url)
        try:
            video_url = 'https://www.googleapis.com/youtube/v3/videos?id={0}&key={1}&fields=items(id,snippet(channelId,title,categoryId),statistics)&part=snippet,statistics'.format(
                video_id, DEVELOPER_KEY)
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36'}
            response = requests.get(video_url, headers=headers)
            video_details = response.json()
            if "items" not in video_details or len(video_details["items"]) == 0:
                raise ValueError("Unable to Get Video Details")
            video_information = {"ref_id": video_id,
                                 "ratings": "N/A",
                                 "name": video_details["items"][0]["snippet"]["title"],
                                 "reviews": [],
                                 "url": 'https://www.youtube.com/watch?v=' + video_id,
                                 "comment_count": video_details["items"][0]["statistics"]["commentCount"]
                                 }
            data = []
            results = self.youtube.commentThreads().list(part="snippet", videoId=video_id,
                                                         textFormat="plainText").execute()
            for item in results["items"]:
                review_dict = {

                    'review': item['snippet']['topLevelComment']['snippet']['textOriginal'],
                    'date': dateparser.parse(item['snippet']['topLevelComment']['snippet']['publishedAt']).strftime(
                        '%d %b %Y'),

                    'star_rating': "N/A",
                    'user_name': item['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                    'url': 'https://www.youtube.com/watch?v={0}&lc={1}'.format(video_id, item['id'])
                }
                data.append(review_dict)
            while "nextPageToken" in results:
                results = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    pageToken=results["nextPageToken"],
                    textFormat="plainText",
                ).execute()
                for item in results["items"]:
                    snippet = item['snippet']['topLevelComment']['snippet']
                    if snippet :
                     review_dict = {'review': snippet.get('textOriginal', ''),
                                   'date': dateparser.parse(snippet['publishedAt']).strftime( '%d %b %Y'), 'star_rating': 0,
                                   'user_name': snippet.get('authorDisplayName',''),
                                   'url': 'https://www.youtube.com/watch?v={0}&lc={1}'.format(video_id, item['id'])}
                    data.append(review_dict)
            video_information["reviews"] = data
            item = models.Item(name=video_information['name'], url=youtube_url, ref_id=video_id)
            db.session.add(item)
            db.session.commit()
            for comment in data:
                review = models.Review(user_name=comment['user_name'], review=comment['review'], url=comment['url'],
                                       date=comment['date'], star_rating=comment['star_rating'], item_id=item.id)
                db.session.add(review)
            db.session.commit()

            return item.id
        except Exception as e:
            print(e)
            self.errors.append(e.__str__())
            return {"error": self.errors}
        return {"error": "failed to process comments", "video_id": video_id}


# Amazon Review Parser
class AmazonReviewParser(ReviewParser):
    def __init__(self):
        super(AmazonReviewParser, self).__init__('amazon')

    def get_reviews(self, url):
        try:
            amazon_url, asin = get_amazon_asin(url)
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36'}
            page = requests.get(amazon_url, headers=headers)
            page_response = page.text

            parser = html.fromstring(page_response)
            XPATH_AGGREGATE = '//span[@id="acrCustomerReviewText"]'
            XPATH_REVIEW_SECTION_1 = '//div[contains(@id,"reviews-summary")]'
            XPATH_REVIEW_SECTION_2 = '//div[@data-hook="review"]'

            XPATH_AGGREGATE_RATING = '//table[@id="histogramTable"]//tr'
            XPATH_PRODUCT_NAME = '//h1//span[@id="productTitle"]//text()'
            XPATH_PRODUCT_PRICE = '//span[@id="priceblock_ourprice"]/text()'

            raw_product_price = parser.xpath(XPATH_PRODUCT_PRICE)
            product_price = ''.join(raw_product_price).replace(',', '')

            raw_product_name = parser.xpath(XPATH_PRODUCT_NAME)
            product_name = ''.join(raw_product_name).strip()
            total_ratings = parser.xpath(XPATH_AGGREGATE_RATING)
            reviews = parser.xpath(XPATH_REVIEW_SECTION_1)
            if not reviews:
                reviews = parser.xpath(XPATH_REVIEW_SECTION_2)
            ratings_dict = {}
            reviews_list = []

            if not reviews:
                raise ValueError('unable to find reviews in page')

            # grabing the rating  section in product page
            for ratings in total_ratings:
                extracted_rating = ratings.xpath('./td//a//text()')
                if extracted_rating:
                    rating_key = extracted_rating[0]
                    raw_raing_value = extracted_rating[1]
                    rating_value = raw_raing_value
                    if rating_key:
                        ratings_dict.update({rating_key: rating_value})
            # Parsing individual reviews
            for review in reviews:
                XPATH_RATING = './/i[@data-hook="review-star-rating"]//text()'
                XPATH_REVIEW_HEADER = './/a[@data-hook="review-title"]//text()'
                XPATH_REVIEW_POSTED_DATE = './/a[contains(@href,"/profile/")]/parent::span/following-sibling::span/text()'
                XPATH_REVIEW_TEXT_1 = './/div[@data-hook="review-collapsed"]//text()'
                XPATH_REVIEW_TEXT_2 = './/div//span[@data-action="columnbalancing-showfullreview"]/@data-columnbalancing-showfullreview'
                XPATH_REVIEW_COMMENTS = './/span[@data-hook="review-comment"]//text()'
                XPATH_AUTHOR = './/a[contains(@href,"/profile/")]/parent::span//text()'
                XPATH_REVIEW_TEXT_3 = './/div[contains(@id,"dpReviews")]/div/text()'
                raw_review_author = review.xpath(XPATH_AUTHOR)
                raw_review_rating = review.xpath(XPATH_RATING)
                raw_review_header = review.xpath(XPATH_REVIEW_HEADER)
                raw_review_posted_date = review.xpath(XPATH_REVIEW_POSTED_DATE)
                raw_review_text1 = review.xpath(XPATH_REVIEW_TEXT_1)
                raw_review_text2 = review.xpath(XPATH_REVIEW_TEXT_2)
                raw_review_text3 = review.xpath(XPATH_REVIEW_TEXT_3)
                review_id = review.attrib['id']
                author = ' '.join(''.join(raw_review_author).split()).strip('By')

                # cleaning data
                review_rating = ''.join(raw_review_rating).replace('out of 5 stars', '')
                review_header = ' '.join(' '.join(raw_review_header).split())
                review_posted_date = dateparser.parse(''.join(raw_review_posted_date)).strftime('%d %b %Y')
                review_text = ' '.join(' '.join(raw_review_text1).split())

                # grabbing hidden comments if present
                if raw_review_text2:
                    json_loaded_review_data = json.loads(raw_review_text2[0])
                    json_loaded_review_data_text = json_loaded_review_data['rest']
                    cleaned_json_loaded_review_data_text = re.sub('<.*?>', '', json_loaded_review_data_text)
                    full_review_text = review_text + cleaned_json_loaded_review_data_text
                else:
                    full_review_text = review_text
                if not raw_review_text1:
                    full_review_text = ' '.join(' '.join(raw_review_text3).split())

                raw_review_comments = review.xpath(XPATH_REVIEW_COMMENTS)
                review_comments = ''.join(raw_review_comments)
                review_comments = re.sub('[A-Za-z]', '', review_comments).strip()
                review_dict = {

                    'review': full_review_text,
                    'date': review_posted_date,

                    'star_rating': review_rating,
                    'user_name': author,
                    'url': "https://www.amazon.com/gp/customer-reviews/{0}".format(review_id)
                }

                reviews_list.append(review_dict)

            data = {
                'ratings': ratings_dict,
                'reviews': reviews_list,
                'url': amazon_url,
                'price': product_price,
                'name': product_name
            }
            item = models.Item(name=product_name, url=amazon_url, ref_id=asin)
            db.session.add(item)
            db.session.commit()
            for comment in reviews_list:
                review = models.Review(user_name=comment['user_name'], review=comment['review'], url=comment['url'],
                                       date=comment['date'], star_rating=comment['star_rating'], item_id=item.id)
                db.session.add(review)
            db.session.commit()

            return item.id
        except Exception as e:
            print(os.environ)
            print(e)
            self.errors.append(e.__str__())
            return {"error": self.errors}

        return {"error": "failed to process the page", "asin": asin}


def get_amazon_asin(url):
    pattern = AMAZON_ASIN.search(url)
    if pattern:
        asin = pattern.groups(0)[0]
        amazon_url = 'http://www.amazon.com/dp/' + asin
        return amazon_url, asin
    return None


def get_youtube_id(url):
    pattern = YOUTUBE_ID.search(url)
    if pattern:
        video_id = pattern.group(0)
        youtube_url = 'https://www.youtube.com/watch?v=' + video_id
        return youtube_url, video_id
    return None


if __name__ == '__main__':
     app.run(threaded=True,
           host='0.0.0.0'
             )
