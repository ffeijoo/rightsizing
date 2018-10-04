import boto3
import codecs
import datetime as dt
import json
import os
import pandas as pd
import re
import sys
import time
from multiprocessing import Process, Pipe
from argparse import ArgumentParser

class MetricsParallel:
    def __init__(self, region, accountId, statistics, period, startTime, endTime):
        self.ec2 = boto3.resource('ec2', region_name = region)
        self.accountId = accountId
        self.statistics = statistics
        self.period = period
        self.startTime = startTime
        self.endTime = endTime

    def total_metrics(self):

        metric_units = { 
            'CPUUtilization': 'Percent',
            'NetworkIn': 'Bytes', 'NetworkOut': 'Bytes',
            'DiskReadOps': 'Count', 'DiskWriteOps': 'Count',
            'CPUCreditBalance': 'Count', 'CPUSurplusCreditBalance': 'Count' }

        instances = []

        try:          
            instances = self.ec2.instances.filter(
                Filters=[{'Name': 'instance-state-name','Values': ['running']}])
        
        except Exception as e:
            print(e)
        
        processes = []
        parent_connections = []
  
        now = int(time.time() * 1000)
        
        for instance in instances:            

            parent_conn, child_conn = Pipe()
            parent_connections.append(parent_conn)

            process = Process(target=self.instance_metrics, args=(now, metric_units, instance, child_conn))
            processes.append(process)

        for process in processes:
            process.start()

        for process in processes:
            process.join()

        metrics = []
        for parent_connection in parent_connections:
            metrics.append(parent_connection.recv()[0])

        return metrics

    def instance_metrics(self, now, metric_units, instance, conn):
        
        res = ""
        output = {}

        for key in metric_units.keys():
            args = {
                'dimensions': [{'Name': 'InstanceId', 'Value': instance.id}],
                'startTime': now - self.startTime,
                'endTime': now - self.endTime,
                'period': self.period,
                'statistics': [self.statistics],
                'metricName': key,
                'namespace': 'AWS/EC2',
                'unit': metric_units[key]
            }

            numRetries = 0
            gettingMetrics = True
            while gettingMetrics:
                try:
                    session = boto3.session.Session(region_name=instance.placement['AvailabilityZone'][:-1])
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
                        output[str(datapoint['Timestamp'])][key] = datapoint[self.statistics]
                    else:
                        readableTimeStamp = datapoint['Timestamp']
                        readableInstanceLaunchTime = instance.launch_time
                        tagString = ''
                        ebsString = ''

                        if instance.tags:
                            for tag in instance.tags:
                                tagString += re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Key'].replace(',', ' ')) + ':' + re.sub('[^a-zA-Z0-9-_ *.]', '', tag['Value'].replace(',', ' ')) + ' | '
                            tagString = tagString[:-3]
                        if instance.block_device_mappings:
                            for ebs in instance.block_device_mappings:
                                ebsString += ebs['Ebs']['VolumeId'] + ' | '
                            ebsString = ebsString[:-3]

                        output[str(datapoint['Timestamp'])] = {
                            'humanReadableTimestamp': readableTimeStamp,
                            'timestamp': datapoint['Timestamp'],
                            'accountId': self.accountId,                            
                            'az': instance.placement['AvailabilityZone'],
                            'instanceId': instance.id,
                            'instanceType': instance.instance_type,
                            'instanceTags': tagString,
                            'ebsBacked': True if instance.root_device_type == 'ebs' else 'false',
                            'volumeIds': ebsString,
                            'instanceLaunchTime': instance.launch_time,
                            'humanReadableInstanceLaunchTime': readableInstanceLaunchTime,
                            key: datapoint[self.statistics]
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
        
        conn.send([res])
        conn.close()

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
    
    metrics = MetricsParallel(
        args.region,
        args.account,
        args.statistics,
        int(args.period) * 60,
        int(args.start) * 60 * 60 * 1000,
        int(args.end) * 60 * 60 * 1000
    )

    rs = metrics.total_metrics()

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