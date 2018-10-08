import json
import boto3
import urllib
import csv
import os
import io

def lambda_handler(event, context):
    
    raw = '/tmp/raw.csv'
    out = io.StringIO()
    
    try:
        
        urllib.request.urlretrieve(os.environ['PRICE_LIST_URL'], raw)

        with open(raw, "rt") as infile:
            reader = csv.reader(infile, delimiter=',', quotechar='"')
            for x in range(0,5):
                next(reader, None)
            writer = csv.writer(out, delimiter='|', quoting=csv.QUOTE_MINIMAL)

            for row in reader:
                writer.writerow(row)

        boto3.client(service_name='s3').put_object(
            Body=out.getvalue(), Bucket=os.environ['BUCKET_NAME'], Key='_temporary/prices/ec2.csv')
            
        return {
            'crawlerName': os.environ['CRAWLER_NAME']
        }

    except Exception as e:
        print(e)
        message = 'Error downloading Price List'
        print(message)
        raise Exception(message)