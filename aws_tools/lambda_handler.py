import json
import boto3


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
        print(f"INVOKE LAMBDA FUNCTION: {function_name} {invocation_type} ...")
        #print("PAYLOAD1", repr(payload))
        #print("PAYLOAD2", repr(json.dumps(payload)))
        payloadString = json.dumps(payload)
        if not isinstance(payloadString,str): # then it must be Python3 bytes
            payloadString = payloadString.decode()
        #print("PAYLOAD3", repr(payloadString))
        return self.client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            LogType='Tail',
            Payload=payloadString
        )
