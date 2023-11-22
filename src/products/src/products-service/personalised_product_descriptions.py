# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
from dynamo_setup import dynamo_resource,ddb_table_personalised_product_descriptions,ddb_table_products
from server import app
import os
import boto3
import requests
import json

class PersonalisedDescriptionGenerator():
    users_api_url = os.getenv("USERS_API_URL")
    users_service_host = os.getenv('USERS_SERVICE_HOST')
    users_service_port = os.getenv('USERS_SERVICE_PORT', 80)
    dynamo_client = dynamo_resource.meta.client
    
    def initialise_bedrock():
        app.logger.info("Initialising bedrock client...")
        try:
            bedrock = boto3.client('bedrock-runtime',region_name=os.getenv('AWS_REGION'))
            app.logger.info("Bedrock client initialised successfully.")
            return bedrock
        except Exception as e:
            app.logger.error(f"Exception during bedrock initialisation: {e}")
            raise e
        
 
    def get_user_service_host_and_port(self):
        if self.users_api_url:
            app.logger.info(f"USERS_API_URL found in env variables: {self.users_api_url}")
            temp = self.users_api_url.replace("localhost","users")
            temp = temp.replace("8002","80")
            app.logger.info(f"USERS_API_URL changed to: {temp}")
            return temp
        else:
            app.logger.info("USERS_API_URL not found in env variables- if developping locally please check .env")
            app.logger.info("Retrieving user url from namespace")
            servicediscovery = boto3.client('servicediscovery')
            try:
                response = servicediscovery.discover_instances(
                NamespaceName='retaildemostore.local',
                ServiceName='users',
                MaxResults=1,
                HealthStatus='HEALTHY'
                )
                print(f"Retrieved users service: {response}")
                app.logger.info(f"Retrieved users service: {response}")
            except Exception as e:
                app.logger.info(f"Error retrieving users host using servicediscovery: {e}")
                raise
            temp_users_service_host = response['Instances'][0]['Attributes']['AWS_INSTANCE_IPV4']
            temp_users_api_url = f'http://{temp_users_service_host}:{self.users_service_port}' 
            app.logger.info(f"USERS_API_URL set to: {temp_users_api_url}")
            return temp_users_api_url
    
    bedrock = initialise_bedrock()
    
            
    def get_user(self, user_id):
        user_service_api_url = self.get_user_service_host_and_port()
        url = f"{user_service_api_url}/users/id/{user_id}"
        app.logger.info(f"Retrieving user info from {url}")
        response = requests.get(url)
        print(f"Retrieved user info from {url}: {response}")
        if response.ok:
            return response.json()
        app.logger.info(f"Error retrieving user info from {url}")
        return None
    
    def get_product(self, product_id):
        product_id = str(product_id.lower())
        app.logger.info(f"Retrieving product with id: {product_id}")
        try:
            response = self.dynamo_client.get_item(
                TableName=ddb_table_products,
                Key={
                    'id': product_id
                }
            )
            app.logger.info(f"Retrieved product: {response}")
        except Exception as e:
            app.logger.info(f"Error retrieving product with id: {product_id}")
            raise e
        if 'Item' in response:
            return response['Item']
    @staticmethod
    def getAgeRange(age: int) -> str:
        age_ranges = [
            (18, ""),
            (25, "18-24"),
            (35, "25-34"),
            (45, "35-44"),
            (55, "45-54"),
            (70, "55-69"),
            (float('inf'), "70-and-above"),
        ]
    
        for limit, label in age_ranges:
            if age < limit:
                return label  
    @staticmethod
    def generate_prompt(product, user_persona,user_age_range) -> str:
        description = product.get('description', '')
        product_name = product.get('name', '')
        product_category = product.get('category', '')
        product_style = product.get('style', '')
        template = (
            f"Given the following user details:\n"
            f"- User Age Range: {user_age_range}\n"
            f"- User Interests: {user_persona}\n"
            f"Given the following product details:\n"
            f"- Original Description: {description}\n"
            f"- Product Name: {product_name}\n"
            f"- Product Category: {product_category}\n"
            f"- Product Style: {product_style}\n"
            f"Please generate an enhanced and product description personalised for the user"  
            f"that incorporates all the above elements while ensuring "
            f"high-quality language and factual coherence. Make the description rich in relevant details "
            f"and present it in a format that includes:\n"
            f"- A compelling opening sentence\n"
            f"- Key features\n"
            f"- Benefits\n"
            f"- Each paragraph generated should be in xml format, like so: <p>Paragraph here</p>\n"
        )
        app.logger.info(f"Generated prompt: {template}")
        return template
    

    def generate_key(self,user_persona, user_age_range,product_id) -> str:
        return f"{user_persona}-{user_age_range}-{product_id}"
    
    def check_ddb_cache(self, persona_key):
        try:
            response = self.dynamo_client.get_item(
                TableName=ddb_table_personalised_product_descriptions,
                Key={
                    'id': persona_key
                }
            )
        except Exception as e:
            app.logger.info(f"Error retrieving personalised product description from DDB: {e}")
            raise e
        return response
    
    def cache_generated_description(self, persona_key, generated_description):
        try:
            self.dynamo_client.put_item(
                TableName=ddb_table_personalised_product_descriptions,
                Item={
                    'id': persona_key,
                    'generated_description': generated_description
                }
            )
        except Exception as e:
            app.logger.info(f"Error caching generated description for user: {persona_key}")
            raise e
    
    def generate_personalised_description(self, productid, userid) -> str:
        product = self.get_product(productid)
        user = self.get_user(userid)
        user_age_range = self.getAgeRange(user.get('age'))
        user_persona = user.get('persona')
        persona_key = self.generate_key(user_persona,user_age_range,productid)
        cached_description = self.check_ddb_cache(persona_key)
        if cached_description.get('Item') is not None:
            print(f"Cached description found is {cached_description}")
            generated_description = cached_description.get('Item').get('generated_description')
            return {'description':generated_description}
        prompt = self.generate_prompt(product, user_persona,user_age_range)
        claude_prompt = f"\n\nHuman:{prompt}\n\nAssistant:"
        body = json.dumps({
            "prompt": claude_prompt,
            "max_tokens_to_sample":2000,
            "temperature":0,
            "top_p":1,
            "stop_sequences": ["\n\nHuman:"],
            "top_k": 250
        })
        modelId = 'anthropic.claude-v2'
        accept = 'application/json'
        contentType = 'application/json'
        try:
            response = self.bedrock.invoke_model(
                body=body,
                modelId=modelId,
                accept=accept,
                contentType=contentType
            )
        except Exception as e:
            app.logger.info(f"Error invoking model: {e}")
            return {'description':''}
        response_body = json.loads(response.get('body').read())
        if 'Sorry' in response_body.get('completion'):
            app.logger.info('No description can be generated for product')
            return ''
    
        generated_description = ' '.join(response_body.get('completion').split('\n',2)[2:])
        self.cache_generated_description(
            persona_key=persona_key,
            generated_description=generated_description
            )
        return {'description':generated_description}