import json
import boto3
import logging


class LambdaHandler:
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, aws_region_name='us-west-2'):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region_name = aws_region_name
        self.client = None
        self.setup_resources()

    def setup_resources(self):
        self.client = boto3.client('lambda',
                                   aws_access_key_id=self.aws_access_key_id,
                                   aws_secret_access_key=self.aws_secret_access_key,
                                   region_name=self.aws_region_name)

    def invoke(self, function_name, payload, asyncFlag=False):
        invocation_type = 'RequestResponse' if not asyncFlag else 'Event'
        logging.info(f"INVOKE AWS LAMBDA FUNCTION: {function_name} {invocation_type} …")
        #print("PAYLOAD1", repr(payload))
        #print("PAYLOAD2", repr(json.dumps(payload)))
        payloadString = json.dumps(payload)
        if not isinstance(payloadString,str): # then it must be Python3 bytes
            payloadString = payloadString.decode()
        #print("PAYLOAD3", repr(payloadString))
        payload_length = len(payloadString)
        logging.info(f"LENGTH OF PAYLOAD TO BE SENT TO AWS LAMBDA: {payload_length:,} characters.")
        if payload_length <= 6291456: # 6 MB
            # This is the max allowed, see https://docs.aws.amazon.com/lambda/latest/dg/limits.html
            return self.client.invoke(
                FunctionName=function_name,
                InvocationType=invocation_type,
                LogType='Tail',
                Payload=payloadString
            )
        logging.critical(f"Aborted oversize submission to AWS Lambda '{function_name}'")
        return False
