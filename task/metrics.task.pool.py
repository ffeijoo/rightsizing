import boto3
import codecs
import datetime as dt
import json
import multiprocessing
import os
import pandas as pd
import re
import sys
import time
from argparse import ArgumentParser
from functools import partial

def total_metrics(region, accountId, statistics, period, startTime, endTime):

    ec2 = boto3.resource('ec2', region_name = region)
    
    now = int(time.time() * 1000)
    
    instances = []

    try:          
        rs = ec2.meta.client.describe_instances()
    except Exception as e:
        print(e)
    
    if 'Reservations' in rs:
        for reservation in rs['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    instance['OwnerAccountId'] = accountId
                    instances.append(instance)

    pool = multiprocessing.Pool(multiprocessing.cpu_count() - 1)
    func = partial(instance_metrics, accountId, statistics, period, now, startTime, endTime)
    response = pool.map(func, instances)
    pool.close()
    pool.join()

    return response

def instance_metrics(accountId, statistics, period, now, startTime, endTime, instance):

    metric_units = { 
        'CPUUtilization': 'Percent',
        'NetworkIn': 'Bytes', 'NetworkOut': 'Bytes',
        'DiskReadOps': 'Count', 'DiskWriteOps': 'Count',
        'CPUCreditBalance': 'Count', 'CPUSurplusCreditBalance': 'Count' }

    
    res = ""
    output = {}

    for key in metrics.keys():
        args = {
            'dimensions': [{'Name': 'InstanceId', 'Value': instance['InstanceId']}],
            'startTime': now - startTime,
            'endTime': now - endTime,
            'period': period,
            'statistics': [statistics],
            'metricName': key,
            'namespace': 'AWS/EC2',
            'unit': metrics[key]
        }

        numRetries = 0
        gettingMetrics = True
        while gettingMetrics:
            try:
                session = boto3.session.Session(region_name=instance['Placement']['AvailabilityZone'][:-1])
                cloudwatch = session.resource('cloudwatch')
                result = cloudwatch.meta.client.get_metric_statistics(
                    Dimensions=args['dimensions'],StartTime=dt.datetime.fromtimestamp(args['startTime']/1e3).strftime('%Y-%m-%d %H:%M:%S'),
                    EndTime=dt.datetime.fromtimestamp(args['endTime']/1e3).strftime('%Y-%m-%d %H:%M:%S'),
                    Period=args['period'],
                    Statistics=args['statistics'],
                    MetricName=args['metricName'],
                    Namespace=args['namespace'],
                    Unit=args['unit'])
                gettingMetrics = False
            except Exception as e:
                print(e)
                numRetries += 1
                if numRetries > 3:
                    gettingMetrics = False
                    raise
                    time.sleep(1)
        
        for datapoint in result['Datapoints']:
            try:
                if(str(datapoint['Timestamp']) in output):
                    output[str(datapoint['Timestamp'])][key] = datapoint[statistics]
                else:
                    readableTimeStamp = datapoint['Timestamp']
                    readableInstanceLaunchTime = instance['LaunchTime']
                    tagString = ''
                    ebsString = ''

                    if instance.get('Tags','None') != 'None':
                        for tag in instance['Tags']:
                            tagString += re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Key'].replace(',', ' ')) + ':' + re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Value'].replace(',', ' ')) + ' | '
                        tagString = tagString[:-3]
                    if instance['BlockDeviceMappings']:
                        for ebs in instance['BlockDeviceMappings']:
                            ebsString += ebs['Ebs']['VolumeId'] + ' | '
                        ebsString = ebsString[:-3]

                    output[str(datapoint['Timestamp'])] = {
                        'humanReadableTimestamp': readableTimeStamp,
                        'timestamp': datapoint['Timestamp'],
                        'accountId': instance['OwnerAccountId'],                            
                        'az': instance['Placement']['AvailabilityZone'],
                        'instanceId': instance['InstanceId'],
                        'instanceType': instance['InstanceType'],
                        'instanceTags': tagString,
                        'ebsBacked': True if instance["RootDeviceType"] == 'ebs' else 'false',
                        'volumeIds': ebsString,
                        'instanceLaunchTime': instance['LaunchTime'],
                        'humanReadableInstanceLaunchTime': readableInstanceLaunchTime,
                         key: datapoint[statistics]
                    }
            except Exception as e:
                print(e)

    for row in output:
        res += u"\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\",\"{5}\",\"{6}\",\"{7}\",\"{8}\",\"{9}\",\"{10}\",\"{11}\",\"{12}\",\"{13}\",\"{14}\",\"{15}\",\"{16}\",\"{17}\"\n".format(\
            output[row].setdefault('humanReadableTimestamp',''),\
            output[row].setdefault('timestamp',''),\
            output[row].setdefault('accountId',''),\
            output[row].setdefault('az',''),\
            output[row].setdefault('instanceId',''),\
            output[row].setdefault('instanceType',''),\
            output[row].setdefault('instanceTags',''),\
            output[row].setdefault('ebsBacked',''),\
            output[row].setdefault('volumeIds',''),\
            output[row].setdefault('instanceLaunchTime',''),\
            output[row].setdefault('humanReadableInstanceLaunchTime',''),\
            output[row].setdefault('CPUUtilization','0'),\
            output[row].setdefault('NetworkIn','0'),\
            output[row].setdefault('NetworkOut','0'),\
            output[row].setdefault('DiskReadOps','0'),\
            output[row].setdefault('DiskWriteOps','0'),
            output[row].setdefault('CPUCreditBalance','0'),
            output[row].setdefault('CPUSurplusCreditBalance','0'))
    
    return res

def main():

    parser = ArgumentParser()
    parser.add_argument('--region')
    parser.add_argument('--account')
    parser.add_argument('--statistics')
    parser.add_argument('--period',)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--bucket')

    args = parser.parse_args()
    
    rs = total_metrics(
        args.region,
        args.account,
        args.statistics,
        int(args.period) * 60,
        int(args.start) * 60 * 60 * 1000,
        int(args.end) * 60 * 60 * 1000
    )

    now = dt.datetime.now()
    start = now - dt.timedelta(hours=int(args.start))
    end = now - dt.timedelta(hours=int(args.end))

    filename = args.region + '-' + format(start, '[%Y-%m-%d]') + '-' + format(end, '[%Y-%m-%d]')
    
    csv = filename + '.csv'
    outfile = codecs.open(csv, 'a', encoding='utf-8')

    outfile.write(
        u"\"{0}\",\"{1}\",\"{2}\",\"{3}\",\"{4}\",\"{5}\",\"{6}\",\"{7}\",\"{8}\",\"{9}\",\"{10}\",\"{11}\",\"{12}\",\"{13}\",\"{14}\",\"{15}\",\"{16}\",\"{17}\"\n".format(
            'humanReadableTimestamp', 'timestamp', 'accountId', 'az', 'instanceId', 'instanceType', 'instanceTags',
            'ebsBacked', 'volumeIds', 'instanceLaunchTime', 'humanReadableInstanceLaunchTime', 'CPUUtilization',
            'NetworkIn', 'NetworkOut', 'DiskReadOps', 'DiskWriteOps', 'CPUCreditBalance', 'CPUSurplusCreditBalance'))
    
    for line in rs:
        outfile.write(line)
    outfile.close()

    parquet = filename + '.parquet'
    pd.read_csv(csv).to_parquet(parquet, compression='gzip')

    s3 = boto3.resource('s3', region_name = args.region)
    s3.meta.client.upload_file(parquet, args.bucket, 'metrics/' + args.statistics + '/' + format(now, '%Y/%m/%d') + '/' + parquet)

    sys.exit(0)

if __name__ == "__main__":
    main()