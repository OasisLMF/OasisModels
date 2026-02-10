### Piwind run on S3.
this folder contains the minimal set of files and option to run on s3

For the key server step, credential cannot be stored in the keys_data_storage options, they need to be set in env variable or in ~/.aws
The following environmental variables will be picked up for authentication:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION=us-west-2

