import csv
import io
import re
from flask import Flask, render_template, request, jsonify, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from rq import Queue
from rq.job import Job

import configuration
import reviewparser
from worker import conn

app = Flask(__name__)
app.config.from_object(configuration.ProductionConfig)
db = SQLAlchemy(app)

task_queue = Queue(connection=conn)

import models


@app.route('/')
def index():
    return render_template('index.html')

#Route to pull the data
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

#Route to check job status
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

#Route to Export the CSV
@app.route('/download/<int:id>',methods=['get'])
def download_csv(id):
    dest = io.StringIO()
    #writer = csv.writer(dest)
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


if __name__ == '__main__':
    app.run(threaded=True,
            host='0.0.0.0'
            )
