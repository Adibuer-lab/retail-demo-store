from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from flask import Flask, current_app
from dataclasses import fields

    
def get_valid_keys(cls):
        return {field.name for field in fields(cls)}
    
@dataclass
class Address:
    first_name: str
    last_name: str
    address1: str
    address2: str
    city: str
    state: str
    country: str
    zipcode: str
    default: bool

    def to_dict(self) -> Dict[str, Any]:
        address_dict = asdict(self)
        return address_dict

@dataclass
class User:
    id: str
    name: str
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""
    addresses: List[Address] = field(default_factory=list)
    age: int = 0
    age_range: Optional[str] = None
    gender: str = ""
    persona: str = ""
    discount_persona: str = ""
    selectable_user: Optional[bool] = None
    sign_up_date: Optional[datetime] = None
    last_sign_in_date: Optional[datetime] = None
    identity_id: Optional[str] = None
    phone_number: str = ""
    claimed_user: int = 0
    traits: Dict[str, Any] = field(default_factory=dict)
    platforms: Dict[str, Any] = field(default_factory=dict)
    username: str

    table_name = 'users'
    region = 'us-east-1'
    table = None
    
    


    @classmethod
    def init_app(cls, app: Flask) -> None:
        """
        Initialize the DynamoDB table with Flask application settings.
        """
        cls.table_name = app.config.get('DDB_TABLE_USERS', cls.table_name)
        cls.region = app.config.get('AWS_DEFAULT_REGION', cls.region)
        
        
        if 'DDB_ENDPOINT_OVERRIDE' in app.config:
            cls.dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url=app.config.get('DDB_ENDPOINT_OVERRIDE'),
                aws_access_key_id='XXXXk',
                aws_secret_access_key='XXXkX'
            )     
            app.logger.info(f"DynamoDB endpoint overridden: {app.config['DDB_ENDPOINT_OVERRIDE']}")
        else:
            cls.dynamodb = boto3.resource(
                'dynamodb'
                )     
        cls.table = cls.dynamodb.Table(cls.table_name)

    @classmethod
    def init_tables(cls):
        try:
            existing_tables = cls.dynamodb.meta.client.list_tables()['TableNames']
            if cls.table_name not in existing_tables:
                current_app.logger.info(f"Creating table {cls.table_name}")
                table = cls.dynamodb.create_table(
                    TableName=cls.table_name,
                    KeySchema=KEY_SCHEMA,
                    AttributeDefinitions=ATTRIBUTE_DEFINITIONS,
                    GlobalSecondaryIndexes=GLOBAL_SECONDARY_INDEXES,
                    BillingMode='PAY_PER_REQUEST'
                )
                table.meta.client.get_waiter('table_exists').wait(TableName=cls.table_name)
                current_app.logger.info(f"Table {cls.table_name} created successfully")
            else:
                current_app.logger.info(f"Table {cls.table_name} already exists")
            return True
        except ClientError as e:
            current_app.logger.error(f"Error initializing tables: {str(e)}")
            return False

    def to_dict(self) -> Dict[str, Any]:
        user_dict = asdict(self)
        if self.age:
            user_dict['age'] = int(self.age)
        
        if self.sign_up_date:
            user_dict['sign_up_date'] = self.sign_up_date.isoformat()
        if self.last_sign_in_date:
            user_dict['last_sign_in_date'] = self.last_sign_in_date.isoformat()
        return user_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        if 'addresses' in data:
            data['addresses'] = [Address(**addr) for addr in data['addresses']]
        if 'sign_up_date' in data and data['sign_up_date']:
            data['sign_up_date'] = datetime.fromisoformat(data['sign_up_date'].replace('Z', '+00:00'))
        if 'last_sign_in_date' in data and data['last_sign_in_date']:
            data['last_sign_in_date'] = datetime.fromisoformat(data['last_sign_in_date'].replace('Z', '+00:00'))
        return cls(**data)

def get_age_range(age: int) -> str:
    if age < 18:
        return ""
    elif age < 25:
        return "18-24"
    elif age < 35:
        return "25-34"
    elif age < 45:
        return "35-44"
    elif age < 55:
        return "45-54"
    elif age < 70:
        return "54-70"
    else:
        return "70-and-above"

# DynamoDB table and index definitions
KEY_SCHEMA = [
    {
        'AttributeName': 'id',
        'KeyType': 'HASH'  # Partition key
    }
]
ATTRIBUTE_DEFINITIONS = [
    {'AttributeName': 'id', 'AttributeType': 'S'},
    {'AttributeName': 'username', 'AttributeType': 'S'},
    {'AttributeName': 'claimed_user', 'AttributeType': 'N'},
    {'AttributeName': 'identity_id', 'AttributeType': 'S'}
]
GLOBAL_SECONDARY_INDEXES = [
    {
        'IndexName': 'username-index',
        'KeySchema': [{'AttributeName': 'username', 'KeyType': 'HASH'}],
        'Projection': {'ProjectionType': 'ALL'}
    },
    {
        'IndexName': 'claimed-index',
        'KeySchema': [{'AttributeName': 'claimed_user', 'KeyType': 'HASH'}],
        'Projection': {'ProjectionType': 'ALL'}
    },
    {
        'IndexName': 'identity_id-index',
        'KeySchema': [{'AttributeName': 'identity_id', 'KeyType': 'HASH'}],
        'Projection': {'ProjectionType': 'ALL'}
    }
]