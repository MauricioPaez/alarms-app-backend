export type AmplifyDependentResourcesAttributes = {
    "function": {
        "alarmsScheduler": {
            "Name": "string",
            "Arn": "string",
            "Region": "string",
            "LambdaExecutionRole": "string"
        },
        "alarmsExecuter": {
            "Name": "string",
            "Arn": "string",
            "Region": "string",
            "LambdaExecutionRole": "string"
        }
    },
    "api": {
        "alarmsAPI": {
            "RootUrl": "string",
            "ApiName": "string",
            "ApiId": "string"
        }
    }
}