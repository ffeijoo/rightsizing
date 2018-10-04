FROM danigoland/py36-alpine-llvm6

ENV AWS_CLI_VERSION 1.16.15

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN apk --update add --no-cache g++ build-base

RUN pip install --no-cache-dir -r requirements.txt

COPY metrics.task.process.py ./
COPY metrics.task.pool.py ./

CMD python ./metrics.task.process.py --region ${REGION} --account ${ACCOUNT} --statistics ${STATISTICS} --period ${PERIOD} --start ${START_TIME} --end ${END_TIME} --bucket ${TARGET_BUCKET}
#CMD python ./metrics.task.pool.py --region ${REGION} --account ${ACCOUNT} --statistics ${STATISTICS} --period ${PERIOD} --start ${START_TIME} --end ${END_TIME}