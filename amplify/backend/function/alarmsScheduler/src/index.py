import os
import json
import re
import boto3
from datetime import datetime


def handler(event, context):
    print('received event:')
    print(event)
    
    env = os.environ['ENV']

    try:
        request_body = json.loads(event['body'])
    except Exception as e:
        return json_response(str(e), 400)

    # Validate POST HttpMethod
    if(event['httpMethod'] != 'POST'):
        error_message = 'Please use POST httpMethod for this endPoint'
        return json_response(error_message, 405)

    # Validate action on request body
    try:
        action = request_body['action']

        if not action and action != 'create' and action != 'query' and action != 'delete' and action != 'update':
            error_message = 'The action on the body request should be: create, query, delete or update.'
            return json_response(error_message, 400)

    except KeyError:
        error_message = 'There was an error reading the action on the body request'
        return json_response(error_message, 400)

    # Create CloudWatchEvents client
    cloudwatch_events = boto3.client('events')

    # Create LambdaClient
    lambdaClient = boto3.client('lambda')

    response = lambdaClient.get_function(
        FunctionName='alarmsExecuter-' + env
    )

    executerArn = response['Configuration']['FunctionArn']

    if(action == 'create'):
        return create_rule(request_body, executerArn, cloudwatch_events)

    if(action == 'query'):
        return query_rule(request_body, cloudwatch_events)

    if(action == 'update'):
        return update_rule(request_body, cloudwatch_events)

    if(action == 'delete'):
        return delete_rule(request_body, cloudwatch_events)


def query_rule(requestBody, cloudwatch_events):

    name = str(read_body_parameter(requestBody, 'id'))

    try:
        if not name:
            query_result = cloudwatch_events.list_rules()
            return json_response(query_result, 200)

        if not validate_name(name):
            error_message = "The rule's id must satisfy regular expression pattern: " + \
                "[\\.\\-_A-Za-z0-9]+"
            return json_response(error_message, 400)

        query_result = cloudwatch_events.describe_rule(
            Name=name
        )

        return json_response(query_result, 200)
    except Exception as e:
        return json_response(str(e), 400)


def create_rule(requestBody, executerArn, cloudwatch_events):

    name = str(read_body_parameter(requestBody, 'id'))
    date = read_body_parameter(requestBody, 'date')

    if not name:
        error_message = 'The id on the body request cannot be empty'
        return json_response(error_message, 400)

    if not date:
        error_message = 'You must provide a date for the event'
        return json_response(error_message, 400)

    if not validate_name(name):
        error_message = "The rule's id must satisfy regular expression pattern: [\.\-_A-Za-z0-9]+"
        return json_response(error_message, 400)

    datetime_object = validate_date(date)

    if not datetime_object:
        error_message = "There was an issue reading the date. Provide a date with a valid format e.g. yyyy-mm-dd HH:MM:ss"
        return json_response(error_message, 400)

    try:
        cron_expression = 'cron(%s %s * * ? *)' % (
            datetime_object.minute, datetime_object.hour)

        new_rule_response = cloudwatch_events.put_rule(
            Name=name,
            ScheduleExpression=cron_expression,
            State='ENABLED'
        )

        # Put target for rule
        created_rule_response = cloudwatch_events.put_targets(
            Rule=name,
            Targets=[
                {
                    'Arn': executerArn,
                    'Id': name,
                    'Input': '{ "id" : ' + name + ' }'
                }
            ]
        )
        print(created_rule_response)

        return json_response("New Rule created successfully: " + new_rule_response['RuleArn'], 200)

    except Exception as e:
        return json_response(str(e), 400)


def update_rule(requestBody, cloudwatch_events):

    name = str(read_body_parameter(requestBody, 'id'))
    date = read_body_parameter(requestBody, 'date')
    state = read_body_parameter(requestBody, 'state')

    if not name:
        error_message = 'The id on the body request cannot be empty'
        return json_response(error_message, 400)

    if not date and not state:
        error_message = 'You must provide a date or a state to update the event'
        return json_response(error_message, 400)

    if not validate_name(name):
        error_message = "The rule's id must satisfy regular expression pattern: [\.\-_A-Za-z0-9]+"
        return json_response(error_message, 400)

    datetime_object = None
    if date:
        datetime_object = validate_date(date)

    if state and state.upper() != 'ENABLED' and state.upper() != 'DISABLED':
        error_message = "The state must be either ENABLED or DISABLED"
        return json_response(error_message, 400)

    try:
        cron_expression = None
        if datetime_object:
            cron_expression = 'cron(%s %s * * ? *)' % (
                datetime_object.minute, datetime_object.hour)

        query_result = cloudwatch_events.describe_rule(
            Name=name
        )

        updated_rule_response = cloudwatch_events.put_rule(
            Name=name,
            ScheduleExpression=cron_expression if cron_expression else query_result[
                'ScheduleExpression'],
            State=state.upper() if state else query_result['State']
        )

        return json_response("Rule updated successfully: " + updated_rule_response['RuleArn'], 200)

    except Exception as e:
        return json_response(str(e), 400)


def delete_rule(requestBody, cloudwatch_events):
    name = str(read_body_parameter(requestBody, 'id'))

    if not name:
        error_message = 'The id on the body request cannot be empty'
        return json_response(error_message, 400)

    if not validate_name(name):
        error_message = "The rule's id must satisfy regular expression pattern: [\.\-_A-Za-z0-9]+"
        return json_response(error_message, 400)

    try:
        remove_targets_response = cloudwatch_events.remove_targets(
            Rule=name,
            Ids=[
                name
            ],
            Force=True
        )

        if remove_targets_response:
            delete_rule_response = cloudwatch_events.delete_rule(
                Name=name,
                Force=True
            )

        if delete_rule_response:
            return json_response("Rule deleted successfully", 200)

    except Exception as e:
        return json_response(str(e), 400)


def validate_name(name):
    pattern = "[\\.\\-_A-Za-z0-9]+"

    return re.fullmatch(pattern, name)


def validate_date(strDate):
    try:
        localFormat = "%Y-%m-%d %H:%M:%S"
        datetime_object = datetime.strptime(strDate, localFormat)

        return datetime_object
    except Exception as e:
        return ''


def read_body_parameter(requestBody, parameterName):
    try:
        parameterValue = requestBody[parameterName]

        return parameterValue

    except KeyError:
        return ''


def json_response(responseMessage, code):
    return {
        'statusCode': code,
        'headers': {
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST'
        },
        'body': json.dumps(responseMessage).replace('\\\\', '\\')
    }
