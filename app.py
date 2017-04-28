import reviewparser
import csv
import re
import io

from flask.ext.sqlalchemy import SQLAlchemy
import os
from flask import Flask, render_template, request, jsonify, url_for, redirect, abort, make_response
from rq import Queue
from rq.job import Job

import configuration
from worker import conn

app = Flask(__name__)
app.config.from_object(configuration.ProductionConfig)
db = SQLAlchemy(app)

task_queue = Queue(connection=conn)

from models import *


@app.route('/')
def index():
    return render_template('index.html')


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
    parser =  reviewparser.ReviewParser.get_parser(parser_name)

    # start job
    job = task_queue.enqueue_call(
        func=parser.get_reviews, args=(url,), result_ttl=5000
    )
    # return created job id
    return job.get_id()


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


@app.route('/download/<int:id>',methods=['get'])
def download_csv(id):
    dest = io.StringIO()
    #writer = csv.writer(dest)
    reviews = Review.query.filter_by(item_id=id).all()
    header = ["user_name", "date", "star_rating", "review", "url"]
    writer = csv.DictWriter(dest, delimiter=",", fieldnames=header)
    writer.writeheader()
    for row in reviews:
        writer.writerow(row.serialize)

    output = make_response(dest.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output


if __name__ == '__main__':
    app.run(threaded=True,
            host='0.0.0.0'
            )
