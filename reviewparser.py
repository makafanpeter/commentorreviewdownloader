



if __name__ == '__main__':
    parser = ReviewParser.get_parser("youtube")
    result = parser.get_reviews('https://www.youtube.com/watch?v=WFF0YBKfbnk')
    # UserName Date Star rating Review or Comment Link
    if type(result) is not dict:
        output = 'hello.csv'
        header = ["user_name", "date", "star_rating", "review", "url"]
        reviews = models.Review.query.filter_by(item_id=result).all()
        with open(output, "w", encoding="utf-8") as g:
            writer = csv.DictWriter(g, delimiter=",", fieldnames=header)
            writer.writeheader()
            for row in reviews:
                p = row.serialize
                print(p)
                writer.writerow(p)
